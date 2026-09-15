"""Log de auditoria para ações destrutivas (exclusão definitiva)

Extensão de escopo pedida pelo usuário: exclusões (admin-only, irreversíveis)
precisam ficar registradas — quem, quando, o quê exatamente foi removido
(snapshot completo antes de apagar). Cobre só exclusões por enquanto; outras
ações já têm rastro parcial (criado_por, confirmado_por em conciliacoes).

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-15

"""
from typing import Sequence, Union

from alembic import op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE logs_auditoria (
            id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            usuario_id      UUID NOT NULL REFERENCES usuarios(id),
            acao            VARCHAR(50) NOT NULL,
            entidade        VARCHAR(50) NOT NULL,
            entidade_id     UUID NOT NULL,
            dados_antes     JSONB NOT NULL,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
        );

        CREATE INDEX idx_logs_auditoria_entidade ON logs_auditoria(entidade, entidade_id);
        CREATE INDEX idx_logs_auditoria_usuario ON logs_auditoria(usuario_id);
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS logs_auditoria CASCADE;")
