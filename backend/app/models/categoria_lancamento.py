import uuid
from datetime import datetime

from sqlalchemy import Boolean, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base
from app.models.enums import RegraDiaUtilCategoria
from app.models.pg_enums import regra_dia_util_categoria_pg


class CategoriaLancamento(Base):
    __tablename__ = "categorias_lancamento"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    nome: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    regra_dia_util: Mapped[RegraDiaUtilCategoria] = mapped_column(
        regra_dia_util_categoria_pg, nullable=False, default=RegraDiaUtilCategoria.bancaria
    )
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
