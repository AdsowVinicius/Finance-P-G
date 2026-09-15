"""Log de auditoria — só para ações destrutivas (exclusão definitiva), onde
não sobra nenhum outro jeito de saber o que existia depois do fato. Guarda
um snapshot completo do registro antes de apagar.
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


def snapshot(instancia: Any) -> dict[str, Any]:
    colunas = inspect(instancia).mapper.column_attrs
    return {coluna.key: _serializar_valor(getattr(instancia, coluna.key)) for coluna in colunas}


def registrar_exclusao(
    db: Session, usuario_id: uuid.UUID, entidade: str, entidade_id: uuid.UUID, dados_antes: dict[str, Any]
) -> None:
    db.add(
        LogAuditoria(
            usuario_id=usuario_id,
            acao="exclusao",
            entidade=entidade,
            entidade_id=entidade_id,
            dados_antes=dados_antes,
        )
    )
