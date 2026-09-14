import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, ForeignKey, Numeric
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base
from app.models.enums import TipoMatch
from app.models.pg_enums import tipo_match_pg


class Conciliacao(Base):
    __tablename__ = "conciliacoes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    lancamento_extrato_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("lancamentos_extrato.id"), nullable=False
    )
    conta_financeira_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("contas_financeiras.id"))
    nota_fiscal_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("notas_fiscais.id"))

    valor_conciliado: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    tipo_match: Mapped[TipoMatch] = mapped_column(tipo_match_pg, nullable=False)

    confirmado_por: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("usuarios.id"))
    confirmado_em: Mapped[datetime | None]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)

    __table_args__ = (
        CheckConstraint(
            "conta_financeira_id IS NOT NULL OR nota_fiscal_id IS NOT NULL", name="chk_conciliacao_tem_destino"
        ),
    )
