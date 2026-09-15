"""Relaxa chk_data_vencimento_ajustada pra permitir deslocamento pra trás

A constraint original (schema.sql) assumia data_vencimento >= data_vencimento_original
porque o único ajuste que existia (proximo_dia_util) só empurra pra frente.
A regra "bancária" nova (categorias_lancamento, migration 0006) empurra pra
trás quando cai no fim de semana — até a sexta-feira anterior, no máximo
2 dias antes da data original (sábado -1, domingo -2). Troca o >= simples
por uma tolerância de 2 dias pra trás, mantendo a constraint como guarda
contra ajuste errado (ex: bug que jogasse a data meses de diferença).

Revision ID: 0007
Revises: 0006
Create Date: 2026-09-15

"""
from typing import Sequence, Union

from alembic import op

revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE contas_financeiras DROP CONSTRAINT chk_data_vencimento_ajustada;
        ALTER TABLE contas_financeiras ADD CONSTRAINT chk_data_vencimento_ajustada
            CHECK (data_vencimento >= data_vencimento_original - INTERVAL '2 days');
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE contas_financeiras DROP CONSTRAINT chk_data_vencimento_ajustada;
        ALTER TABLE contas_financeiras ADD CONSTRAINT chk_data_vencimento_ajustada
            CHECK (data_vencimento >= data_vencimento_original);
        """
    )
