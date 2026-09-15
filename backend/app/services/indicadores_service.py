"""Agregações somente-leitura para o dashboard de indicadores (gráficos/KPIs)."""

import calendar
from datetime import date
from decimal import Decimal
from typing import Any

from dateutil.relativedelta import relativedelta
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.centro_custo import CentroCusto
from app.models.conta_financeira import ContaFinanceira
from app.models.enums import StatusConta, TipoOperacaoNota
from app.models.nota_fiscal import NotaFiscal
from app.models.parceiro import Parceiro
from app.services.nota_fiscal_service import CNPJ_SENTINELA


def _limites_mes(referencia: date) -> tuple[date, date]:
    ultimo_dia = calendar.monthrange(referencia.year, referencia.month)[1]
    return referencia.replace(day=1), date(referencia.year, referencia.month, ultimo_dia)


def resumo(db: Session) -> dict[str, Any]:
    hoje = date.today()
    inicio_mes, fim_mes = _limites_mes(hoje)

    def soma_paga(tipo: TipoOperacaoNota) -> Decimal:
        total = (
            db.query(func.coalesce(func.sum(ContaFinanceira.valor_pago), 0))
            .filter(
                ContaFinanceira.tipo_operacao == tipo,
                ContaFinanceira.status == StatusConta.pago,
                ContaFinanceira.data_pagamento >= inicio_mes,
                ContaFinanceira.data_pagamento <= fim_mes,
            )
            .scalar()
        )
        return Decimal(total)

    def soma_aberta(tipo: TipoOperacaoNota) -> Decimal:
        total = (
            db.query(func.coalesce(func.sum(ContaFinanceira.valor), 0))
            .filter(
                ContaFinanceira.tipo_operacao == tipo,
                ContaFinanceira.status.in_([StatusConta.pendente, StatusConta.atrasado]),
            )
            .scalar()
        )
        return Decimal(total)

    # entrada = despesa (a pagar), saida = receita (a receber) — schema.sql
    saldo_mes = soma_paga(TipoOperacaoNota.saida) - soma_paga(TipoOperacaoNota.entrada)

    qtd_atrasadas, total_atrasadas = (
        db.query(func.count(), func.coalesce(func.sum(ContaFinanceira.valor), 0))
        .filter(ContaFinanceira.status == StatusConta.atrasado)
        .first()
    )

    return {
        "saldo_mes": saldo_mes,
        "total_a_pagar_aberto": soma_aberta(TipoOperacaoNota.entrada),
        "total_a_receber_aberto": soma_aberta(TipoOperacaoNota.saida),
        "contas_atrasadas_qtd": qtd_atrasadas,
        "contas_atrasadas_total": Decimal(total_atrasadas),
    }


def evolucao_mensal(db: Session, meses: int = 6) -> list[dict[str, Any]]:
    hoje = date.today()
    inicio = hoje.replace(day=1) - relativedelta(months=meses - 1)

    mes_expr = func.date_trunc("month", ContaFinanceira.data_vencimento)
    linhas = (
        db.query(mes_expr.label("mes"), ContaFinanceira.tipo_operacao, func.sum(ContaFinanceira.valor))
        .filter(ContaFinanceira.data_vencimento >= inicio)
        .group_by(mes_expr, ContaFinanceira.tipo_operacao)
        .all()
    )

    por_mes: dict[str, dict[str, Decimal]] = {}
    for mes_dt, tipo, total in linhas:
        chave = mes_dt.strftime("%Y-%m")
        bucket = por_mes.setdefault(chave, {"pago": Decimal("0"), "recebido": Decimal("0")})
        if tipo == TipoOperacaoNota.entrada:
            bucket["pago"] = Decimal(total)
        else:
            bucket["recebido"] = Decimal(total)

    resultado = []
    cursor = inicio
    for _ in range(meses):
        chave = cursor.strftime("%Y-%m")
        valores = por_mes.get(chave, {"pago": Decimal("0"), "recebido": Decimal("0")})
        resultado.append({"mes": chave, "total_pago": valores["pago"], "total_recebido": valores["recebido"]})
        cursor += relativedelta(months=1)
    return resultado


def por_centro_custo(db: Session, tipo_operacao: TipoOperacaoNota = TipoOperacaoNota.entrada) -> list[dict[str, Any]]:
    inicio_mes, fim_mes = _limites_mes(date.today())
    linhas = (
        db.query(CentroCusto.nome, func.sum(ContaFinanceira.valor))
        .join(ContaFinanceira, ContaFinanceira.centro_custo_id == CentroCusto.id)
        .filter(
            ContaFinanceira.tipo_operacao == tipo_operacao,
            ContaFinanceira.data_vencimento >= inicio_mes,
            ContaFinanceira.data_vencimento <= fim_mes,
        )
        .group_by(CentroCusto.nome)
        .order_by(func.sum(ContaFinanceira.valor).desc())
        .all()
    )
    return [{"centro_custo": nome, "total": Decimal(total)} for nome, total in linhas]


def notas_por_status(db: Session) -> list[dict[str, Any]]:
    linhas = (
        db.query(NotaFiscal.status, func.count())
        .join(Parceiro, NotaFiscal.parceiro_id == Parceiro.id)
        .filter(Parceiro.cnpj_cpf != CNPJ_SENTINELA)
        .group_by(NotaFiscal.status)
        .all()
    )
    return [{"status": status.value, "quantidade": qtd} for status, qtd in linhas]
