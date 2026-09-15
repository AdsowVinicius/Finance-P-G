"""Forma de pagamento em contas_financeiras e pre_lancamentos_whatsapp

Campo pedido pelo usuário pra suportar conciliação corretamente: Pix/cartão/
transferência aparecem no extrato bancário e devem casar automaticamente;
dinheiro nunca aparece no extrato, então não deveria nem tentar conciliar.

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-15

"""
from typing import Sequence, Union

from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TYPE forma_pagamento AS ENUM
            ('pix', 'dinheiro', 'cartao_credito', 'cartao_debito', 'boleto', 'transferencia', 'outro');

        ALTER TABLE contas_financeiras ADD COLUMN forma_pagamento forma_pagamento;
        ALTER TABLE pre_lancamentos_whatsapp ADD COLUMN forma_pagamento forma_pagamento;

        CREATE INDEX idx_contas_financeiras_forma_pagamento ON contas_financeiras(forma_pagamento);
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP INDEX IF EXISTS idx_contas_financeiras_forma_pagamento;
        ALTER TABLE pre_lancamentos_whatsapp DROP COLUMN IF EXISTS forma_pagamento;
        ALTER TABLE contas_financeiras DROP COLUMN IF EXISTS forma_pagamento;
        DROP TYPE IF EXISTS forma_pagamento;
        """
    )
