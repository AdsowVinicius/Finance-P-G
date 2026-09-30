"""Tasks do Celery (CLAUDE.md/arquitetura.mermaid): processar_nota_fiscal
(extrai chave → chama API → parse XML), processar_importacao_extrato (parse
do arquivo + dispara o matching), e as 3 tasks do canal WhatsApp — mensagem
de texto, áudio (transcreve e trata como texto) e mídia de nota fiscal
(foto/PDF vira nota pendente de revisão).

Todas idempotentes onde faz sentido: reprocessar não duplica dado nem gera
cobrança repetida na API paga.
"""

import logging
import mimetypes
import uuid
from datetime import date
from decimal import Decimal
from pathlib import Path

from sqlalchemy.exc import IntegrityError

from app.config import settings
from app.core.storage import salvar_bytes
from app.database import SessionLocal
from app.models.conciliacao import Conciliacao
from app.models.conta_financeira import ContaFinanceira
from app.models.enums import (
    FormaBaixa,
    StatusConciliacaoLinha,
    StatusConta,
    StatusImportacao,
    StatusProcessamentoNota,
    TipoNota,
    TipoOperacaoNota,
)
from app.models.extrato_importado import ExtratoImportado
from app.models.lancamento_extrato import LancamentoExtrato
from app.models.nota_fiscal import NotaFiscal
from app.models.parceiro import Parceiro
from app.models.usuario import Usuario
from app.services import auditoria_service, transcricao_service, whatsapp_client, whatsapp_service
from app.services.conciliacao_matcher import ConciliacaoMatcher, LancamentoParaConciliar
from app.services.extrato_parser_service import ExtratoParserService
from app.services.importacao_extrato_service import persistir_e_conciliar
from app.services import open_finance_service, sefaz_sync_service
from app.services.pluggy_client import PluggyClient
from app.models.conta_bancaria import ContaBancaria
from app.models.nfe_sefaz_recebida import NfeSefazRecebida
from app.services.nfe_consulta_client import NfeConsultaClient, NfeConsultaError, parse_nfe_xml
from app.services.nota_fiscal_service import atualizar_status_conciliacao
from app.services.nota_fiscal_service import CNPJ_SENTINELA, obter_ou_criar_parceiro_por_cnpj
from app.services.nota_fiscal_service import NotaFiscalService, obter_ou_criar_parceiro_sentinela
from app.services.recorrencia_service import RecorrenciaService
from app.workers.celery_app import celery_app

_EXTENSOES_NOTA_WHATSAPP = {".pdf", ".jpg", ".jpeg", ".png"}

logger = logging.getLogger(__name__)


