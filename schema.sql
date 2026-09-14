-- ============================================================================
-- SCHEMA — Finance P&G
-- PostgreSQL 15+
-- MVP: conciliação bancária (OFX/CSV), notas fiscais, contas a pagar/receber
--      com recorrência e regra de dia útil.
-- ============================================================================

-- Extensão pra UUID
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ----------------------------------------------------------------------------
-- ENUMS
-- ----------------------------------------------------------------------------

CREATE TYPE papel_usuario AS ENUM ('financeiro', 'admin', 'master', 'sub');

CREATE TYPE tipo_parceiro AS ENUM ('fornecedor', 'cliente', 'ambos');

CREATE TYPE tipo_nota AS ENUM ('nfe', 'nfse');

CREATE TYPE tipo_operacao_nota AS ENUM ('entrada', 'saida'); -- entrada=despesa (compra), saida=receita (venda)

CREATE TYPE status_nota AS ENUM ('pendente', 'parcialmente_conciliada', 'conciliada', 'cancelada');

CREATE TYPE status_processamento_nota AS ENUM (
    'aguardando_extracao',   -- PDF subiu, worker ainda não pegou
    'chave_nao_encontrada',  -- extração falhou, aguardando chave manual
    'consultando_api',       -- chamando o provedor externo (NFe.io etc.)
    'concluido',             -- XML obtido e campos preenchidos
    'erro_api'               -- provedor externo falhou, permite retry manual
);

CREATE TYPE periodicidade AS ENUM ('mensal', 'quinzenal', 'semanal', 'anual', 'personalizada_dias');

CREATE TYPE status_conta AS ENUM ('pendente', 'pago', 'atrasado', 'cancelado');

CREATE TYPE forma_baixa AS ENUM ('manual', 'conciliacao_automatica');

CREATE TYPE formato_extrato AS ENUM ('ofx', 'csv');

CREATE TYPE status_importacao AS ENUM ('processando', 'concluido', 'erro');

CREATE TYPE tipo_lancamento_extrato AS ENUM ('credito', 'debito');

CREATE TYPE status_conciliacao_linha AS ENUM ('pendente', 'conciliado', 'parcial', 'divergente', 'ignorado');

CREATE TYPE tipo_match AS ENUM ('automatico_exato', 'automatico_tolerancia', 'parcial', 'manual');


-- ----------------------------------------------------------------------------
-- USUÁRIOS E ACESSO
-- ----------------------------------------------------------------------------

CREATE TABLE usuarios (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    nome            VARCHAR(150) NOT NULL,
    email           VARCHAR(150) NOT NULL UNIQUE,
    senha_hash      VARCHAR(255) NOT NULL,
    papel           papel_usuario NOT NULL DEFAULT 'sub',
    ativo           BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);


-- ----------------------------------------------------------------------------
-- CADASTROS BASE
-- ----------------------------------------------------------------------------

