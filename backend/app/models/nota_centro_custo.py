import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class NotaCentroCusto(Base):
    """Nota/anotação livre num centro de custo (obra) — painel colaborativo,
    qualquer usuário com acesso de escrita pode adicionar, todos veem.
    """

    __tablename__ = "notas_centro_custo"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    centro_custo_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("centros_custo.id"), nullable=False)
    usuario_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("usuarios.id"), nullable=False)
    texto: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
