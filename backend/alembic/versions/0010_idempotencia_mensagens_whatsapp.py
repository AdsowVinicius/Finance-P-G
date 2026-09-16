"""Idempotência de mensagem do WhatsApp (wamid)

Bug real: a Cloud API do WhatsApp reentrega webhooks (timeout, resposta
não-200, etc.) e nada no fluxo (`whatsapp_webhook.py` → tasks Celery →
`criar_pre_lancamento`) deduplicava pelo id da mensagem (wamid) — uma
reentrega processava a mesma mensagem de novo e podia criar um
pré-lançamento financeiro duplicado. Mesmo padrão de idempotência já usado
em `chave_acesso` (notas fiscais) e `fitid` (extrato): um identificador
único do lado de fora, checado/registrado antes de processar.

Revision ID: 0010
Revises: 0009
Create Date: 2026-09-16

"""
from typing import Sequence, Union

from alembic import op

revision: str = "0010"
down_revision: Union[str, None] = "0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE mensagens_whatsapp_processadas (
            id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            wamid       VARCHAR(100) NOT NULL UNIQUE,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS mensagens_whatsapp_processadas CASCADE;")
