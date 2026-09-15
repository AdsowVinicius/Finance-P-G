"""Conciliação manual — RF04: 'Divergências não resolvidas automaticamente
ficam disponíveis para conciliação manual.' O motor automático
(ConciliacaoMatcher, rodado na importação do extrato) já cobre match exato,
match com tolerância de data e split simples; o que sobra pendente cai aqui
pro financeiro resolver escolhendo manualmente a(s) conta(s) — sempre valor
exato, nunca tolerância de valor, igual à regra automática.
"""

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, require_write_access
from app.database import get_db
from app.models.conciliacao import Conciliacao
from app.models.conta_financeira import ContaFinanceira
from app.models.enums import FormaBaixa, StatusConciliacaoLinha, StatusConta, TipoLancamentoExtrato, TipoMatch, TipoOperacaoNota
from app.models.lancamento_extrato import LancamentoExtrato
from app.models.usuario import Usuario
from app.schemas.conta_financeira import ContaFinanceiraRead
from app.schemas.extrato import ConciliarManualRequest, LancamentoExtratoRead
from app.services import auditoria_service
from app.services.nota_fiscal_service import atualizar_status_conciliacao

router = APIRouter(prefix="/conciliacoes", tags=["conciliação"], dependencies=[Depends(get_current_user)])


def _direcao_esperada(tipo: TipoLancamentoExtrato) -> TipoOperacaoNota:
    # mesma regra do ConciliacaoMatcher: crédito no extrato = dinheiro
    # entrando = quita conta a RECEBER (saida); débito = quita conta a PAGAR (entrada)
    return TipoOperacaoNota.saida if tipo == TipoLancamentoExtrato.credito else TipoOperacaoNota.entrada


@router.get("/pendentes", response_model=list[LancamentoExtratoRead])
def listar_pendentes(conta_bancaria_id: uuid.UUID | None = None, db: Session = Depends(get_db)) -> list[LancamentoExtrato]:
    query = db.query(LancamentoExtrato).filter(
        LancamentoExtrato.status_conciliacao.in_([StatusConciliacaoLinha.pendente, StatusConciliacaoLinha.divergente])
    )
    if conta_bancaria_id is not None:
        query = query.filter(LancamentoExtrato.conta_bancaria_id == conta_bancaria_id)
    return query.order_by(LancamentoExtrato.data.desc()).all()


@router.get("/{lancamento_id}/candidatas", response_model=list[ContaFinanceiraRead])
def listar_candidatas(lancamento_id: uuid.UUID, db: Session = Depends(get_db)) -> list[ContaFinanceira]:
    lancamento = db.get(LancamentoExtrato, lancamento_id)
    if lancamento is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lançamento não encontrado")

    direcao = _direcao_esperada(lancamento.tipo)
    return (
        db.query(ContaFinanceira)
        .filter(
            ContaFinanceira.tipo_operacao == direcao,
            ContaFinanceira.status.in_([StatusConta.pendente, StatusConta.atrasado]),
        )
        .order_by(ContaFinanceira.data_vencimento)
        .all()
    )