CREATE TABLE contas_bancarias (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    apelido         VARCHAR(100) NOT NULL,          -- ex: "Itaú CC Principal"
    banco           VARCHAR(100),
    agencia         VARCHAR(20),
    numero_conta    VARCHAR(30),
    tipo_conta      VARCHAR(30),                    -- corrente, poupança
    saldo_inicial   NUMERIC(14,2) NOT NULL DEFAULT 0,
    ativo           BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE centros_custo (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    codigo          VARCHAR(30) UNIQUE,
    nome            VARCHAR(150) NOT NULL,
    ativo           BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE parceiros (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tipo            tipo_parceiro NOT NULL DEFAULT 'fornecedor',
    cnpj_cpf        VARCHAR(20) UNIQUE,
    razao_social    VARCHAR(200) NOT NULL,
    nome_fantasia   VARCHAR(200),
    email           VARCHAR(150),
    telefone        VARCHAR(30),
    ativo           BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Projeto de obra/contrato. Usado pra vincular mão de obra contratada
-- E receita recorrente de cliente (medições) a um contexto comum.
CREATE TYPE status_projeto AS ENUM ('ativo', 'concluido', 'cancelado');

CREATE TABLE projetos (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    nome                VARCHAR(200) NOT NULL,
    cliente_id          UUID REFERENCES parceiros(id),   -- parceiro com tipo='cliente'
    data_inicio         DATE,
    data_fim_previsto   DATE,
    status              status_projeto NOT NULL DEFAULT 'ativo',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_projetos_status ON projetos(status);


-- ----------------------------------------------------------------------------
-- NOTAS FISCAIS
-- ----------------------------------------------------------------------------

CREATE TABLE notas_fiscais (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    parceiro_id         UUID NOT NULL REFERENCES parceiros(id),
    centro_custo_id     UUID REFERENCES centros_custo(id),
    tipo                tipo_nota NOT NULL,
    tipo_operacao       tipo_operacao_nota NOT NULL DEFAULT 'entrada',
    numero_nota         VARCHAR(30),
    serie               VARCHAR(10),
    chave_acesso        VARCHAR(44) UNIQUE,          -- chave NFe, evita duplicidade no upload
    valor_total         NUMERIC(14,2) NOT NULL,
    data_emissao        DATE NOT NULL,

    -- classificação de despesa (só relevante quando tipo_operacao = 'entrada')
    despesa_fixa        BOOLEAN NOT NULL DEFAULT FALSE,
    despesa_parcelada   BOOLEAN NOT NULL DEFAULT FALSE,
    numero_parcelas     INTEGER NOT NULL DEFAULT 1,

    arquivo_xml_path    TEXT,
    arquivo_pdf_path    TEXT,
    dados_extraidos_xml JSONB,                       -- payload cru extraído do XML, pra auditoria/reprocessamento

    status              status_nota NOT NULL DEFAULT 'pendente',
    status_processamento status_processamento_nota NOT NULL DEFAULT 'aguardando_extracao',
    criado_por          UUID REFERENCES usuarios(id),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT chk_parcelas_positivas CHECK (numero_parcelas >= 1)
);

CREATE INDEX idx_notas_parceiro ON notas_fiscais(parceiro_id);
CREATE INDEX idx_notas_status ON notas_fiscais(status);
CREATE INDEX idx_notas_data_emissao ON notas_fiscais(data_emissao);


-- ----------------------------------------------------------------------------
-- RECORRÊNCIA (regra de negócio central de geração de parcelas futuras)
-- ----------------------------------------------------------------------------

CREATE TABLE lancamentos_recorrentes (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tipo_operacao       tipo_operacao_nota NOT NULL,      -- entrada=pagar, saida=receber
    descricao           VARCHAR(200) NOT NULL,
    parceiro_id         UUID REFERENCES parceiros(id),
    centro_custo_id     UUID REFERENCES centros_custo(id),
    nota_fiscal_origem_id UUID REFERENCES notas_fiscais(id),  -- se nasceu de uma nota parcelada
    projeto_id          UUID REFERENCES projetos(id),         -- salário de funcionário ou contrato de cliente

    valor_parcela       NUMERIC(14,2) NOT NULL,

    -- condição de parada: numero_ocorrencias fixo (ex: nota em 3x) OU
    -- data_fim aberta (ex: salário/contrato que roda "enquanto durar").
    -- Pelo menos um dos dois é obrigatório; se os dois forem informados,
    -- para no que vier primeiro.
    numero_ocorrencias  INTEGER,
    data_fim            DATE,

    periodicidade       periodicidade NOT NULL,
    intervalo_dias      INTEGER,                      -- só usado se periodicidade = 'personalizada_dias'
    data_inicio         DATE NOT NULL,

    conta_bancaria_id   UUID REFERENCES contas_bancarias(id),  -- de/para qual conta
    ativo               BOOLEAN NOT NULL DEFAULT TRUE,
    criado_por          UUID REFERENCES usuarios(id),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT chk_ocorrencias_positivas CHECK (numero_ocorrencias IS NULL OR numero_ocorrencias >= 1),
    CONSTRAINT chk_tem_condicao_parada CHECK (numero_ocorrencias IS NOT NULL OR data_fim IS NOT NULL),
    CONSTRAINT chk_intervalo_dias CHECK (
        (periodicidade = 'personalizada_dias' AND intervalo_dias IS NOT NULL)
        OR (periodicidade != 'personalizada_dias')
    )
);

CREATE INDEX idx_lancrec_projeto ON lancamentos_recorrentes(projeto_id);


-- ----------------------------------------------------------------------------
-- FUNCIONÁRIOS (mão de obra por projeto)
-- Contratação gera automaticamente 1 lancamento_recorrente (salário mensal,
-- data_fim = data prevista de fim do projeto ou aberta). Demissão fecha essa
-- recorrência (seta data_fim = data_demissao) sem apagar histórico já pago.
-- ----------------------------------------------------------------------------

CREATE TYPE status_funcionario AS ENUM ('ativo', 'demitido');

CREATE TABLE funcionarios (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    nome                    VARCHAR(150) NOT NULL,
    cpf                     VARCHAR(14) UNIQUE,
    cargo                   VARCHAR(100),
    projeto_id              UUID REFERENCES projetos(id),
    valor_salario           NUMERIC(14,2) NOT NULL,
    data_contratacao        DATE NOT NULL,
    data_demissao           DATE,
    status                  status_funcionario NOT NULL DEFAULT 'ativo',
    lancamento_recorrente_id UUID REFERENCES lancamentos_recorrentes(id),  -- despesa salarial gerada
    criado_por              UUID REFERENCES usuarios(id),
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT chk_demissao_apos_contratacao CHECK (data_demissao IS NULL OR data_demissao >= data_contratacao)
);

CREATE INDEX idx_funcionarios_projeto ON funcionarios(projeto_id);
CREATE INDEX idx_funcionarios_status ON funcionarios(status);


-- ----------------------------------------------------------------------------
-- CONTAS A PAGAR / RECEBER
-- Cada linha é UMA parcela/ocorrência já materializada (não um cálculo em tempo real).
-- Motivo: dashboard de vencimento precisa de query simples e rápida, e baixa
-- (pagamento) precisa de um registro fixo pra conciliar contra.
-- ----------------------------------------------------------------------------

CREATE TABLE contas_financeiras (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tipo_operacao           tipo_operacao_nota NOT NULL,   -- entrada=pagar, saida=receber

    lancamento_recorrente_id UUID REFERENCES lancamentos_recorrentes(id),
    nota_fiscal_id          UUID REFERENCES notas_fiscais(id),
    parceiro_id             UUID NOT NULL REFERENCES parceiros(id),
    centro_custo_id         UUID REFERENCES centros_custo(id),

    descricao               VARCHAR(200) NOT NULL,
    numero_parcela          INTEGER NOT NULL DEFAULT 1,
    total_parcelas          INTEGER NOT NULL DEFAULT 1,
    valor                   NUMERIC(14,2) NOT NULL,

    -- auditoria da regra de dia útil: guarda as duas datas
    data_vencimento_original DATE NOT NULL,   -- data "pura", antes do ajuste de fim de semana/feriado
    data_vencimento          DATE NOT NULL,   -- data real de cobrança, já ajustada (usada em toda query/alerta)

    data_pagamento          DATE,
    valor_pago              NUMERIC(14,2),
    status                  status_conta NOT NULL DEFAULT 'pendente',
    forma_baixa             forma_baixa,

    -- boleto (quando aplicável) — data_vencimento acima já é a data do boleto;
    -- o arquivo fica anexado na própria parcela pra aparecer junto no relatório
    boleto_linha_digitavel  VARCHAR(60),
    boleto_codigo_barras    VARCHAR(60),
    boleto_arquivo_path     TEXT,

    conta_bancaria_id       UUID REFERENCES contas_bancarias(id),  -- conta usada na baixa
    criado_por              UUID REFERENCES usuarios(id),
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT chk_data_vencimento_ajustada CHECK (data_vencimento >= data_vencimento_original)
);

-- Índice principal do dashboard: "o que vence nos próximos X dias"
CREATE INDEX idx_contas_vencimento_status ON contas_financeiras(data_vencimento, status);
CREATE INDEX idx_contas_parceiro ON contas_financeiras(parceiro_id);
CREATE INDEX idx_contas_recorrencia ON contas_financeiras(lancamento_recorrente_id);
CREATE INDEX idx_contas_nota ON contas_financeiras(nota_fiscal_id);


-- ----------------------------------------------------------------------------
-- CONCILIAÇÃO BANCÁRIA
-- ----------------------------------------------------------------------------

CREATE TABLE extratos_importados (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conta_bancaria_id   UUID NOT NULL REFERENCES contas_bancarias(id),
    arquivo_original_path TEXT NOT NULL,
    formato             formato_extrato NOT NULL,
    periodo_inicio      DATE,
    periodo_fim         DATE,
    status              status_importacao NOT NULL DEFAULT 'processando',
    mensagem_erro       TEXT,
    importado_por       UUID REFERENCES usuarios(id),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE lancamentos_extrato (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    extrato_importado_id    UUID NOT NULL REFERENCES extratos_importados(id),
    conta_bancaria_id       UUID NOT NULL REFERENCES contas_bancarias(id),  -- denormalizado, acelera query

    data                    DATE NOT NULL,
    descricao               TEXT,
    valor                   NUMERIC(14,2) NOT NULL,       -- sempre positivo
    tipo                    tipo_lancamento_extrato NOT NULL,
    fitid                   VARCHAR(100),                 -- ID único da transação no OFX, evita duplicar em reimportação

    status_conciliacao      status_conciliacao_linha NOT NULL DEFAULT 'pendente',
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- evita reimportar a mesma transação duas vezes
    CONSTRAINT uq_lancamento_extrato_fitid UNIQUE (conta_bancaria_id, fitid)
);

CREATE INDEX idx_lancext_conta_status ON lancamentos_extrato(conta_bancaria_id, status_conciliacao);
CREATE INDEX idx_lancext_data_valor ON lancamentos_extrato(data, valor);  -- usado pelo matching automático

-- Tabela de junção N:N — é isso que resolve o matching parcial.
-- Um lançamento de extrato pode conciliar com várias contas_financeiras
-- (ex: 1 PIX paga 2 parcelas), e uma conta_financeira pode ser paga
-- por vários lançamentos de extrato (ex: pagamento dividido).
CREATE TABLE conciliacoes (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lancamento_extrato_id UUID NOT NULL REFERENCES lancamentos_extrato(id),
    conta_financeira_id UUID REFERENCES contas_financeiras(id),
    nota_fiscal_id      UUID REFERENCES notas_fiscais(id),

    valor_conciliado    NUMERIC(14,2) NOT NULL,
    tipo_match          tipo_match NOT NULL,

    confirmado_por      UUID REFERENCES usuarios(id),   -- null = ainda não revisado por humano
    confirmado_em       TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT chk_conciliacao_tem_destino CHECK (
        conta_financeira_id IS NOT NULL OR nota_fiscal_id IS NOT NULL
    )
);

CREATE INDEX idx_conciliacoes_lancamento ON conciliacoes(lancamento_extrato_id);
CREATE INDEX idx_conciliacoes_conta ON conciliacoes(conta_financeira_id);


-- ----------------------------------------------------------------------------
-- NOTA DE DESIGN: regra de dia útil
-- ----------------------------------------------------------------------------
-- NÃO existe tabela de feriados aqui de propósito. Pro MVP, o cálculo de
-- dia útil (sábado/domingo → próximo dia útil, + feriados nacionais BR)
-- é feito 100% na aplicação via lib `workalendar` (Brazil calendar), num
-- serviço único `DiaUtilCalculator`. Isso evita manter uma tabela de
-- feriados manualmente. Se no futuro precisar de feriados municipais/
-- pontos facultativos específicos da empresa, aí sim cria-se uma tabela
-- `feriados_customizados` — não é necessário para o MVP.
-- ============================================================================
