"""WhatsApp: vínculo de telefone ao usuário + pré-lançamentos pendentes de revisão

Extensão de escopo pedida pelo usuário (fora do schema.sql original, que
segue fechado e intocado) — lançamento/consulta via WhatsApp reaproveitando
o motor do RF16, com uma função de escrita nova (criar_pre_lancamento).

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-15

"""
from typing import Sequence, Union

from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE usuarios ADD COLUMN telefone_whatsapp VARCHAR(20) UNIQUE;

        CREATE TYPE status_pre_lancamento_whatsapp AS ENUM ('pendente_revisao', 'confirmado', 'descartado');

        CREATE TABLE pre_lancamentos_whatsapp (
            id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            telefone            VARCHAR(20) NOT NULL,
            usuario_id          UUID REFERENCES usuarios(id),
            mensagem_original   TEXT NOT NULL,
            tipo_operacao       tipo_operacao_nota NOT NULL,
            valor               NUMERIC(14,2),
            descricao           VARCHAR(200),
            fornecedor_texto    VARCHAR(200),
            parceiro_id         UUID REFERENCES parceiros(id),
            centro_custo_id     UUID REFERENCES centros_custo(id),
            conta_financeira_id UUID REFERENCES contas_financeiras(id),
            status              status_pre_lancamento_whatsapp NOT NULL DEFAULT 'pendente_revisao',
            created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
        );

        CREATE INDEX idx_pre_lancamentos_whatsapp_status ON pre_lancamentos_whatsapp(status);
        CREATE INDEX idx_pre_lancamentos_whatsapp_telefone ON pre_lancamentos_whatsapp(telefone);
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP TABLE IF EXISTS pre_lancamentos_whatsapp CASCADE;
        DROP TYPE IF EXISTS status_pre_lancamento_whatsapp CASCADE;
        ALTER TABLE usuarios DROP COLUMN IF EXISTS telefone_whatsapp;
        """
    )
