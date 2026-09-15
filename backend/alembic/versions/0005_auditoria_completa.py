"""Auditoria genérica (criação/edição/exclusão) — expande logs_auditoria

Antes só cobria exclusão (dados_antes NOT NULL). Agora também cobre criação
(dados_antes fica nulo, só dados_depois) e edição (os dois preenchidos, dá
pra comparar antes/depois).

Revision ID: 0005
Revises: 0004
Create Date: 2026-09-15

"""
from typing import Sequence, Union

from alembic import op

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE logs_auditoria ALTER COLUMN dados_antes DROP NOT NULL;
        ALTER TABLE logs_auditoria ADD COLUMN dados_depois JSONB;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE logs_auditoria DROP COLUMN IF EXISTS dados_depois;
        UPDATE logs_auditoria SET dados_antes = '{}'::jsonb WHERE dados_antes IS NULL;
        ALTER TABLE logs_auditoria ALTER COLUMN dados_antes SET NOT NULL;
        """
    )
