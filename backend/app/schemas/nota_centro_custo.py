import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class NotaCentroCustoCreate(BaseModel):
    texto: str = Field(min_length=1, max_length=2000)


class NotaCentroCustoRead(BaseModel):
    id: uuid.UUID
    centro_custo_id: uuid.UUID
    usuario_id: uuid.UUID
    usuario_nome: str
    texto: str
    created_at: datetime
