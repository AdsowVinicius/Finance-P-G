import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class LogAuditoria(Base):
    """Trilha de auditoria de toda ação que muda dado na aplicação —
    criação, edição e exclusão. dados_antes/dados_depois guardam o snapshot
    do registro antes/depois da mudança (antes fica nulo numa criação,
    depois fica nulo numa exclusão) — é o único jeito de saber o que mudou,
    quem mudou e quando, já que os registros em si não guardam histórico.
    """

    __tablename__ = "logs_auditoria"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    usuario_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("usuarios.id"), nullable=False)
    acao: Mapped[str] = mapped_column(String(50), nullable=False)
    entidade: Mapped[str] = mapped_column(String(50), nullable=False)
    entidade_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    dados_antes: Mapped[dict | None] = mapped_column(JSONB)
    dados_depois: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
