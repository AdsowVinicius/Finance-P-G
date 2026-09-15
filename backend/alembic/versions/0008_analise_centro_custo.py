"""Orçamento e notas por centro de custo (análise por obra)

Pedido do usuário: uma área de análise por centro de custo/obra com Curva S
(planejado x realizado) e um painel de notas colaborativo visível pra todos.
Curva S precisa de um valor planejado por mês, que não existia em lugar
nenhum — daí orcamentos_centro_custo. notas_centro_custo é só texto livre
associado a um centro de custo e a quem escreveu.

Revision ID: 0008
Revises: 0007
Create Date: 2026-09-15

"""
from typing import Sequence, Union

from alembic import op

revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE orcamentos_centro_custo (
            id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            centro_custo_id UUID NOT NULL REFERENCES centros_custo(id),
            mes_referencia  DATE NOT NULL,
            valor_planejado NUMERIC(14,2) NOT NULL,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE (centro_custo_id, mes_referencia)
        );
        CREATE INDEX idx_orcamentos_centro_custo_centro ON orcamentos_centro_custo(centro_custo_id);

        CREATE TABLE notas_centro_custo (
            id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            centro_custo_id UUID NOT NULL REFERENCES centros_custo(id),
            usuario_id      UUID NOT NULL REFERENCES usuarios(id),
            texto           TEXT NOT NULL,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE INDEX idx_notas_centro_custo_centro ON notas_centro_custo(centro_custo_id);
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP TABLE IF EXISTS notas_centro_custo CASCADE;
        DROP INDEX IF EXISTS idx_orcamentos_centro_custo_centro;
        DROP TABLE IF EXISTS orcamentos_centro_custo CASCADE;
        """
    )
