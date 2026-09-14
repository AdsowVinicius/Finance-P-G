import uuid
from datetime import date, datetime

from sqlalchemy import Date, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base
from app.models.enums import FormatoExtrato, StatusImportacao
from app.models.pg_enums import formato_extrato_pg, status_importacao_pg


class ExtratoImportado(Base):
    __tablename__ = "extratos_importados"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    conta_bancaria_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contas_bancarias.id"), nullable=False
    )
    arquivo_original_path: Mapped[str] = mapped_column(Text, nullable=False)
    formato: Mapped[FormatoExtrato] = mapped_column(formato_extrato_pg, nullable=False)
    periodo_inicio: Mapped[date | None] = mapped_column(Date)
    periodo_fim: Mapped[date | None] = mapped_column(Date)
    status: Mapped[StatusImportacao] = mapped_column(
        status_importacao_pg, nullable=False, default=StatusImportacao.processando
    )
    mensagem_erro: Mapped[str | None] = mapped_column(Text)
    importado_por: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("usuarios.id"))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
