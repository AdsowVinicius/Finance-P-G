import uuid
from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, LargeBinary, SmallInteger, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class CertificadoDigital(Base):
    """Certificado A1 cadastrado. `arquivo_cifrado` e `senha_cifrada` estão
    cifrados com Fernet (CERT_ENCRYPTION_KEY) — nunca em texto puro, nunca
    no STORAGE_DIR (que é servido publicamente em /storage).
    """

    __tablename__ = "certificados_digitais"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    cnpj: Mapped[str] = mapped_column(String(14), nullable=False)
    razao_social: Mapped[str] = mapped_column(String(255), nullable=False)
    arquivo_cifrado: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    senha_cifrada: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    fingerprint_sha256: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    valido_de: Mapped[datetime] = mapped_column(nullable=False)
    valido_ate: Mapped[datetime] = mapped_column(nullable=False)
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")

    uf_autor: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=35, server_default="35")  # cUFAutor (35=SP)
    ult_nsu: Mapped[str] = mapped_column(String(15), nullable=False, default="0", server_default="0")
    max_nsu: Mapped[str | None] = mapped_column(String(15))
    ult_sincronizacao: Mapped[datetime | None] = mapped_column()
    ult_mensagem_sefaz: Mapped[str | None] = mapped_column(Text)
    bloqueado_ate: Mapped[datetime | None] = mapped_column()  # cStat 656: SEFAZ pede pra esperar 1h

    criado_por: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("usuarios.id"))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
