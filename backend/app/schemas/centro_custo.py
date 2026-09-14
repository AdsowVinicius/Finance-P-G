import uuid

from pydantic import BaseModel, ConfigDict


class CentroCustoBase(BaseModel):
    codigo: str | None = None
    nome: str


class CentroCustoCreate(CentroCustoBase):
    pass


class CentroCustoUpdate(BaseModel):
    codigo: str | None = None
    nome: str | None = None
    ativo: bool | None = None


class CentroCustoRead(CentroCustoBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    ativo: bool
