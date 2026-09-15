"""Lançamento e consulta via WhatsApp — reaproveita o motor de linguagem
natural do RF16 (mesmas funções de consulta somente-leitura) e adiciona uma
função de escrita (criar_pre_lancamento), que nunca grava direto em
contas_financeiras: sempre cria um registro pendente de revisão do
financeiro, porque falta centro de custo (obrigatório) e confirmação do
fornecedor.
"""

import json
from decimal import Decimal
from typing import Any

import anthropic
from sqlalchemy.orm import Session

from app.config import settings
from app.models.enums import TipoOperacaoNota
from app.models.pre_lancamento_whatsapp import PreLancamentoWhatsapp
from app.models.usuario import Usuario
from app.services.assistente_consulta_service import FERRAMENTAS_LEITURA, FUNCOES_LEITURA

_MAX_ITERACOES_TOOL_USE = 4

_SYSTEM_PROMPT = (
    "Você é o assistente financeiro da P&G Engenharia, respondendo por WhatsApp. Pode responder "
    "consultas (vencimentos, gastos, recebimentos, notas fiscais) usando as funções de consulta "
    "disponíveis, e também registrar uma despesa ou receita informal relatada em linguagem natural "
    "usando criar_pre_lancamento — nunca invente números, use sempre as funções. Depois de registrar "
    "um pré-lançamento, avise que ele fica pendente de revisão do financeiro antes de virar um "
    "lançamento de verdade. Responda em português, curto e direto (é WhatsApp, não e-mail), sem "
    "markdown (sem **negrito**, sem #), citando valores como R$ com duas casas decimais."
)

_FERRAMENTA_CRIAR_PRE_LANCAMENTO = {
    "name": "criar_pre_lancamento",
    "description": (
        "Registra uma despesa ou receita informal (sem nota fiscal) relatada em linguagem natural, "
        "como pré-lançamento PENDENTE DE REVISÃO — nunca lança direto na conta a pagar/receber, "
        "porque falta centro de custo (obrigatório) e confirmação do fornecedor. Use quando a "
        "mensagem for algo como 'gastei 20 reais na padaria' ou 'recebi 500 do cliente X', nunca "
        "para perguntas de consulta."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "tipo_operacao": {
                "type": "string",
                "enum": ["entrada", "saida"],
                "description": "saida = despesa (paguei/gastei), entrada = receita (recebi).",
            },
            "valor": {"type": "number", "description": "Valor em reais, ex: 20.00"},
            "descricao": {
                "type": "string",
                "description": "Descrição curta do que foi comprado/recebido, ex: 'Padaria do seu Zé'.",
            },
            "fornecedor_texto": {
                "type": "string",
                "description": "Nome do fornecedor/cliente mencionado, se houver.",
            },
        },
        "required": ["tipo_operacao", "valor", "descricao"],
    },
}


def _criar_pre_lancamento(
    db: Session,
    *,
    telefone: str,
    usuario_id: Any,
    mensagem_original: str,
    tipo_operacao: str,
    valor: float,
    descricao: str,
    fornecedor_texto: str | None = None,
) -> dict[str, Any]:
    pre = PreLancamentoWhatsapp(
        telefone=telefone,
        usuario_id=usuario_id,
        mensagem_original=mensagem_original,
        tipo_operacao=TipoOperacaoNota(tipo_operacao),
        valor=Decimal(str(valor)),
        descricao=descricao,
        fornecedor_texto=fornecedor_texto,
    )
    db.add(pre)
    db.commit()
    db.refresh(pre)
    return {
        "pre_lancamento_id": str(pre.id),
        "status": "pendente_revisao",
        "mensagem": "Registrado como pendente de revisão do financeiro.",
    }


class WhatsappIndisponivelError(Exception):
    """ANTHROPIC_API_KEY não configurada."""


def processar_mensagem(telefone: str, texto: str, db: Session) -> str:
    usuario = db.query(Usuario).filter(Usuario.telefone_whatsapp == telefone).first()
    if usuario is None:
        return (
            "Esse número ainda não está vinculado a um usuário do Finance P&G. "
            "Peça pra um admin vincular seu WhatsApp no sistema antes de usar o assistente por aqui."
        )

    if not settings.anthropic_api_key:
        raise WhatsappIndisponivelError("ANTHROPIC_API_KEY não configurada")
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    ferramentas = [*FERRAMENTAS_LEITURA, _FERRAMENTA_CRIAR_PRE_LANCAMENTO]
    mensagens: list[dict[str, Any]] = [{"role": "user", "content": texto}]

    for _ in range(_MAX_ITERACOES_TOOL_USE):
        resposta = client.messages.create(
            model=settings.anthropic_model,
            max_tokens=1024,
            system=_SYSTEM_PROMPT,
            tools=ferramentas,
            messages=mensagens,
        )

        if resposta.stop_reason != "tool_use":
            return "".join(bloco.text for bloco in resposta.content if bloco.type == "text").strip()

        mensagens.append({"role": "assistant", "content": resposta.content})
        resultados_tool: list[dict[str, Any]] = []
        for bloco in resposta.content:
            if bloco.type != "tool_use":
                continue
            if bloco.name == "criar_pre_lancamento":
                resultado = _criar_pre_lancamento(
                    db,
                    telefone=telefone,
                    usuario_id=usuario.id,
                    mensagem_original=texto,
                    **bloco.input,
                )
            else:
                funcao = FUNCOES_LEITURA.get(bloco.name)
                resultado = (
                    funcao(db, **bloco.input) if funcao else {"erro": f"função desconhecida: {bloco.name}"}
                )
            resultados_tool.append(
                {"type": "tool_result", "tool_use_id": bloco.id, "content": json.dumps(resultado, default=str, ensure_ascii=False)}
            )
        mensagens.append({"role": "user", "content": resultados_tool})

    return "Não consegui concluir isso — tente reformular a mensagem."
