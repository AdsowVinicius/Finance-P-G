import uuid
from datetime import date, datetime

from sqlalchemy import Date, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base
from app.models.enums import StatusProjeto
from app.models.pg_enums import status_projeto_pg

# Mapeamento mínimo — só pra resolver a FK de lancamentos_recorrentes.projeto_id.
# Funcionários/projetos estão fora do MVP atual (ver CLAUDE.md); sem router/schema
# próprios ainda.


class Projeto(Base):
    __tablename__ = "projetos"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    nome: Mapped[str] = mapped_column(String(200), nullable=False)
    cliente_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("parceiros.id"))
    data_inicio: Mapped[date | None] = mapped_column(Date)
    data_fim_previsto: Mapped[date | None] = mapped_column(Date)
    status: Mapped[StatusProjeto] = mapped_column(status_projeto_pg, nullable=False, default=StatusProjeto.ativo)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
