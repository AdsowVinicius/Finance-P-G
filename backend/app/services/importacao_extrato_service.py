"""Persistência + conciliação automática de lançamentos de extrato.

Compartilhado entre importação de arquivo (OFX/CSV) e sincronização Open
Finance: a origem dos `LancamentoExtratoDTO` muda, o tratamento não.
Idempotente por (conta_bancaria_id, fitid). Não commita — o chamador decide
a transação.
"""

import logging

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.conciliacao import Conciliacao
from app.models.conta_financeira import ContaFinanceira
from app.models.enums import FormaBaixa, StatusConciliacaoLinha, StatusConta
from app.models.extrato_importado import ExtratoImportado
from app.models.lancamento_extrato import LancamentoExtrato
from app.services.conciliacao_matcher import ConciliacaoMatcher, LancamentoParaConciliar
from app.services.extrato_parser_service import LancamentoExtratoDTO
from app.services.nota_fiscal_service import atualizar_status_conciliacao

logger = logging.getLogger(__name__)


def persistir_e_conciliar(
    db: Session,
    extrato: ExtratoImportado,
    lancamentos_dto: list[LancamentoExtratoDTO],
    tolerancia_dias: int = 5,
) -> int:
    """Grava os lançamentos novos e concilia automaticamente. Devolve
    quantos lançamentos novos foram criados."""
    lancamentos_criados: list[LancamentoExtrato] = []
    for indice, dto in enumerate(lancamentos_dto, start=1):
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
        try:
            # savepoint por lançamento: um conflito de integridade nesta
            # linha (ex: corrida com outra importação do mesmo fitid) só
            # descarta esta linha, nunca o lote inteiro.
            with db.begin_nested():
                db.add(lancamento)
                db.flush()
        except IntegrityError as exc:
            logger.warning(
                "lançamento #%d do extrato %s ignorado por conflito de integridade: %s", indice, extrato.id, exc
            )
            continue
        lancamentos_criados.append(lancamento)

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
            atualizar_status_conciliacao(db, conta.nota_fiscal_id)
            candidatas_pendentes.remove(conta)  # não reusar a mesma conta noutro lançamento deste lote

        lancamento.status_conciliacao = StatusConciliacaoLinha.conciliado

    return len(lancamentos_criados)
