import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class ContaBancaria(Base):
    __tablename__ = "contas_bancarias"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    apelido: Mapped[str] = mapped_column(String(100), nullable=False)
    banco: Mapped[str | None] = mapped_column(String(100))
    agencia: Mapped[str | None] = mapped_column(String(20))
    numero_conta: Mapped[str | None] = mapped_column(String(30))
    tipo_conta: Mapped[str | None] = mapped_column(String(30))
    saldo_inicial: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=Decimal("0"))
    # Open Finance: conta remota do agregador vinculada a esta conta
    conexao_open_finance_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conexoes_open_finance.id")
    )
    open_finance_conta_id: Mapped[str | None] = mapped_column(String(100), unique=True)
    open_finance_sincronizado_em: Mapped[datetime | None] = mapped_column()
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
