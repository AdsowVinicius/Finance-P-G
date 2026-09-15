"""Categorias de lançamento (regra de dia útil por categoria)

Pedido do usuário: um jeito de marcar se um lançamento é "pagamento de
funcionário" (sábado conta como dia útil) ou "conta de banco" (só seg-sex,
cai no fim de semana empurra pra sexta anterior — ao contrário do padrão
DiaUtilCalculator.proximo_dia_util, que empurra pra frente). Categoria é
opcional: lançamento sem categoria continua no comportamento padrão de
sempre (proximo_dia_util, sem mudança nenhuma).

Revision ID: 0006
Revises: 0005
Create Date: 2026-09-15

"""
from typing import Sequence, Union

from alembic import op

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TYPE regra_dia_util_categoria AS ENUM ('funcionario', 'bancaria');

        CREATE TABLE categorias_lancamento (
            id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            nome           VARCHAR(80) NOT NULL UNIQUE,
            regra_dia_util regra_dia_util_categoria NOT NULL DEFAULT 'bancaria',
            ativo          BOOLEAN NOT NULL DEFAULT true,
            created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
        );

        ALTER TABLE contas_financeiras ADD COLUMN categoria_id UUID REFERENCES categorias_lancamento(id);
        ALTER TABLE lancamentos_recorrentes ADD COLUMN categoria_id UUID REFERENCES categorias_lancamento(id);

        CREATE INDEX idx_contas_financeiras_categoria ON contas_financeiras(categoria_id);
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP INDEX IF EXISTS idx_contas_financeiras_categoria;
        ALTER TABLE lancamentos_recorrentes DROP COLUMN IF EXISTS categoria_id;
        ALTER TABLE contas_financeiras DROP COLUMN IF EXISTS categoria_id;
        DROP TABLE IF EXISTS categorias_lancamento CASCADE;
        DROP TYPE IF EXISTS regra_dia_util_categoria CASCADE;
        """
    )
