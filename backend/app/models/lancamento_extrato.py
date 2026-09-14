import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base
from app.models.enums import StatusConciliacaoLinha, TipoLancamentoExtrato
from app.models.pg_enums import status_conciliacao_linha_pg, tipo_lancamento_extrato_pg


class LancamentoExtrato(Base):
    __tablename__ = "lancamentos_extrato"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    extrato_importado_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("extratos_importados.id"), nullable=False
    )
    conta_bancaria_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contas_bancarias.id"), nullable=False
    )

    data: Mapped[date] = mapped_column(Date, nullable=False)
    descricao: Mapped[str | None] = mapped_column(Text)
    valor: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    tipo: Mapped[TipoLancamentoExtrato] = mapped_column(tipo_lancamento_extrato_pg, nullable=False)
    fitid: Mapped[str | None] = mapped_column(String(100))

    status_conciliacao: Mapped[StatusConciliacaoLinha] = mapped_column(
        status_conciliacao_linha_pg, nullable=False, default=StatusConciliacaoLinha.pendente
    )
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
