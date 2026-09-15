import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, ForeignKey, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base
from app.models.enums import Periodicidade, TipoOperacaoNota
from app.models.pg_enums import periodicidade_pg, tipo_operacao_nota_pg


class LancamentoRecorrente(Base):
    __tablename__ = "lancamentos_recorrentes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    tipo_operacao: Mapped[TipoOperacaoNota] = mapped_column(tipo_operacao_nota_pg, nullable=False)
    descricao: Mapped[str] = mapped_column(String(200), nullable=False)
    parceiro_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("parceiros.id"))
    centro_custo_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("centros_custo.id"))
    categoria_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("categorias_lancamento.id"))
    nota_fiscal_origem_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("notas_fiscais.id"))
    projeto_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("projetos.id"))

    valor_parcela: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)

    numero_ocorrencias: Mapped[int | None] = mapped_column(Integer)
    data_fim: Mapped[date | None] = mapped_column(Date)

    periodicidade: Mapped[Periodicidade] = mapped_column(periodicidade_pg, nullable=False)
    intervalo_dias: Mapped[int | None] = mapped_column(Integer)
    data_inicio: Mapped[date] = mapped_column(Date, nullable=False)

    conta_bancaria_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("contas_bancarias.id"))
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    criado_por: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("usuarios.id"))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
