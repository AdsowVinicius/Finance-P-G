import uuid
from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import FormaBaixa, FormaPagamento, StatusConta, TipoOperacaoNota


class ContaFinanceiraCreate(BaseModel):
    """Lançamento manual avulso (sem nota fiscal nem recorrência)."""

    tipo_operacao: TipoOperacaoNota
    parceiro_id: uuid.UUID
    centro_custo_id: uuid.UUID
    categoria_id: uuid.UUID | None = None
    descricao: str
    valor: Decimal = Field(gt=0)
    data_vencimento: date
    conta_bancaria_id: uuid.UUID | None = None
    forma_pagamento: FormaPagamento | None = None


class ContaFinanceiraBaixa(BaseModel):
    data_pagamento: date
    valor_pago: Decimal = Field(gt=0)
    forma_pagamento: FormaPagamento | None = None
    conta_bancaria_id: uuid.UUID | None = None


class ContaFinanceiraRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tipo_operacao: TipoOperacaoNota
    lancamento_recorrente_id: uuid.UUID | None
    nota_fiscal_id: uuid.UUID | None
    parceiro_id: uuid.UUID
    centro_custo_id: uuid.UUID | None
    categoria_id: uuid.UUID | None
    descricao: str
    numero_parcela: int
    total_parcelas: int
    valor: Decimal
    data_vencimento_original: date
    data_vencimento: date
    data_pagamento: date | None
    valor_pago: Decimal | None
    juros_pago: Decimal | None
    status: StatusConta
    forma_baixa: FormaBaixa | None
    forma_pagamento: FormaPagamento | None
    boleto_linha_digitavel: str | None
    boleto_codigo_barras: str | None
    boleto_arquivo_path: str | None
    conta_bancaria_id: uuid.UUID | None


class DashboardVencimentoResponse(BaseModel):
    atrasado: list[ContaFinanceiraRead]
    hoje: list[ContaFinanceiraRead]
    semana: list[ContaFinanceiraRead]
    total_atrasado: Decimal
    total_hoje: Decimal
    total_semana: Decimal
