import uuid
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class ContaBancariaBase(BaseModel):
    apelido: str
    banco: str | None = None
    agencia: str | None = None
    numero_conta: str | None = None
    tipo_conta: str | None = None
    saldo_inicial: Decimal = Decimal("0")


class ContaBancariaCreate(ContaBancariaBase):
    pass


class ContaBancariaUpdate(BaseModel):
    apelido: str | None = None
    banco: str | None = None
    agencia: str | None = None
    numero_conta: str | None = None
    tipo_conta: str | None = None
    saldo_inicial: Decimal | None = None
    ativo: bool | None = None


class ContaBancariaRead(ContaBancariaBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    ativo: bool
