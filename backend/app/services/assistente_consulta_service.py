"""RF16 — assistente de consulta em linguagem natural.

Chama o Claude Haiku 4.5 (Anthropic API) restrito a um conjunto fixo de
funções de consulta pré-definidas (tool use) — nunca geração livre de SQL.
Cada função aqui é só leitura, monta a query com SQLAlchemy e devolve um
dict serializável; o modelo nunca vê nem escreve SQL.
"""

import calendar
import json
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

import anthropic
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import settings
from app.models.conta_financeira import ContaFinanceira
from app.models.enums import StatusConta, StatusNota, TipoOperacaoNota
from app.models.nota_fiscal import NotaFiscal
from app.models.parceiro import Parceiro
from app.services.nota_fiscal_service import CNPJ_SENTINELA

_MAX_ITERACOES_TOOL_USE = 4

_SYSTEM_PROMPT = (
    "Você é o assistente financeiro interno da P&G Engenharia. Responda perguntas sobre "
    "contas a pagar/receber e notas fiscais SOMENTE com base no retorno das funções de "
    "consulta disponíveis — nunca invente números. Se uma função não cobrir a pergunta, "
    "diga que não tem essa informação disponível. Responda em português, de forma direta "
    "e objetiva, citando valores sempre como R$ com duas casas decimais."
)

_FERRAMENTAS: list[dict[str, Any]] = [
    {
        "name": "consultar_vencimentos",
        "description": (
            "Lista contas a pagar/receber pendentes ou atrasadas que vencem entre hoje e "
            "N dias à frente (inclui as já atrasadas). Use para perguntas tipo 'o que vence "
            "essa semana' ou 'o que vence nos próximos 15 dias'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "dias": {
                    "type": "integer",
                    "description": "Janela de dias a partir de hoje (padrão 7).",
                },
                "tipo_operacao": {
                    "type": "string",
                    "enum": ["entrada", "saida"],
                    "description": "Filtra só contas a pagar (entrada) ou a receber (saida). Omitir para ambos.",
                },
            },
        },
    },
    {
        "name": "consultar_atrasados",
        "description": "Lista contas a pagar/receber com status atrasado (vencimento já passou e não foi paga).",
        "input_schema": {
            "type": "object",
            "properties": {
                "tipo_operacao": {
                    "type": "string",
                    "enum": ["entrada", "saida"],
                    "description": "Filtra só contas a pagar (entrada) ou a receber (saida). Omitir para ambos.",
                },
            },
        },
    },
    {
        "name": "consultar_total_gasto",
        "description": (
            "Soma o total de contas a pagar (saída) em um mês/ano. Use para 'quanto gastei "
            "esse mês' ou 'quanto vou gastar em outubro'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "mes": {"type": "integer", "description": "Mês (1-12). Padrão: mês atual."},
                "ano": {"type": "integer", "description": "Ano (ex: 2026). Padrão: ano atual."},
                "apenas_pagos": {
                    "type": "boolean",
                    "description": (
                        "Se true, soma só o que já foi efetivamente pago no período (por data de "
                        "pagamento). Se false (padrão), soma tudo que vence no período, pago ou não."
                    ),
                },
            },
        },
    },
    {
        "name": "consultar_recebimentos",
        "description": (
            "Soma o total de contas a receber (entrada) em um mês/ano. Use para 'quanto vou "
            "receber esse mês' ou 'quanto recebi em setembro'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "mes": {"type": "integer", "description": "Mês (1-12). Padrão: mês atual."},
                "ano": {"type": "integer", "description": "Ano (ex: 2026). Padrão: ano atual."},
                "apenas_pagos": {
                    "type": "boolean",
                    "description": (
                        "Se true, soma só o que já foi efetivamente recebido no período (por data "
                        "de pagamento). Se false (padrão), soma tudo que vence no período, pago ou não."
                    ),
                },
            },
        },
    },
    {
        "name": "consultar_saldo_periodo",
        "description": (
            "Calcula o saldo (recebido - pago) de um mês/ano, considerando só o que já foi "
            "efetivamente baixado. Use para 'qual o saldo desse mês'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "mes": {"type": "integer", "description": "Mês (1-12). Padrão: mês atual."},
                "ano": {"type": "integer", "description": "Ano (ex: 2026). Padrão: ano atual."},
            },
        },
    },
    {
        "name": "consultar_notas_por_status",
        "description": (
            "Lista notas fiscais filtrando por status de conciliação e/ou tipo de operação. "
            "Use para 'quais notas estão pendentes de conciliação'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "enum": [s.value for s in StatusNota],
                    "description": "Status da nota fiscal. Omitir para todos os status.",
                },
                "tipo_operacao": {
                    "type": "string",
                    "enum": ["entrada", "saida"],
                    "description": "Filtra notas de entrada (compra) ou saída (venda). Omitir para ambos.",
                },
            },
        },
    },
]


