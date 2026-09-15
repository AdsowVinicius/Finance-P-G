import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import FormatoExtrato, StatusConciliacaoLinha, StatusImportacao, TipoLancamentoExtrato, TipoMatch


class ExtratoImportadoRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    conta_bancaria_id: uuid.UUID
    formato: FormatoExtrato
    status: StatusImportacao
    mensagem_erro: str | None
    created_at: datetime


class LancamentoExtratoRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    extrato_importado_id: uuid.UUID
    conta_bancaria_id: uuid.UUID
    data: date
    descricao: str | None
    valor: Decimal
    tipo: TipoLancamentoExtrato
    fitid: str | None
    status_conciliacao: StatusConciliacaoLinha


class ConciliacaoRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    lancamento_extrato_id: uuid.UUID
    conta_financeira_id: uuid.UUID | None
    nota_fiscal_id: uuid.UUID | None
    valor_conciliado: Decimal
    tipo_match: TipoMatch


class ConciliarManualRequest(BaseModel):
    contas_financeira_ids: list[uuid.UUID] = Field(min_length=1)
