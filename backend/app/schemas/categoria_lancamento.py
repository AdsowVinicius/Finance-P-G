import uuid

from pydantic import BaseModel, ConfigDict

from app.models.enums import RegraDiaUtilCategoria


class CategoriaLancamentoBase(BaseModel):
    nome: str
    regra_dia_util: RegraDiaUtilCategoria


class CategoriaLancamentoCreate(CategoriaLancamentoBase):
    pass


class CategoriaLancamentoRead(CategoriaLancamentoBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    ativo: bool
