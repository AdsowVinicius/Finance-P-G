import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class NfeSefazRecebida(Base):
    """Caixa de entrada de NFes emitidas contra o CNPJ do certificado
    (NFeDistribuicaoDFe). `chave_acesso` UNIQUE = idempotência: rebaixar o
    mesmo NSU nunca duplica. `tipo_documento`: 'resumo' (resNFe — só
    cabeçalho) ou 'completo' (procNFe — XML inteiro).
    """

    __tablename__ = "nfes_sefaz_recebidas"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    certificado_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("certificados_digitais.id"), nullable=False
    )
    nsu: Mapped[str] = mapped_column(String(15), nullable=False)
    chave_acesso: Mapped[str] = mapped_column(String(44), nullable=False, unique=True)
    cnpj_emitente: Mapped[str | None] = mapped_column(String(14))
    nome_emitente: Mapped[str | None] = mapped_column(String(255))
    valor_total: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    data_emissao: Mapped[date | None] = mapped_column(Date)
    tipo_documento: Mapped[str] = mapped_column(String(10), nullable=False)
    xml_bruto: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