def _periodo(mes: int | None, ano: int | None) -> tuple[date, date]:
    hoje = date.today()
    mes = mes or hoje.month
    ano = ano or hoje.year
    ultimo_dia = calendar.monthrange(ano, mes)[1]
    return date(ano, mes, 1), date(ano, mes, ultimo_dia)


def _conta_para_dict(conta: ContaFinanceira, parceiro: Parceiro | None) -> dict[str, Any]:
    return {
        "descricao": conta.descricao,
        "parceiro": parceiro.razao_social if parceiro else None,
        "valor": str(conta.valor),
        "data_vencimento": conta.data_vencimento.isoformat(),
        "status": conta.status.value,
        "tipo_operacao": conta.tipo_operacao.value,
    }


def consultar_vencimentos(db: Session, dias: int = 7, tipo_operacao: str | None = None) -> dict[str, Any]:
    hoje = date.today()
    fim = hoje + timedelta(days=max(dias, 0))
    query = (
        db.query(ContaFinanceira, Parceiro)
        .join(Parceiro, ContaFinanceira.parceiro_id == Parceiro.id)
        .filter(
            ContaFinanceira.status.in_([StatusConta.pendente, StatusConta.atrasado]),
            ContaFinanceira.data_vencimento <= fim,
        )
    )
    if tipo_operacao:
        query = query.filter(ContaFinanceira.tipo_operacao == TipoOperacaoNota(tipo_operacao))
    linhas = query.order_by(ContaFinanceira.data_vencimento).all()
    contas = [_conta_para_dict(conta, parceiro) for conta, parceiro in linhas]
    total = sum((conta.valor for conta, _ in linhas), Decimal("0"))
    return {"quantidade": len(contas), "total": str(total), "contas": contas}


def consultar_atrasados(db: Session, tipo_operacao: str | None = None) -> dict[str, Any]:
    query = (
        db.query(ContaFinanceira, Parceiro)
        .join(Parceiro, ContaFinanceira.parceiro_id == Parceiro.id)
        .filter(ContaFinanceira.status == StatusConta.atrasado)
    )
    if tipo_operacao:
        query = query.filter(ContaFinanceira.tipo_operacao == TipoOperacaoNota(tipo_operacao))
    linhas = query.order_by(ContaFinanceira.data_vencimento).all()
    contas = [_conta_para_dict(conta, parceiro) for conta, parceiro in linhas]
    total = sum((conta.valor for conta, _ in linhas), Decimal("0"))
    return {"quantidade": len(contas), "total": str(total), "contas": contas}


def _total_por_tipo(
    db: Session, tipo_operacao: TipoOperacaoNota, mes: int | None, ano: int | None, apenas_pagos: bool
) -> dict[str, Any]:
    inicio, fim = _periodo(mes, ano)
    filtros = [ContaFinanceira.tipo_operacao == tipo_operacao]
    if apenas_pagos:
        filtros += [
            ContaFinanceira.status == StatusConta.pago,
            ContaFinanceira.data_pagamento >= inicio,
            ContaFinanceira.data_pagamento <= fim,
        ]
        valor_coluna = ContaFinanceira.valor_pago
    else:
        filtros += [ContaFinanceira.data_vencimento >= inicio, ContaFinanceira.data_vencimento <= fim]
        valor_coluna = ContaFinanceira.valor

    total, quantidade = (
        db.query(func.coalesce(func.sum(valor_coluna), 0), func.count()).filter(*filtros).first()
    )
    return {
        "periodo": f"{inicio.isoformat()} a {fim.isoformat()}",
        "apenas_pagos": apenas_pagos,
        "quantidade": quantidade,
        "total": str(Decimal(total)),
    }


def consultar_total_gasto(
    db: Session, mes: int | None = None, ano: int | None = None, apenas_pagos: bool = False
) -> dict[str, Any]:
    return _total_por_tipo(db, TipoOperacaoNota.entrada, mes, ano, apenas_pagos)


