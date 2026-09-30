"""Certificado A1 (NFeDistribuicaoDFe) e Open Finance (Pluggy)

- certificados_digitais: .pfx e senha CIFRADOS (Fernet); no máximo 1 ativo.
- nfes_sefaz_recebidas: caixa de entrada de NFes do CNPJ (chave UNIQUE).
- conexoes_open_finance + colunas em contas_bancarias pra vincular conta remota.
- formato_extrato ganha 'open_finance' (sincronização automática, sem arquivo).

Revision ID: 0011
Revises: 0010
Create Date: 2026-09-30

"""
from typing import Sequence, Union

from alembic import op

revision: str = "0011"
down_revision: Union[str, None] = "0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ADD VALUE não pode ser usado na mesma transação em que é criado
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE formato_extrato ADD VALUE IF NOT EXISTS 'open_finance';")

    op.execute(
        """
        CREATE TABLE certificados_digitais (
            id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            cnpj                VARCHAR(14)  NOT NULL,
            razao_social        VARCHAR(255) NOT NULL,
            arquivo_cifrado     BYTEA        NOT NULL,
            senha_cifrada       BYTEA        NOT NULL,
            fingerprint_sha256  VARCHAR(64)  NOT NULL UNIQUE,
            valido_de           TIMESTAMPTZ  NOT NULL,
            valido_ate          TIMESTAMPTZ  NOT NULL,
            ativo               BOOLEAN      NOT NULL DEFAULT true,
            uf_autor            SMALLINT     NOT NULL DEFAULT 35,
            ult_nsu             VARCHAR(15)  NOT NULL DEFAULT '0',
            max_nsu             VARCHAR(15),
            ult_sincronizacao   TIMESTAMPTZ,
            ult_mensagem_sefaz  TEXT,
            bloqueado_ate       TIMESTAMPTZ,
            criado_por          UUID REFERENCES usuarios(id),
            created_at          TIMESTAMPTZ  NOT NULL DEFAULT now()
        );
        CREATE UNIQUE INDEX uq_certificado_ativo ON certificados_digitais ((true)) WHERE ativo;

        CREATE TABLE nfes_sefaz_recebidas (
            id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            certificado_id  UUID NOT NULL REFERENCES certificados_digitais(id),
            nsu             VARCHAR(15) NOT NULL,
            chave_acesso    VARCHAR(44) NOT NULL UNIQUE,
            cnpj_emitente   VARCHAR(14),
            nome_emitente   VARCHAR(255),
            valor_total     NUMERIC(14,2),
            data_emissao    DATE,
            tipo_documento  VARCHAR(10) NOT NULL CHECK (tipo_documento IN ('resumo', 'completo')),
            xml_bruto       TEXT,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE INDEX idx_nfes_sefaz_data ON nfes_sefaz_recebidas (data_emissao DESC);

        CREATE TABLE conexoes_open_finance (
            id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            provedor       VARCHAR(30)  NOT NULL DEFAULT 'pluggy',
            item_id        VARCHAR(100) NOT NULL UNIQUE,
            conector_nome  VARCHAR(100),
            status         VARCHAR(40),
            criado_por     UUID REFERENCES usuarios(id),
            created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
        );

        ALTER TABLE contas_bancarias
            ADD COLUMN conexao_open_finance_id      UUID REFERENCES conexoes_open_finance(id),
            ADD COLUMN open_finance_conta_id        VARCHAR(100) UNIQUE,
            ADD COLUMN open_finance_sincronizado_em TIMESTAMPTZ;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE contas_bancarias
            DROP COLUMN IF EXISTS open_finance_sincronizado_em,
            DROP COLUMN IF EXISTS open_finance_conta_id,
            DROP COLUMN IF EXISTS conexao_open_finance_id;
        DROP TABLE IF EXISTS conexoes_open_finance CASCADE;
        DROP TABLE IF EXISTS nfes_sefaz_recebidas CASCADE;
        DROP TABLE IF EXISTS certificados_digitais CASCADE;
        """
    )
    # o valor 'open_finance' do enum fica (Postgres não remove valor de ENUM)
