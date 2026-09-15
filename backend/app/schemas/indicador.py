import uuid
from datetime import date
from decimal import Decimal

from pydantic import BaseModel


class ResumoIndicadores(BaseModel):
    saldo_mes: Decimal
    total_a_pagar_aberto: Decimal
    total_a_receber_aberto: Decimal
    contas_atrasadas_qtd: int
    contas_atrasadas_total: Decimal
    juros_pagos_mes: Decimal


class PontoEvolucaoMensal(BaseModel):
    mes: str
    total_pago: Decimal
    total_recebido: Decimal


class ItemCentroCusto(BaseModel):
    centro_custo_id: uuid.UUID
    centro_custo: str
    total: Decimal


class ItemStatusNota(BaseModel):
    status: str
    quantidade: int


class ItemGastoPrevistoDia(BaseModel):
    data: date
    total: Decimal
