import uuid
from datetime import datetime

from sqlalchemy import String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class MensagemWhatsappProcessada(Base):
    """Marca um wamid (id de mensagem do WhatsApp) já processado — idempotência
    contra reentrega de webhook da Cloud API, mesmo padrão de `chave_acesso`
    (notas fiscais) e `fitid` (extrato): identificador único externo,
    registrado antes de agir sobre a mensagem.
    """

    __tablename__ = "mensagens_whatsapp_processadas"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    wamid: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
