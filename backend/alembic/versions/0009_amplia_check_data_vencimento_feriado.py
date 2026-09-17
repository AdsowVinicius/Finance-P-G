"""Amplia chk_data_vencimento_ajustada pra cobrir feriado emendado com fim de semana

A migration 0007 relaxou a constraint pra permitir até 2 dias de deslocamento
pra trás (só cobria o caso "cai no fim de semana" da regra bancária). Corrigido
`DiaUtilCalculator.ajustar_por_categoria` (regra `bancaria`) pra também
empurrar pra trás sobre feriado nacional, não só fim de semana — banco não
abre em feriado. Isso pode encadear mais de 2 dias pra trás quando o feriado
emenda com o fim de semana (ex: feriado numa sexta-feira: domingo seguinte
precisa voltar sábado + sexta feriado + só aí acha quinta útil = 3 dias).
Amplia a tolerância pra 4 dias, mantendo a constraint como guarda contra
ajuste catastrófico (ex: bug que jogasse a data meses de diferença) sem
travar o caso legítimo de feriado emendado.

Revision ID: 0009
Revises: 0008
Create Date: 2026-09-16

"""
from typing import Sequence, Union

from alembic import op

revision: str = "0009"
down_revision: Union[str, None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE contas_financeiras DROP CONSTRAINT chk_data_vencimento_ajustada;
        ALTER TABLE contas_financeiras ADD CONSTRAINT chk_data_vencimento_ajustada
            CHECK (data_vencimento >= data_vencimento_original - INTERVAL '4 days');
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE contas_financeiras DROP CONSTRAINT chk_data_vencimento_ajustada;
        ALTER TABLE contas_financeiras ADD CONSTRAINT chk_data_vencimento_ajustada
            CHECK (data_vencimento >= data_vencimento_original - INTERVAL '2 days');
        """
    )