@celery_app.task(name="processar_nota_fiscal")
def processar_nota_fiscal(nota_fiscal_id: str) -> None:
    db = SessionLocal()
    try:
        # FOR UPDATE trava a linha até o commit/rollback desta task — evita
        # que um retry do broker (ou um .delay() duplicado) rodando em
        # paralelo passe pela checagem de idempotência abaixo antes do
        # primeiro processamento commitar, o que duplicaria as parcelas
        # geradas no bloco `eh_sentinela` mais adiante.
        nota = db.query(NotaFiscal).filter(NotaFiscal.id == uuid.UUID(nota_fiscal_id)).with_for_update().first()
        if nota is None or not nota.chave_acesso:
            return

        # idempotência: nota já resolvida não chama a API de novo
        if nota.status_processamento == StatusProcessamentoNota.concluido:
            return

        # Se o SEFAZ (certificado A1) já trouxe o XML completo desta chave,
        # usa ele: zero custo e nenhuma chamada externa.
        dados = None
        recebida = (
            db.query(NfeSefazRecebida)
            .filter(NfeSefazRecebida.chave_acesso == nota.chave_acesso, NfeSefazRecebida.tipo_documento == "completo")
            .first()
        )
        if recebida is not None and recebida.xml_bruto:
            try:
                dados = parse_nfe_xml(recebida.xml_bruto)
            except NfeConsultaError:
                logger.warning("XML completo do SEFAZ para %s não pôde ser lido; caindo pro provedor", nota.chave_acesso)

        if dados is None:
            client = NfeConsultaClient()
            if not client.configurado:
                logger.info("MEUDANFE_API_KEY não configurada — nota %s fica em consultando_api", nota_fiscal_id)
                return

            try:
                dados = client.consultar_e_extrair(nota.chave_acesso)
            except NfeConsultaError as exc:
                logger.warning("erro ao consultar NFe %s: %s", nota.chave_acesso, exc)
                nota.status_processamento = StatusProcessamentoNota.erro_api
                db.commit()
                return

        if dados is None:
            # not found no provedor: fica como erro_api (permite retry manual),
            # já que o enum não tem um status dedicado de "não encontrada".
            nota.status_processamento = StatusProcessamentoNota.erro_api
            db.commit()
            return

        nota.dados_extraidos_xml = {
            "fornecedor_cnpj": dados.fornecedor_cnpj,
            "fornecedor_razao_social": dados.fornecedor_razao_social,
            "valor_total": str(dados.valor_total),
            "data_emissao": dados.data_emissao.isoformat(),
        }

        # RF05/"único input manual é o PDF": se a nota foi criada no fluxo
        # automático (parceiro sentinela + valor/data placeholder — ver
        # routers/notas_fiscais.py), agora é a hora de preencher os dados de
        # verdade e gerar as parcelas, que ainda não existiam. Se o usuário
        # preencheu na mão no upload, isso NUNCA é sobrescrito — os dados da
        # API só entram em dados_extraidos_xml, como conferência/auditoria.
        eh_sentinela = (
            db.query(Parceiro).filter(Parceiro.id == nota.parceiro_id, Parceiro.cnpj_cpf == CNPJ_SENTINELA).first()
            is not None
        )

        if eh_sentinela:
            parceiro_real = obter_ou_criar_parceiro_por_cnpj(
                db, dados.fornecedor_cnpj, dados.fornecedor_razao_social, nota.tipo_operacao
            )
            nota.parceiro_id = parceiro_real.id
            nota.valor_total = dados.valor_total
            nota.data_emissao = dados.data_emissao
            db.flush()

            parcelas = RecorrenciaService().gerar_parcelas_valor_total(
                tipo_operacao=nota.tipo_operacao,
                parceiro_id=nota.parceiro_id,
                centro_custo_id=nota.centro_custo_id,
                descricao=f"NFe {nota.numero_nota or ''}".strip(),
                valor_total=nota.valor_total,
                numero_parcelas=nota.numero_parcelas,
                data_inicio=nota.data_emissao,
                nota_fiscal_id=nota.id,
            )
            db.add_all(parcelas)

        nota.status_processamento = StatusProcessamentoNota.concluido

        pasta_xml = Path(settings.storage_dir) / "notas"
        pasta_xml.mkdir(parents=True, exist_ok=True)
        caminho_xml = pasta_xml / f"{nota.id}.xml"
        caminho_xml.write_text(dados.xml_bruto, encoding="utf-8")
        nota.arquivo_xml_path = f"notas/{nota.id}.xml"

        db.commit()
    finally:
        db.close()


@celery_app.task(name="processar_importacao_extrato")
def processar_importacao_extrato(extrato_importado_id: str, tolerancia_dias: int = 5) -> None:
    db = SessionLocal()
    try:
        extrato = db.get(ExtratoImportado, uuid.UUID(extrato_importado_id))
        if extrato is None:
            return

        try:
            conteudo_bytes = (Path(settings.storage_dir) / extrato.arquivo_original_path).read_bytes()
            lancamentos_dto = ExtratoParserService().parse(extrato.formato, conteudo_bytes)
        except Exception as exc:  # parsing pode falhar de várias formas (arquivo malformado etc.)
            extrato.status = StatusImportacao.erro
            extrato.mensagem_erro = str(exc)
            db.commit()
            return

        try:
            persistir_e_conciliar(db, extrato, lancamentos_dto, tolerancia_dias)

            extrato.status = StatusImportacao.concluido
            db.commit()
        except Exception as exc:
            # guarda geral: qualquer falha inesperada aqui (não só a
            # montagem dos lançamentos) não pode deixar o extrato preso
            # indefinidamente em "processando" sem sinalizar erro.
            db.rollback()
            extrato.status = StatusImportacao.erro
            extrato.mensagem_erro = str(exc)
            db.commit()
    finally:
        db.close()


