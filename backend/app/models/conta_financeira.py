import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base
from app.models.enums import FormaBaixa, StatusConta, TipoOperacaoNota
from app.models.pg_enums import forma_baixa_pg, status_conta_pg, tipo_operacao_nota_pg


class ContaFinanceira(Base):
    __tablename__ = "contas_financeiras"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    tipo_operacao: Mapped[TipoOperacaoNota] = mapped_column(tipo_operacao_nota_pg, nullable=False)

    lancamento_recorrente_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("lancamentos_recorrentes.id")
    )
    nota_fiscal_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("notas_fiscais.id"))
    parceiro_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("parceiros.id"), nullable=False)
    centro_custo_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("centros_custo.id"))

    descricao: Mapped[str] = mapped_column(String(200), nullable=False)
    numero_parcela: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    total_parcelas: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    valor: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)

    data_vencimento_original: Mapped[date] = mapped_column(Date, nullable=False)
    data_vencimento: Mapped[date] = mapped_column(Date, nullable=False)

    data_pagamento: Mapped[date | None] = mapped_column(Date)
    valor_pago: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    status: Mapped[StatusConta] = mapped_column(status_conta_pg, nullable=False, default=StatusConta.pendente)
    forma_baixa: Mapped[FormaBaixa | None] = mapped_column(forma_baixa_pg)

    boleto_linha_digitavel: Mapped[str | None] = mapped_column(String(60))
    boleto_codigo_barras: Mapped[str | None] = mapped_column(String(60))
    boleto_arquivo_path: Mapped[str | None] = mapped_column(Text)

    conta_bancaria_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("contas_bancarias.id"))
    criado_por: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("usuarios.id"))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
