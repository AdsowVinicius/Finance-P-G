import uuid
from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import Periodicidade, TipoOperacaoNota


class LancamentoRecorrenteCreate(BaseModel):
    tipo_operacao: TipoOperacaoNota
    descricao: str
    parceiro_id: uuid.UUID
    centro_custo_id: uuid.UUID
    conta_bancaria_id: uuid.UUID | None = None

    valor_parcela: Decimal = Field(gt=0)
    numero_ocorrencias: int | None = Field(default=None, ge=1)
    data_fim: date | None = None

    periodicidade: Periodicidade
    intervalo_dias: int | None = Field(default=None, gt=0)
    data_inicio: date

    @model_validator(mode="after")
    def _valida_condicao_de_parada(self) -> "LancamentoRecorrenteCreate":
        if self.numero_ocorrencias is None and self.data_fim is None:
            raise ValueError("informe numero_ocorrencias e/ou data_fim")
        if self.periodicidade == Periodicidade.personalizada_dias and not self.intervalo_dias:
            raise ValueError("periodicidade 'personalizada_dias' exige intervalo_dias")
        return self


class LancamentoRecorrenteRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tipo_operacao: TipoOperacaoNota
    descricao: str
    parceiro_id: uuid.UUID | None
    centro_custo_id: uuid.UUID | None
    conta_bancaria_id: uuid.UUID | None
    valor_parcela: Decimal
    numero_ocorrencias: int | None
    data_fim: date | None
    periodicidade: Periodicidade
    intervalo_dias: int | None
    data_inicio: date
    ativo: bool
