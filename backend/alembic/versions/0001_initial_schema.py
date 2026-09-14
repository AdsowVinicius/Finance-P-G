"""schema inicial — migrado 1:1 a partir de schema.sql (fonte da verdade, não redesenhado)

Revision ID: 0001
Revises:
Create Date: 2026-09-14

"""
from pathlib import Path
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# O DDL completo vive em schema.sql, na raiz do projeto (fonte da verdade,
# já fechada e validada). Esta migration só a aplica — não reescreve nada.
_SCHEMA_SQL_PATH = Path(__file__).resolve().parents[3] / "schema.sql"


def upgrade() -> None:
    schema_sql = _SCHEMA_SQL_PATH.read_text(encoding="utf-8")
    op.execute(schema_sql)


def downgrade() -> None:
    tabelas_em_ordem_reversa = [
        "conciliacoes",
        "lancamentos_extrato",
        "extratos_importados",
        "contas_financeiras",
        "funcionarios",
        "lancamentos_recorrentes",
        "notas_fiscais",
        "projetos",
        "parceiros",
        "centros_custo",
        "contas_bancarias",
        "usuarios",
    ]
    for tabela in tabelas_em_ordem_reversa:
        op.execute(f"DROP TABLE IF EXISTS {tabela} CASCADE")

    tipos = [
        "status_funcionario",
        "status_projeto",
        "tipo_match",
        "status_conciliacao_linha",
        "tipo_lancamento_extrato",
        "status_importacao",
        "formato_extrato",
        "forma_baixa",
        "status_conta",
        "periodicidade",
        "status_processamento_nota",
        "status_nota",
        "tipo_operacao_nota",
        "tipo_nota",
        "tipo_parceiro",
        "papel_usuario",
    ]
    for tipo in tipos:
        op.execute(f"DROP TYPE IF EXISTS {tipo} CASCADE")