@router.post("/{lancamento_id}/confirmar", dependencies=[Depends(require_write_access)])
def confirmar_manual(
    lancamento_id: uuid.UUID,
    dados: ConciliarManualRequest,
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(get_current_user),
) -> dict[str, object]:
    lancamento = db.get(LancamentoExtrato, lancamento_id)
    if lancamento is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lançamento não encontrado")
    if lancamento.status_conciliacao == StatusConciliacaoLinha.conciliado:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Lançamento já foi conciliado")

    contas = db.query(ContaFinanceira).filter(ContaFinanceira.id.in_(dados.contas_financeira_ids)).all()
    if len(contas) != len(dados.contas_financeira_ids):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Uma ou mais contas não foram encontradas")

    direcao = _direcao_esperada(lancamento.tipo)
    for conta in contas:
        if conta.tipo_operacao != direcao:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"'{conta.descricao}' tem tipo de operação incompatível com o lançamento",
            )
        if conta.status not in (StatusConta.pendente, StatusConta.atrasado):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail=f"'{conta.descricao}' já não está pendente"
            )

    soma = sum((c.valor for c in contas), Decimal("0"))
    if soma != lancamento.valor:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"A soma das contas selecionadas (R$ {soma}) não bate com o valor do lançamento (R$ {lancamento.valor})",
        )

    agora = datetime.now(timezone.utc)
    antes_lancamento = auditoria_service.snapshot(lancamento)
    for conta in contas:
        db.add(
            Conciliacao(
                lancamento_extrato_id=lancamento.id,
                conta_financeira_id=conta.id,
                valor_conciliado=conta.valor,
                tipo_match=TipoMatch.manual,
                confirmado_por=usuario_atual.id,
                confirmado_em=agora,
            )
        )
        antes_conta = auditoria_service.snapshot(conta)
        conta.status = StatusConta.pago
        conta.data_pagamento = lancamento.data
        conta.valor_pago = conta.valor
        conta.forma_baixa = FormaBaixa.manual
        atualizar_status_conciliacao(db, conta.nota_fiscal_id)
        auditoria_service.registrar_edicao(db, usuario_atual.id, "contas_financeiras", antes_conta, conta)

    lancamento.status_conciliacao = StatusConciliacaoLinha.conciliado
    auditoria_service.registrar_edicao(db, usuario_atual.id, "lancamentos_extrato", antes_lancamento, lancamento)
    db.commit()
    return {"status": "conciliado", "contas_baixadas": len(contas)}


@router.post("/{lancamento_id}/ignorar", dependencies=[Depends(require_write_access)])
def ignorar(
    lancamento_id: uuid.UUID, db: Session = Depends(get_db), usuario_atual: Usuario = Depends(get_current_user)
) -> dict[str, str]:
    lancamento = db.get(LancamentoExtrato, lancamento_id)
    if lancamento is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lançamento não encontrado")
    if lancamento.status_conciliacao == StatusConciliacaoLinha.conciliado:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Lançamento já foi conciliado")

    antes = auditoria_service.snapshot(lancamento)
    lancamento.status_conciliacao = StatusConciliacaoLinha.ignorado
    auditoria_service.registrar_edicao(db, usuario_atual.id, "lancamentos_extrato", antes, lancamento)
    db.commit()
    return {"status": "ignorado"}


@router.post("/{lancamento_id}/reverter", dependencies=[Depends(require_write_access)])
def reverter(
    lancamento_id: uuid.UUID, db: Session = Depends(get_db), usuario_atual: Usuario = Depends(get_current_user)
) -> dict[str, str]:
    """Desfaz uma conciliação (automática ou manual) ou um 'ignorar',
    devolvendo o lançamento e as contas envolvidas pro estado pendente.
    """
    lancamento = db.get(LancamentoExtrato, lancamento_id)
    if lancamento is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lançamento não encontrado")

    antes_lancamento = auditoria_service.snapshot(lancamento)
    conciliacoes = db.query(Conciliacao).filter(Conciliacao.lancamento_extrato_id == lancamento_id).all()
    for conciliacao in conciliacoes:
        if conciliacao.conta_financeira_id is not None:
            conta = db.get(ContaFinanceira, conciliacao.conta_financeira_id)
            if conta is not None:
                antes_conta = auditoria_service.snapshot(conta)
                conta.status = StatusConta.pendente
                conta.data_pagamento = None
                conta.valor_pago = None
                conta.forma_baixa = None
                atualizar_status_conciliacao(db, conta.nota_fiscal_id)
                auditoria_service.registrar_edicao(db, usuario_atual.id, "contas_financeiras", antes_conta, conta)
        db.delete(conciliacao)

    lancamento.status_conciliacao = StatusConciliacaoLinha.pendente
    auditoria_service.registrar_edicao(db, usuario_atual.id, "lancamentos_extrato", antes_lancamento, lancamento)
    db.commit()
    return {"status": "revertido"}
