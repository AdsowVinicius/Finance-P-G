import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base
from app.models.enums import StatusNota, StatusProcessamentoNota, TipoNota, TipoOperacaoNota
from app.models.pg_enums import status_nota_pg, status_processamento_nota_pg, tipo_nota_pg, tipo_operacao_nota_pg


class NotaFiscal(Base):
    __tablename__ = "notas_fiscais"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    parceiro_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("parceiros.id"), nullable=False)
    centro_custo_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("centros_custo.id"))
    tipo: Mapped[TipoNota] = mapped_column(tipo_nota_pg, nullable=False)
    tipo_operacao: Mapped[TipoOperacaoNota] = mapped_column(
        tipo_operacao_nota_pg, nullable=False, default=TipoOperacaoNota.entrada
    )
    numero_nota: Mapped[str | None] = mapped_column(String(30))
    serie: Mapped[str | None] = mapped_column(String(10))
    chave_acesso: Mapped[str | None] = mapped_column(String(44), unique=True)
    valor_total: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    data_emissao: Mapped[date] = mapped_column(Date, nullable=False)

    despesa_fixa: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    despesa_parcelada: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    numero_parcelas: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")

    arquivo_xml_path: Mapped[str | None] = mapped_column(Text)
    arquivo_pdf_path: Mapped[str | None] = mapped_column(Text)
    dados_extraidos_xml: Mapped[dict | None] = mapped_column(JSONB)

    status: Mapped[StatusNota] = mapped_column(status_nota_pg, nullable=False, default=StatusNota.pendente)
    status_processamento: Mapped[StatusProcessamentoNota] = mapped_column(
        status_processamento_nota_pg, nullable=False, default=StatusProcessamentoNota.aguardando_extracao
    )
    criado_por: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("usuarios.id"))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
