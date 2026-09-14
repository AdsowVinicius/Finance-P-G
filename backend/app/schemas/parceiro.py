import uuid

from pydantic import BaseModel, ConfigDict

from app.models.enums import TipoParceiro


class ParceiroBase(BaseModel):
    tipo: TipoParceiro = TipoParceiro.fornecedor
    cnpj_cpf: str | None = None
    razao_social: str
    nome_fantasia: str | None = None
    email: str | None = None
    telefone: str | None = None


class ParceiroCreate(ParceiroBase):
    pass


class ParceiroUpdate(BaseModel):
    tipo: TipoParceiro | None = None
    cnpj_cpf: str | None = None
    razao_social: str | None = None
    nome_fantasia: str | None = None
    email: str | None = None
    telefone: str | None = None
    ativo: bool | None = None


class ParceiroRead(ParceiroBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    ativo: bool
