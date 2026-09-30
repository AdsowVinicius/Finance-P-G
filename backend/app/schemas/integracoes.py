import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class CertificadoRead(BaseModel):
    """Nunca expõe arquivo nem senha (cifrados), só metadados."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    cnpj: str
    razao_social: str
    valido_de: datetime
    valido_ate: datetime
    ativo: bool
    uf_autor: int
    ult_nsu: str
    max_nsu: str | None
    ult_sincronizacao: datetime | None
    ult_mensagem_sefaz: str | None
    bloqueado_ate: datetime | None
    created_at: datetime


class CertificadoStatus(BaseModel):
    criptografia_configurada: bool
    ambiente: str
    certificado: CertificadoRead | None
    dias_para_vencer: int | None
    vencendo_em_breve: bool


class NfeSefazRecebidaRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    chave_acesso: str
    cnpj_emitente: str | None
    nome_emitente: str | None
    valor_total: Decimal | None
    data_emissao: date | None
    tipo_documento: str
    nota_cadastrada: bool = False
    created_at: datetime


class ConectarItemRequest(BaseModel):
    item_id: str = Field(min_length=1, max_length=100)


class ConexaoOpenFinanceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    provedor: str
    item_id: str
    conector_nome: str | None
    status: str | None
    created_at: datetime


class ConnectTokenRead(BaseModel):
    access_token: str


class ContaRemotaRead(BaseModel):
    id: str
    nome: str | None
    tipo: str | None
    subtipo: str | None
    numero: str | None
    saldo: Decimal | None


class VincularContaRequest(BaseModel):
    conexao_id: uuid.UUID
    open_finance_conta_id: str = Field(min_length=1, max_length=100)


class OpenFinanceStatus(BaseModel):
    configurado: bool
    conexoes: list[ConexaoOpenFinanceRead]
    contas_vinculadas: list["ContaVinculadaRead"]


class ContaVinculadaRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    apelido: str
    open_finance_conta_id: str
    open_finance_sincronizado_em: datetime | None


OpenFinanceStatus.model_rebuild()


class EnfileiradoRead(BaseModel):
    mensagem: str
