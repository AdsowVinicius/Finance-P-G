"""Agregações somente-leitura para o dashboard de indicadores (gráficos/KPIs)."""

import calendar
import uuid
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


def resumo(db: Session, mes_referencia: date | None = None) -> dict[str, Any]:
    """saldo_mes e juros_pagos_mes são escopados pelo mês de referência (padrão:
    mês atual do servidor). total_a_pagar_aberto/total_a_receber_aberto e
    contas_atrasadas_* são sempre "o que está em aberto agora" — não fazem
    sentido presos a um mês (uma conta atrasada continua atrasada não importa
    qual mês você está olhando), então ficam de fora do parâmetro.
    """
    inicio_mes, fim_mes = _limites_mes(mes_referencia or date.today())

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
        "juros_pagos_mes": juros_pagos_mes(db, inicio_mes, fim_mes),
    }


def juros_pagos_mes(db: Session, inicio_mes: date, fim_mes: date) -> Decimal:
    """Soma de (valor_pago - valor) das despesas pagas no mês onde se pagou
    a mais que a parcela original (boleto vencido, multa/juros etc.) —
    ignora os casos em que se pagou menos (desconto), que não é 'juros'.
    """
    diferenca = ContaFinanceira.valor_pago - ContaFinanceira.valor
    total = (
        db.query(func.coalesce(func.sum(diferenca), 0))
        .filter(
            ContaFinanceira.tipo_operacao == TipoOperacaoNota.entrada,
            ContaFinanceira.status == StatusConta.pago,
            ContaFinanceira.data_pagamento >= inicio_mes,
            ContaFinanceira.data_pagamento <= fim_mes,
            ContaFinanceira.valor_pago > ContaFinanceira.valor,
        )
        .scalar()
    )
    return Decimal(total)


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


def por_centro_custo(
    db: Session, tipo_operacao: TipoOperacaoNota = TipoOperacaoNota.entrada, mes_referencia: date | None = None
) -> list[dict[str, Any]]:
    inicio_mes, fim_mes = _limites_mes(mes_referencia or date.today())
    linhas = (
        db.query(CentroCusto.id, CentroCusto.nome, func.sum(ContaFinanceira.valor))
        .join(ContaFinanceira, ContaFinanceira.centro_custo_id == CentroCusto.id)
        .filter(
            ContaFinanceira.tipo_operacao == tipo_operacao,
            ContaFinanceira.data_vencimento >= inicio_mes,
            ContaFinanceira.data_vencimento <= fim_mes,
        )
        .group_by(CentroCusto.id, CentroCusto.nome)
        .order_by(func.sum(ContaFinanceira.valor).desc())
        .all()
    )
    return [{"centro_custo_id": centro_id, "centro_custo": nome, "total": Decimal(total)} for centro_id, nome, total in linhas]


def gastos_previstos_por_dia(db: Session, mes_referencia: date) -> list[dict[str, Any]]:
    """Total previsto (data_vencimento) por dia, pro mês de mes_referencia —
    granularidade sempre diária aqui; agrupar por semana/dia-da-semana é
    trabalho do frontend em cima dessa série (evita triplicar a mesma query).
    Usa data_vencimento (já passou pelo ajuste de dia útil na criação), então
    reflete a data real em que o dinheiro é esperado sair, não a data "crua".
    """
    inicio_mes, fim_mes = _limites_mes(mes_referencia)
    linhas = (
        db.query(ContaFinanceira.data_vencimento, func.coalesce(func.sum(ContaFinanceira.valor), 0))
        .filter(
            ContaFinanceira.tipo_operacao == TipoOperacaoNota.entrada,
            ContaFinanceira.status != StatusConta.cancelado,
            ContaFinanceira.data_vencimento >= inicio_mes,
            ContaFinanceira.data_vencimento <= fim_mes,
        )
        .group_by(ContaFinanceira.data_vencimento)
        .order_by(ContaFinanceira.data_vencimento)
        .all()
    )
    return [{"data": dia, "total": Decimal(total)} for dia, total in linhas]