def consultar_recebimentos(
    db: Session, mes: int | None = None, ano: int | None = None, apenas_pagos: bool = False
) -> dict[str, Any]:
    return _total_por_tipo(db, TipoOperacaoNota.saida, mes, ano, apenas_pagos)


def consultar_saldo_periodo(db: Session, mes: int | None = None, ano: int | None = None) -> dict[str, Any]:
    inicio, fim = _periodo(mes, ano)
    recebido = consultar_recebimentos(db, mes=mes, ano=ano, apenas_pagos=True)
    pago = consultar_total_gasto(db, mes=mes, ano=ano, apenas_pagos=True)
    saldo = Decimal(recebido["total"]) - Decimal(pago["total"])
    return {
        "periodo": f"{inicio.isoformat()} a {fim.isoformat()}",
        "total_recebido": recebido["total"],
        "total_pago": pago["total"],
        "saldo": str(saldo),
    }


def consultar_notas_por_status(
    db: Session, status: str | None = None, tipo_operacao: str | None = None
) -> dict[str, Any]:
    query = (
        db.query(NotaFiscal, Parceiro)
        .join(Parceiro, NotaFiscal.parceiro_id == Parceiro.id)
        .filter(Parceiro.cnpj_cpf != CNPJ_SENTINELA)
    )
    if status:
        query = query.filter(NotaFiscal.status == StatusNota(status))
    if tipo_operacao:
        query = query.filter(NotaFiscal.tipo_operacao == TipoOperacaoNota(tipo_operacao))
    linhas = query.order_by(NotaFiscal.data_emissao.desc()).limit(50).all()
    notas = [
        {
            "numero_nota": nota.numero_nota,
            "parceiro": parceiro.razao_social,
            "valor_total": str(nota.valor_total),
            "data_emissao": nota.data_emissao.isoformat(),
            "status": nota.status.value,
            "tipo_operacao": nota.tipo_operacao.value,
        }
        for nota, parceiro in linhas
    ]
    return {"quantidade": len(notas), "notas": notas}


_FUNCOES = {
    "consultar_vencimentos": consultar_vencimentos,
    "consultar_atrasados": consultar_atrasados,
    "consultar_total_gasto": consultar_total_gasto,
    "consultar_recebimentos": consultar_recebimentos,
    "consultar_saldo_periodo": consultar_saldo_periodo,
    "consultar_notas_por_status": consultar_notas_por_status,
}

# Reaproveitados pelo canal WhatsApp (mesmo motor de consulta, só entra um
# canal de entrada diferente + uma função de escrita — ver whatsapp_service).
FERRAMENTAS_LEITURA = _FERRAMENTAS
FUNCOES_LEITURA = _FUNCOES


class AssistenteIndisponivelError(Exception):
    """ANTHROPIC_API_KEY não configurada."""


class AssistenteConsultaService:
    def __init__(self) -> None:
        if not settings.anthropic_api_key:
            raise AssistenteIndisponivelError("ANTHROPIC_API_KEY não configurada")
        self._client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    def responder(self, pergunta: str, db: Session) -> str:
        mensagens: list[dict[str, Any]] = [{"role": "user", "content": pergunta}]

        for _ in range(_MAX_ITERACOES_TOOL_USE):
            resposta = self._client.messages.create(
                model=settings.anthropic_model,
                max_tokens=1024,
                system=_SYSTEM_PROMPT,
                tools=_FERRAMENTAS,
                messages=mensagens,
            )

            if resposta.stop_reason != "tool_use":
                return "".join(bloco.text for bloco in resposta.content if bloco.type == "text").strip()

            mensagens.append({"role": "assistant", "content": resposta.content})
            resultados_tool: list[dict[str, Any]] = []
            for bloco in resposta.content:
                if bloco.type != "tool_use":
                    continue
                funcao = _FUNCOES.get(bloco.name)
                if funcao is None:
                    conteudo = json.dumps({"erro": f"função desconhecida: {bloco.name}"})
                else:
                    resultado = funcao(db, **bloco.input)
                    conteudo = json.dumps(resultado, default=str, ensure_ascii=False)
                resultados_tool.append({"type": "tool_result", "tool_use_id": bloco.id, "content": conteudo})
            mensagens.append({"role": "user", "content": resultados_tool})

        return "Não consegui concluir a consulta — tente reformular a pergunta."
