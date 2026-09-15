import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class OrcamentoCentroCustoUpsert(BaseModel):
    mes_referencia: date
    valor_planejado: Decimal = Field(ge=0)


class OrcamentoCentroCustoRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    centro_custo_id: uuid.UUID
    mes_referencia: date
    valor_planejado: Decimal
    updated_at: datetime


class PontoCurvaS(BaseModel):
    mes: str
    planejado_mes: Decimal
    realizado_mes: Decimal
    planejado_acumulado: Decimal
    realizado_acumulado: Decimal


class ResumoCentroCusto(BaseModel):
    despesas_realizadas: Decimal
    receitas_realizadas: Decimal
    saldo_realizado: Decimal
    despesas_futuras: Decimal
    receitas_futuras: Decimal