def lucro_por_centro_custo(db: Session, mes_referencia: date | None = None) -> list[dict[str, Any]]:
    """Despesa e receita do mês lado a lado por centro de custo — todos os
    centros com algum lançamento no mês, não só os de despesa (diferente de
    por_centro_custo, que é só um lado). Lucro = receita - despesa, calculado
    no frontend a partir dos dois valores.
    """
    inicio_mes, fim_mes = _limites_mes(mes_referencia or date.today())
    linhas = (
        db.query(CentroCusto.id, CentroCusto.nome, ContaFinanceira.tipo_operacao, func.sum(ContaFinanceira.valor))
        .join(ContaFinanceira, ContaFinanceira.centro_custo_id == CentroCusto.id)
        .filter(ContaFinanceira.data_vencimento >= inicio_mes, ContaFinanceira.data_vencimento <= fim_mes)
        .group_by(CentroCusto.id, CentroCusto.nome, ContaFinanceira.tipo_operacao)
        .all()
    )

    por_centro: dict[uuid.UUID, dict[str, Any]] = {}
    for centro_id, nome, tipo, total in linhas:
        bucket = por_centro.setdefault(
            centro_id, {"centro_custo_id": centro_id, "centro_custo": nome, "despesa": Decimal("0"), "receita": Decimal("0")}
        )
        if tipo == TipoOperacaoNota.entrada:
            bucket["despesa"] = Decimal(total)
        else:
            bucket["receita"] = Decimal(total)

    resultado = list(por_centro.values())
    resultado.sort(key=lambda r: r["despesa"] + r["receita"], reverse=True)
    return resultado


def saude_financeira(db: Session) -> dict[str, Any]:
    """Indicadores financeiros "clássicos" de gestão de obra/construtora,
    pensados pra comparar com benchmark de mercado (não são recorte de mês —
    são visão de portfólio inteiro, igual contas_atrasadas/em_aberto).

    - margem_liquida_pct: (receita paga - despesa paga) / receita paga.
      Benchmark de mercado pra construtoras bem geridas: 5–8% (CFMA 2024).
    - dso_dias / dpo_dias: prazo médio real entre vencimento e pagamento
      (positivo = pagou depois do vencimento, negativo = pagou antes).
      DSO de construtora considerado saudável: < 35 dias.
    - indice_inadimplencia_pct: do que está em aberto hoje, quanto já venceu.
    - ticket_medio_despesa / ticket_medio_receita: valor médio por lançamento
      — mede o quão concentrada é a receita vs. pulverizada a despesa.
    """

    def soma_paga(tipo: TipoOperacaoNota) -> Decimal:
        total = (
            db.query(func.coalesce(func.sum(ContaFinanceira.valor_pago), 0))
            .filter(ContaFinanceira.tipo_operacao == tipo, ContaFinanceira.status == StatusConta.pago)
            .scalar()
        )
        return Decimal(total)

    despesa_paga = soma_paga(TipoOperacaoNota.entrada)
    receita_paga = soma_paga(TipoOperacaoNota.saida)
    margem_liquida_pct = ((receita_paga - despesa_paga) / receita_paga * 100) if receita_paga else Decimal("0")

    def prazo_medio(tipo: TipoOperacaoNota) -> Decimal:
        media = (
            db.query(func.avg(ContaFinanceira.data_pagamento - ContaFinanceira.data_vencimento))
            .filter(ContaFinanceira.tipo_operacao == tipo, ContaFinanceira.status == StatusConta.pago)
            .scalar()
        )
        return Decimal(str(round(float(media), 1))) if media is not None else Decimal("0")

    dpo_dias = prazo_medio(TipoOperacaoNota.entrada)
    dso_dias = prazo_medio(TipoOperacaoNota.saida)

    valor_atrasado = Decimal(
        db.query(func.coalesce(func.sum(ContaFinanceira.valor), 0))
        .filter(ContaFinanceira.status == StatusConta.atrasado)
        .scalar()
    )
    valor_pendente = Decimal(
        db.query(func.coalesce(func.sum(ContaFinanceira.valor), 0))
        .filter(ContaFinanceira.status == StatusConta.pendente)
        .scalar()
    )
    total_aberto = valor_atrasado + valor_pendente
    indice_inadimplencia_pct = (valor_atrasado / total_aberto * 100) if total_aberto else Decimal("0")

    def ticket_medio(tipo: TipoOperacaoNota) -> Decimal:
        media = db.query(func.avg(ContaFinanceira.valor)).filter(ContaFinanceira.tipo_operacao == tipo).scalar()
        return Decimal(media).quantize(Decimal("0.01")) if media is not None else Decimal("0")

    return {
        "margem_liquida_pct": margem_liquida_pct.quantize(Decimal("0.1")),
        "dso_dias": dso_dias,
        "dpo_dias": dpo_dias,
        "indice_inadimplencia_pct": indice_inadimplencia_pct.quantize(Decimal("0.1")),
        "ticket_medio_despesa": ticket_medio(TipoOperacaoNota.entrada),
        "ticket_medio_receita": ticket_medio(TipoOperacaoNota.saida),
    }


def notas_por_status(db: Session) -> list[dict[str, Any]]:
    linhas = (
        db.query(NotaFiscal.status, func.count())
        .join(Parceiro, NotaFiscal.parceiro_id == Parceiro.id)
        .filter(Parceiro.cnpj_cpf != CNPJ_SENTINELA)
        .group_by(NotaFiscal.status)
        .all()
    )
    return [{"status": status.value, "quantidade": qtd} for status, qtd in linhas]
