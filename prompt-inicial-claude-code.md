Este é o início do projeto do Finance P&G.

Antes de escrever qualquer código:

1. Leia todos os arquivos da raiz do projeto: CLAUDE.md (contexto e regras de negócio — leia primeiro e integralmente), requisitos-funcionais-nao-funcionais.md, documentacao-sistema-financeiro.md, schema.sql, arquitetura.mermaid, schema-der.mermaid e schema-mer.mermaid.

2. Instale e configure os MCPs conforme claude-code-setup-financeiro.md, nesta ordem: Serena (indexação semântica e memória do projeto), PostgreSQL MCP, Context7, mcp-server-chart (gráficos do dashboard de vencimento — trazido pra agora porque serve o requisito de maior prioridade do projeto). Indexe o projeto com o Serena assim que houver código. Confirme que os quatro estão respondendo antes de seguir para o próximo passo.

3. Comece pelo bloco "Hoje à noite" do cronograma (seção 4 de documentacao-sistema-financeiro.md):
   - Suba um docker-compose.yml com PostgreSQL 15 e Redis.
   - Gere a migration inicial do Alembic a partir do schema.sql existente — o schema já está fechado e validado, não redesenhe, apenas migre.
   - Faça o scaffold do backend em FastAPI, organizado por camada (routers / services / models / workers), e do frontend em React com Vite.
   - Implemente autenticação JWT com os 4 papéis definidos em CLAUDE.md (financeiro, admin, master, sub).
   - Implemente os CRUDs base: parceiros, centros de custo, contas bancárias.

4. Ao final deste bloco, pare e me mostre o que ficou pronto (incluindo como subir o ambiente localmente) antes de seguir para o próximo bloco do cronograma ("Amanhã de manhã": DiaUtilCalculator, RecorrenciaService, contas a pagar/receber, upload de nota fiscal).

Regra geral pro projeto inteiro: siga CLAUDE.md à risca em tudo que for regra de negócio (dia útil, recorrência, conciliação, dinheiro sempre em Decimal) — essas decisões já foram validadas e não devem ser reabertas sem eu pedir.
