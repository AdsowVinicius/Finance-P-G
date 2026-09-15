"""As 2 tasks essenciais do Celery (CLAUDE.md/arquitetura.mermaid):
processar_nota_fiscal (extrai chave → chama API → parse XML) e
processar_importacao_extrato (parse do arquivo + dispara o matching).

Ambas idempotentes: reprocessar não duplica dado nem gera cobrança
repetida na API paga.
"""

import logging
import uuid
from pathlib import Path

from app.config import settings
from app.database import SessionLocal
from app.models.conciliacao import Conciliacao
from app.models.conta_financeira import ContaFinanceira
from app.models.enums import (
    FormaBaixa,
    StatusConciliacaoLinha,
    StatusConta,
    StatusImportacao,
    StatusProcessamentoNota,
)
from app.models.extrato_importado import ExtratoImportado
from app.models.lancamento_extrato import LancamentoExtrato
from app.models.nota_fiscal import NotaFiscal
from app.models.parceiro import Parceiro
from app.services import whatsapp_client, whatsapp_service
from app.services.conciliacao_matcher import ConciliacaoMatcher, LancamentoParaConciliar
from app.services.extrato_parser_service import ExtratoParserService
from app.services.nfe_consulta_client import NfeConsultaClient, NfeConsultaError
from app.services.nota_fiscal_service import CNPJ_SENTINELA, obter_ou_criar_parceiro_por_cnpj
from app.services.recorrencia_service import RecorrenciaService
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="processar_nota_fiscal")
def processar_nota_fiscal(nota_fiscal_id: str) -> None:
    db = SessionLocal()
    try:
        nota = db.get(NotaFiscal, uuid.UUID(nota_fiscal_id))
        if nota is None or not nota.chave_acesso:
            return

        # idempotência: nota já resolvida não chama a API de novo
        if nota.status_processamento == StatusProcessamentoNota.concluido:
            return

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

        lancamentos_criados: list[LancamentoExtrato] = []
        for dto in lancamentos_dto:
            # idempotência: reimportar o mesmo extrato não duplica (UNIQUE conta_bancaria_id+fitid)
            existe = (
                db.query(LancamentoExtrato)
                .filter(
                    LancamentoExtrato.conta_bancaria_id == extrato.conta_bancaria_id,
                    LancamentoExtrato.fitid == dto.fitid,
                )
                .first()
            )
            if existe is not None:
                continue

            lancamento = LancamentoExtrato(
                extrato_importado_id=extrato.id,
                conta_bancaria_id=extrato.conta_bancaria_id,
                data=dto.data,
                descricao=dto.descricao,
                valor=dto.valor,
                tipo=dto.tipo,
                fitid=dto.fitid,
            )
            db.add(lancamento)
            lancamentos_criados.append(lancamento)

        db.flush()

        matcher = ConciliacaoMatcher(tolerancia_dias=tolerancia_dias)
        candidatas_pendentes = (
            db.query(ContaFinanceira)
            .filter(ContaFinanceira.status.in_([StatusConta.pendente, StatusConta.atrasado]))
            .all()
        )

        for lancamento in lancamentos_criados:
            resultado = matcher.conciliar(
                LancamentoParaConciliar(data=lancamento.data, valor=lancamento.valor, tipo=lancamento.tipo),
                candidatas_pendentes,
            )
            if not resultado.encontrou_match:
                continue

            for conta in resultado.contas:
                db.add(
                    Conciliacao(
                        lancamento_extrato_id=lancamento.id,
                        conta_financeira_id=conta.id,
                        valor_conciliado=conta.valor,
                        tipo_match=resultado.tipo_match,
                    )
                )
                conta.status = StatusConta.pago
                conta.data_pagamento = lancamento.data
                conta.valor_pago = conta.valor
                conta.forma_baixa = FormaBaixa.conciliacao_automatica
                candidatas_pendentes.remove(conta)  # não reusar a mesma conta noutro lançamento deste lote

            lancamento.status_conciliacao = StatusConciliacaoLinha.conciliado

        extrato.status = StatusImportacao.concluido
        db.commit()
    finally:
        db.close()


@celery_app.task(name="processar_mensagem_whatsapp")
def processar_mensagem_whatsapp(telefone: str, texto: str) -> None:
    db = SessionLocal()
    try:
        resposta = whatsapp_service.processar_mensagem(telefone, texto, db)
    except whatsapp_service.WhatsappIndisponivelError:
        resposta = "Assistente indisponível no momento — tente novamente mais tarde."
    finally:
        db.close()
    whatsapp_client.enviar_mensagem_texto(telefone, resposta)
