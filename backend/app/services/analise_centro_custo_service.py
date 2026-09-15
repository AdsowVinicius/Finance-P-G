"""Análise financeira por centro de custo (obra) — resumo do projeto inteiro
(não só do mês) e Curva S (planejado x realizado acumulado).
"""

import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.conta_financeira import ContaFinanceira
from app.models.enums import StatusConta, TipoOperacaoNota
from app.models.orcamento_centro_custo import OrcamentoCentroCusto


def resumo_centro_custo(db: Session, centro_custo_id: uuid.UUID) -> dict[str, Any]:
    """Totais do projeto inteiro (sem recorte de mês — uma obra dura vários
    meses): o que já foi realizado (pago) e o que ainda está em aberto
    (pendente/atrasado), separado por despesa/receita.
    """

    def soma(tipo: TipoOperacaoNota, *, realizado: bool) -> Decimal:
        query = db.query(func.coalesce(func.sum(ContaFinanceira.valor), 0)).filter(
            ContaFinanceira.centro_custo_id == centro_custo_id, ContaFinanceira.tipo_operacao == tipo
        )
        if realizado:
            query = query.filter(ContaFinanceira.status == StatusConta.pago)
        else:
            query = query.filter(ContaFinanceira.status.in_([StatusConta.pendente, StatusConta.atrasado]))
        return Decimal(query.scalar())

    despesas_realizadas = soma(TipoOperacaoNota.entrada, realizado=True)
    receitas_realizadas = soma(TipoOperacaoNota.saida, realizado=True)

    return {
        "despesas_realizadas": despesas_realizadas,
        "receitas_realizadas": receitas_realizadas,
        "saldo_realizado": receitas_realizadas - despesas_realizadas,
        "despesas_futuras": soma(TipoOperacaoNota.entrada, realizado=False),
        "receitas_futuras": soma(TipoOperacaoNota.saida, realizado=False),
    }


def curva_s(db: Session, centro_custo_id: uuid.UUID) -> list[dict[str, Any]]:
    """Planejado (orcamentos_centro_custo) x realizado (despesa por
    data_vencimento) acumulado, mês a mês, cobrindo todo mês que tenha
    orçamento OU lançamento — não só o intervalo com os dois.
    """
    planejado_linhas = (
        db.query(OrcamentoCentroCusto.mes_referencia, OrcamentoCentroCusto.valor_planejado)
        .filter(OrcamentoCentroCusto.centro_custo_id == centro_custo_id)
        .all()
    )

    mes_expr = func.date_trunc("month", ContaFinanceira.data_vencimento)
    realizado_linhas = (
        db.query(mes_expr.label("mes"), func.sum(ContaFinanceira.valor))
        .filter(
            ContaFinanceira.centro_custo_id == centro_custo_id,
            ContaFinanceira.tipo_operacao == TipoOperacaoNota.entrada,
        )
        .group_by(mes_expr)
        .all()
    )

    planejado_por_mes = {m.strftime("%Y-%m"): Decimal(v) for m, v in planejado_linhas}
    realizado_por_mes = {m.strftime("%Y-%m"): Decimal(v) for m, v in realizado_linhas}

    todos_meses = sorted(set(planejado_por_mes) | set(realizado_por_mes))

    resultado = []
    acumulado_planejado = Decimal("0")
    acumulado_realizado = Decimal("0")
    for mes in todos_meses:
        planejado_mes = planejado_por_mes.get(mes, Decimal("0"))
        realizado_mes = realizado_por_mes.get(mes, Decimal("0"))
        acumulado_planejado += planejado_mes
        acumulado_realizado += realizado_mes
        resultado.append(
            {
                "mes": mes,
                "planejado_mes": planejado_mes,
                "realizado_mes": realizado_mes,
                "planejado_acumulado": acumulado_planejado,
                "realizado_acumulado": acumulado_realizado,
            }
        )
    return resultado
