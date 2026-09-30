"""Sincroniza a caixa de entrada de NFes (NFeDistribuicaoDFe) do certificado
ativo. Idempotente: `ult_nsu` avança só depois de gravar o lote, e
`chave_acesso` UNIQUE impede duplicata mesmo se o mesmo NSU for rebaixado.

Respeita as regras da SEFAZ: sem documento novo (137) ou consumo indevido
(656) o certificado fica bloqueado por 1h — consultar antes disso piora o
bloqueio.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.config import settings
from app.models.certificado_digital import CertificadoDigital
from app.models.nfe_sefaz_recebida import NfeSefazRecebida
from app.services import certificado_a1_service, certificado_service
from app.services.criptografia_service import CriptografiaInvalida, CriptografiaNaoConfigurada
from app.services.nfe_consulta_client import NfeConsultaError, parse_nfe_xml
from app.services.sefaz_dfe_client import (
    CSTAT_NENHUM_DOCUMENTO,
    SefazDfeClient,
    SefazError,
)

logger = logging.getLogger(__name__)

MAX_LOTES_POR_EXECUCAO = 10  # cada lote traz até 50 docs; evita loop longo numa task
ESPERA_APOS_SEM_DOCUMENTOS = timedelta(hours=1)


@dataclass
class ResultadoSincronizacaoDfe:
    ok: bool
    novos: int = 0
    mensagem: str = ""
    codigo: str | None = None  # "sem_certificado" | "bloqueado" | "erro_certificado" | "erro_sefaz"


def _gravar_documentos(db: Session, certificado: CertificadoDigital, documentos) -> int:
    novos = 0
    for doc in documentos:
        if doc.tipo not in ("resumo", "completo") or not doc.chave_acesso:
            continue  # eventos (cancelamento, CCe...) não entram na caixa de entrada

        dados_completos = None
        if doc.tipo == "completo":
            try:
                dados_completos = parse_nfe_xml(doc.xml)
            except NfeConsultaError:
                logger.warning("procNFe %s sem campos esperados; gravando sem extração", doc.chave_acesso)

        existente = db.query(NfeSefazRecebida).filter(NfeSefazRecebida.chave_acesso == doc.chave_acesso).first()
        if existente is not None:
            # resumo -> completo: atualiza (a SEFAZ entrega o completo depois da manifestação)
            if doc.tipo == "completo" and existente.tipo_documento == "resumo":
                existente.tipo_documento = "completo"
                existente.xml_bruto = doc.xml
            continue

        db.add(
            NfeSefazRecebida(
                certificado_id=certificado.id,
                nsu=doc.nsu,
                chave_acesso=doc.chave_acesso,
                cnpj_emitente=dados_completos.fornecedor_cnpj if dados_completos else doc.cnpj_emitente,
                nome_emitente=dados_completos.fornecedor_razao_social if dados_completos else doc.nome_emitente,
                valor_total=dados_completos.valor_total if dados_completos else doc.valor_total,
                data_emissao=dados_completos.data_emissao if dados_completos else doc.data_emissao,
                tipo_documento=doc.tipo,
                xml_bruto=doc.xml,
            )
        )
        novos += 1
    db.flush()
    return novos


def sincronizar(db: Session, cliente_factory=None) -> ResultadoSincronizacaoDfe:
    """`cliente_factory(certificado) -> SefazDfeClient` é injetável pra teste;
    o padrão abre o mTLS com o .pfx decifrado."""
    certificado = certificado_service.obter_ativo(db)
    if certificado is None:
        return ResultadoSincronizacaoDfe(ok=False, codigo="sem_certificado", mensagem="Nenhum certificado A1 ativo")

    agora = datetime.now(timezone.utc)
    if certificado.bloqueado_ate and certificado.bloqueado_ate > agora:
        return ResultadoSincronizacaoDfe(
            ok=False,
            codigo="bloqueado",
            mensagem=f"Aguardando liberação da SEFAZ até {certificado.bloqueado_ate.astimezone():%d/%m %H:%M}",
        )

    def _cliente_padrao(cert: CertificadoDigital) -> SefazDfeClient:
        pfx, senha = certificado_service.abrir(cert)
        with certificado_a1_service.contexto_mtls(pfx, senha, settings.sefaz_ca_bundle) as ctx:
            return SefazDfeClient(cert.cnpj, cert.uf_autor, settings.sefaz_ambiente, ssl_context=ctx)

    try:
        cliente = (cliente_factory or _cliente_padrao)(certificado)
    except (CriptografiaNaoConfigurada, CriptografiaInvalida, certificado_a1_service.CertificadoInvalido) as exc:
        return ResultadoSincronizacaoDfe(ok=False, codigo="erro_certificado", mensagem=str(exc))

    total_novos = 0
    mensagem = ""
    bloqueado = False
    try:
        for _ in range(MAX_LOTES_POR_EXECUCAO):
            retorno = cliente.consultar_por_nsu(certificado.ult_nsu)
            mensagem = f"{retorno.cstat} - {retorno.motivo}"

            if retorno.bloqueado:
                certificado.bloqueado_ate = agora + ESPERA_APOS_SEM_DOCUMENTOS
                bloqueado = True
                break

            total_novos += _gravar_documentos(db, certificado, retorno.documentos)
            certificado.ult_nsu = retorno.ult_nsu
            certificado.max_nsu = retorno.max_nsu

            if retorno.cstat == CSTAT_NENHUM_DOCUMENTO:
                certificado.bloqueado_ate = agora + ESPERA_APOS_SEM_DOCUMENTOS
                break
            db.commit()  # avança o NSU por lote: uma falha adiante não refaz o que já gravou
            if not retorno.tem_mais:
                break
    except SefazError as exc:
        db.rollback()
        certificado.ult_mensagem_sefaz = str(exc)
        db.commit()
        return ResultadoSincronizacaoDfe(ok=False, codigo="erro_sefaz", mensagem=str(exc), novos=total_novos)

    certificado.ult_sincronizacao = agora
    certificado.ult_mensagem_sefaz = mensagem
    db.commit()
    if bloqueado:
        return ResultadoSincronizacaoDfe(ok=False, codigo="bloqueado", novos=total_novos, mensagem=mensagem)
    return ResultadoSincronizacaoDfe(ok=True, novos=total_novos, mensagem=mensagem)
