import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class LogAuditoriaRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    usuario_id: uuid.UUID
    acao: str
    entidade: str
    entidade_id: uuid.UUID
    dados_antes: dict[str, Any]
    created_at: datetime
