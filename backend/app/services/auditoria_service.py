"""Log de auditoria — cobre toda ação que muda dado na aplicação (criação,
edição, exclusão). Guarda snapshot(s) do registro antes/depois; é o único
jeito de reconstruir o que mudou depois do fato, já que os registros em si
não guardam histórico próprio.
"""

import uuid
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from sqlalchemy import inspect
from sqlalchemy.orm import Session

from app.models.log_auditoria import LogAuditoria


def _serializar_valor(valor: Any) -> Any:
    if isinstance(valor, (uuid.UUID, Decimal)):
        return str(valor)
    if isinstance(valor, (date, datetime)):
        return valor.isoformat()
    if isinstance(valor, Enum):
        return valor.value
    return valor


def snapshot(instancia: Any, excluir: set[str] = frozenset()) -> dict[str, Any]:
    colunas = inspect(instancia).mapper.column_attrs
    return {
        coluna.key: _serializar_valor(getattr(instancia, coluna.key))
        for coluna in colunas
        if coluna.key not in excluir
    }


def _registrar(
    db: Session,
    usuario_id: uuid.UUID,
    acao: str,
    entidade: str,
    entidade_id: uuid.UUID,
    dados_antes: dict[str, Any] | None,
    dados_depois: dict[str, Any] | None,
) -> None:
    db.add(
        LogAuditoria(
            usuario_id=usuario_id,
            acao=acao,
            entidade=entidade,
            entidade_id=entidade_id,
            dados_antes=dados_antes,
            dados_depois=dados_depois,
        )
    )


def registrar_criacao(
    db: Session, usuario_id: uuid.UUID, entidade: str, instancia: Any, excluir: set[str] = frozenset()
) -> None:
    _registrar(
        db, usuario_id, "criacao", entidade, instancia.id, dados_antes=None, dados_depois=snapshot(instancia, excluir)
    )


def registrar_edicao(
    db: Session,
    usuario_id: uuid.UUID,
    entidade: str,
    antes: dict[str, Any],
    instancia_depois: Any,
    excluir: set[str] = frozenset(),
) -> None:
    _registrar(
        db,
        usuario_id,
        "edicao",
        entidade,
        instancia_depois.id,
        dados_antes=antes,
        dados_depois=snapshot(instancia_depois, excluir),
    )


def registrar_exclusao(
    db: Session, usuario_id: uuid.UUID, entidade: str, instancia: Any, excluir: set[str] = frozenset()
) -> None:
    _registrar(
        db, usuario_id, "exclusao", entidade, instancia.id, dados_antes=snapshot(instancia, excluir), dados_depois=None
    )
