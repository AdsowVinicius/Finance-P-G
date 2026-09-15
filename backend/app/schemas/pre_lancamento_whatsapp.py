import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import FormaPagamento, StatusPreLancamentoWhatsapp, TipoOperacaoNota


class PreLancamentoWhatsappRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    telefone: str
    usuario_id: uuid.UUID | None
    mensagem_original: str
    tipo_operacao: TipoOperacaoNota
    valor: Decimal | None
    descricao: str | None
    fornecedor_texto: str | None
    forma_pagamento: FormaPagamento | None
    parceiro_id: uuid.UUID | None
    centro_custo_id: uuid.UUID | None
    conta_financeira_id: uuid.UUID | None
    status: StatusPreLancamentoWhatsapp
    created_at: datetime


class ConfirmarPreLancamento(BaseModel):
    parceiro_id: uuid.UUID
    centro_custo_id: uuid.UUID
    valor: Decimal = Field(gt=0)
    descricao: str = Field(min_length=1, max_length=200)
    data_vencimento: date
    forma_pagamento: FormaPagamento | None = None
    conta_bancaria_id: uuid.UUID | None = None


class VincularTelefoneWhatsapp(BaseModel):
    telefone_whatsapp: str = Field(min_length=10, max_length=20, pattern=r"^\d+$")
