import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base
from app.models.enums import StatusPreLancamentoWhatsapp, TipoOperacaoNota
from app.models.pg_enums import status_pre_lancamento_whatsapp_pg, tipo_operacao_nota_pg


class PreLancamentoWhatsapp(Base):
    """RF do roadmap: lançamento informal via WhatsApp, pendente de revisão
    do financeiro antes de virar uma ContaFinanceira de verdade — falta
    centro de custo (obrigatório) e confirmação do fornecedor.
    """

    __tablename__ = "pre_lancamentos_whatsapp"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    telefone: Mapped[str] = mapped_column(String(20), nullable=False)
    usuario_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("usuarios.id"))

    mensagem_original: Mapped[str] = mapped_column(Text, nullable=False)
    tipo_operacao: Mapped[TipoOperacaoNota] = mapped_column(tipo_operacao_nota_pg, nullable=False)
    valor: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    descricao: Mapped[str | None] = mapped_column(String(200))
    fornecedor_texto: Mapped[str | None] = mapped_column(String(200))

    parceiro_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("parceiros.id"))
    centro_custo_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("centros_custo.id"))
    conta_financeira_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contas_financeiras.id")
    )

    status: Mapped[StatusPreLancamentoWhatsapp] = mapped_column(
        status_pre_lancamento_whatsapp_pg, nullable=False, default=StatusPreLancamentoWhatsapp.pendente_revisao
    )
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
