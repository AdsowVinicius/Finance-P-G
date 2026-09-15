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


class NotaFiscalCompletar(BaseModel):
    """Completa campos que a captura não preencheu — sobretudo notas
    chegadas por WhatsApp (RF16), que nunca têm centro de custo (só existe
    no app) e, quando a foto/PDF não tinha chave de acesso legível, também
    não têm parceiro/valor/data reais ainda (parceiro sentinela até aqui).
    """

    centro_custo_id: uuid.UUID | None = None
    parceiro_id: uuid.UUID | None = None
    valor_total: Decimal | None = Field(default=None, gt=0)
    data_emissao: date | None = None
    numero_nota: str | None = None
    serie: str | None = None
