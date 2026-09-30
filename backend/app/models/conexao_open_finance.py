import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class ConexaoOpenFinance(Base):
    """Uma conexão (item) com um banco no agregador — hoje só 'pluggy'.
    O consentimento do usuário acontece no widget do provedor; aqui só
    guardamos o id do item pra listar contas e sincronizar transações.
    """

    __tablename__ = "conexoes_open_finance"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    provedor: Mapped[str] = mapped_column(String(30), nullable=False, default="pluggy", server_default="pluggy")
    item_id: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    conector_nome: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[str | None] = mapped_column(String(40))
    criado_por: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("usuarios.id"))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