@celery_app.task(name="processar_mensagem_whatsapp")
def processar_mensagem_whatsapp(
    telefone: str, texto: str, phone_number_id: str | None = None, wamid: str | None = None
) -> None:
    db = SessionLocal()
    try:
        # idempotência: a Cloud API reentrega webhook (timeout, non-200 etc.)
        # — sem isso, a reentrega processaria a mesma mensagem de novo.
        if not whatsapp_service.marcar_mensagem_como_processada(db, wamid):
            return
        resposta = whatsapp_service.processar_mensagem(telefone, texto, db)
    except whatsapp_service.WhatsappIndisponivelError:
        resposta = "Assistente indisponível no momento — tente novamente mais tarde."
    finally:
        db.close()
    whatsapp_client.enviar_mensagem_texto(telefone, resposta, phone_number_id)


@celery_app.task(name="processar_audio_whatsapp")
def processar_audio_whatsapp(
    telefone: str, media_id: str, phone_number_id: str | None = None, wamid: str | None = None
) -> None:
    """Voice note do WhatsApp: baixa o áudio, transcreve localmente (Whisper,
    sem API paga) e trata o texto resultante exatamente como se tivesse sido
    digitado — reaproveita o mesmo processar_mensagem do RF16/pré-lançamento.
    """
    db_dedup = SessionLocal()
    try:
        if not whatsapp_service.marcar_mensagem_como_processada(db_dedup, wamid):
            return
    finally:
        db_dedup.close()

    try:
        conteudo, _mime_type = whatsapp_client.baixar_midia(media_id)
    except Exception:
        logger.exception("Falha ao baixar áudio do WhatsApp (media_id=%s)", media_id)
        whatsapp_client.enviar_mensagem_texto(telefone, "Não consegui baixar seu áudio — tenta de novo?", phone_number_id)
        return

    try:
        texto = transcricao_service.transcrever(conteudo)
    except Exception:
        logger.exception("Falha ao transcrever áudio do WhatsApp (media_id=%s)", media_id)
        whatsapp_client.enviar_mensagem_texto(
            telefone, "Não consegui processar seu áudio — pode tentar de novo ou mandar por texto?", phone_number_id
        )
        return

    if not texto:
        whatsapp_client.enviar_mensagem_texto(
            telefone, "Não consegui entender o áudio — pode tentar de novo ou mandar por texto?", phone_number_id
        )
        return

    db = SessionLocal()
    try:
        resposta = whatsapp_service.processar_mensagem(telefone, texto, db)
    except whatsapp_service.WhatsappIndisponivelError:
        resposta = "Assistente indisponível no momento — tente novamente mais tarde."
    finally:
        db.close()
    whatsapp_client.enviar_mensagem_texto(telefone, f'"{texto}"\n\n{resposta}', phone_number_id)


