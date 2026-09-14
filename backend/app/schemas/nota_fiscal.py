import uuid
from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import StatusNota, StatusProcessamentoNota, TipoNota, TipoOperacaoNota


class NotaFiscalRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    parceiro_id: uuid.UUID
    centro_custo_id: uuid.UUID | None
    tipo: TipoNota
    tipo_operacao: TipoOperacaoNota
    numero_nota: str | None
    serie: str | None
    chave_acesso: str | None
    valor_total: Decimal
    data_emissao: date
    despesa_fixa: bool
    despesa_parcelada: bool
    numero_parcelas: int
    arquivo_xml_path: str | None
    arquivo_pdf_path: str | None
    status: StatusNota
    status_processamento: StatusProcessamentoNota


class ChaveAcessoManual(BaseModel):
    chave_acesso: str = Field(min_length=44, max_length=44, pattern=r"^\d{44}$")
