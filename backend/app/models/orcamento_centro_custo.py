import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Numeric
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class OrcamentoCentroCusto(Base):
    """Valor planejado por mês pra um centro de custo/obra — usado pra
    comparar planejado x realizado na Curva S (análise por centro de custo).
    """

    __tablename__ = "orcamentos_centro_custo"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    centro_custo_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("centros_custo.id"), nullable=False)
    mes_referencia: Mapped[date] = mapped_column(Date, nullable=False)
    valor_planejado: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