@celery_app.task(name="processar_midia_nota_whatsapp")
def processar_midia_nota_whatsapp(
    telefone: str,
    media_id: str,
    tipo_midia: str,
    phone_number_id: str | None = None,
    wamid: str | None = None,
) -> None:
    """Foto ou PDF de nota fiscal mandado por WhatsApp: baixa, tenta achar a
    chave de acesso (só funciona em PDF com camada de texto — foto sempre
    cai no fallback manual, igual upload de PDF escaneado) e cria a nota
    fiscal pendente de revisão (sem centro de custo, que só existe no app).
    """
    db = SessionLocal()
    try:
        if not whatsapp_service.marcar_mensagem_como_processada(db, wamid):
            return

        usuario = db.query(Usuario).filter(Usuario.telefone_whatsapp == telefone).first()
        if usuario is None:
            whatsapp_client.enviar_mensagem_texto(
                telefone,
                "Esse número ainda não está vinculado a um usuário do Finance P&G. Peça pra um admin "
                "vincular seu WhatsApp no sistema antes de mandar notas por aqui.",
                phone_number_id,
            )
            return

        try:
            conteudo, mime_type = whatsapp_client.baixar_midia(media_id)
        except Exception:
            logger.exception("Falha ao baixar mídia do WhatsApp (media_id=%s)", media_id)
            whatsapp_client.enviar_mensagem_texto(telefone, "Não consegui baixar o arquivo — tenta mandar de novo?", phone_number_id)
            return

        extensao = mimetypes.guess_extension(mime_type.split(";")[0].strip()) or (
            ".pdf" if tipo_midia == "document" else ".jpg"
        )
        if extensao not in _EXTENSOES_NOTA_WHATSAPP:
            whatsapp_client.enviar_mensagem_texto(
                telefone, "Esse tipo de arquivo eu ainda não processo — manda em PDF, JPG ou PNG.", phone_number_id
            )
            return

        caminho = salvar_bytes(conteudo, "notas", f"whatsapp{extensao}", extensoes_permitidas=_EXTENSOES_NOTA_WHATSAPP)

        chave_acesso = NotaFiscalService().extrair_chave_de_pdf(conteudo) if extensao == ".pdf" else None
        if chave_acesso and db.query(NotaFiscal).filter(NotaFiscal.chave_acesso == chave_acesso).first():
            whatsapp_client.enviar_mensagem_texto(telefone, "Essa nota fiscal já estava cadastrada no sistema.", phone_number_id)
            return

        status_processamento = (
            StatusProcessamentoNota.consultando_api if chave_acesso else StatusProcessamentoNota.chave_nao_encontrada
        )
        parceiro_sentinela = obter_ou_criar_parceiro_sentinela(db)
        nota = NotaFiscal(
            parceiro_id=parceiro_sentinela.id,
            centro_custo_id=None,
            tipo=TipoNota.nfe,
            tipo_operacao=TipoOperacaoNota.entrada,
            chave_acesso=chave_acesso,
            valor_total=Decimal("0.01"),
            data_emissao=date.today(),
            arquivo_pdf_path=caminho,
            status_processamento=status_processamento,
            criado_por=usuario.id,
        )
        db.add(nota)
        db.flush()
        auditoria_service.registrar_criacao(db, usuario.id, "notas_fiscais", nota)
        db.commit()
        db.refresh(nota)
        nota_id = str(nota.id)
    finally:
        db.close()

    if status_processamento == StatusProcessamentoNota.consultando_api:
        processar_nota_fiscal.delay(nota_id)
        resposta = (
            "Recebi sua nota fiscal! Encontrei a chave de acesso e já tô consultando os dados — "
            "confira em Notas Fiscais no sistema em alguns instantes."
        )
    else:
        resposta = (
            "Recebi seu arquivo e salvei como nota fiscal pendente! Não consegui identificar a chave de "
            "acesso automaticamente (comum em foto) — entra no sistema, na tela de Notas Fiscais, pra "
            "completar os dados ou colar a chave manualmente."
        )
    whatsapp_client.enviar_mensagem_texto(telefone, resposta, phone_number_id)


@celery_app.task(name="sincronizar_dfe")
def sincronizar_dfe() -> dict:
    """Baixa NFes emitidas contra o CNPJ do certificado A1 ativo (SEFAZ).
    Idempotente: NSU só avança depois de gravar e chave_acesso é UNIQUE."""
    db = SessionLocal()
    try:
        resultado = sefaz_sync_service.sincronizar(db)
        logger.info("sincronizar_dfe: ok=%s novos=%s %s", resultado.ok, resultado.novos, resultado.mensagem)
        return {"ok": resultado.ok, "novos": resultado.novos, "mensagem": resultado.mensagem}
    finally:
        db.close()


@celery_app.task(name="sincronizar_open_finance_conta")
def sincronizar_open_finance_conta(conta_bancaria_id: str) -> dict:
    db = SessionLocal()
    try:
        conta = db.get(ContaBancaria, uuid.UUID(conta_bancaria_id))
        if conta is None:
            return {"ok": False, "erro": "conta não encontrada"}
        cliente = PluggyClient()
        if not cliente.configurado:
            return {"ok": False, "erro": "Pluggy não configurado"}
        resultado = open_finance_service.sincronizar_conta(db, conta, cliente)
        if not resultado.ok:
            logger.warning("Open Finance: conta %s falhou: %s", conta_bancaria_id, resultado.erro)
        return {"ok": resultado.ok, "novos": resultado.novos, "erro": resultado.erro}
    finally:
        db.close()


@celery_app.task(name="sincronizar_open_finance_todas")
def sincronizar_open_finance_todas() -> int:
    """Agendada (beat): enfileira a sincronização de cada conta vinculada."""
    db = SessionLocal()
    try:
        ids = [
            str(c.id)
            for c in db.query(ContaBancaria)
            .filter(ContaBancaria.open_finance_conta_id.isnot(None), ContaBancaria.ativo.is_(True))
            .all()
        ]
    finally:
        db.close()
    for conta_id in ids:
        sincronizar_open_finance_conta.delay(conta_id)
    return len(ids)
