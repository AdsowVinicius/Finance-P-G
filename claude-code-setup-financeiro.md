# Setup do Claude Code — Aplicação de Gestão Financeira

Documento de referência com os plugins/MCPs recomendados, ordem de instalação e boas práticas para manter excelência de código durante o desenvolvimento do MVP.

---

## 1. Plugins/MCPs recomendados

### Prioridade 1 — instalar antes de começar a codar

| Plugin | O que faz | Por que importa aqui | Comando |
|---|---|---|---|
| **Serena** | Indexação semântica do código por símbolo (função/classe/variável) via LSP, com memória persistente do projeto entre sessões. Evita releitura de arquivos inteiros a cada prompt. | Projeto vai crescer rápido (conciliação, notas, contas a pagar/receber) — mantém o Claude Code eficiente em token conforme o repositório aumenta. | Ver seção 2 (instalação via Docker) |
| **PostgreSQL MCP** | Consulta e manipulação do banco em linguagem natural, direto do terminal. | Acelera testes da modelagem de dados (lançamentos, recorrência, matching de extrato) sem sair do Claude Code. | `claude mcp add postgres -- npx -y @modelcontextprotocol/server-postgres "<connection_string>"` |
| **Context7** | Documentação atualizada de libs/frameworks direto no contexto. | Evita código gerado com API desatualizada — retrabalho custa tempo que você não tem até segunda. | `claude mcp add context7 -- npx -y @upstash/context7-mcp` |

### Prioridade 2 — durante o desenvolvimento

| Plugin | O que faz | Comando |
|---|---|---|
| **GitHub MCP** | Integra PRs, issues e CI/CD direto no fluxo do Claude Code. | `claude mcp add github -- npx -y @modelcontextprotocol/server-github` (precisa de token) |
| **mcp-server-chart (AntV)** | Gera 25+ tipos de gráfico (linha, barra, treemap, sankey etc.) a partir de dados — útil para dashboards financeiros (fluxo de caixa, DRE simplificado). | `claude mcp add mcp-server-chart -- npx -y @antv/mcp-server-chart` |
| **Playwright MCP** | Testes end-to-end automatizados das telas (login, lançamento, conciliação). Token-pesado — usar só nos fluxos críticos. | via `claude mcp add playwright` (checar docs oficiais para o comando atual) |

### Prioridade 3 — refinamento de UI (pós-MVP funcional)

| Plugin | O que faz | Comando |
|---|---|---|
| **21st MCP (ex-Magic)** | Gera componentes React/Tailwind prontos a partir de descrição em linguagem natural, puxando de catálogo com +10 mil componentes. | `claude plugin marketplace add 21st-dev/magic-mcp` seguido de `claude plugin install 21st` (precisa de API key em 21st.dev/mcp) |

---

## 2. Instalação detalhada — Serena (o mais importante pra economia de token)

```bash
docker pull ghcr.io/oraios/serena:latest

claude mcp add serena \
  --scope user \
  --transport stdio \
  -- docker run --rm -i \
     --network host \
     -e SERENA_DOCKER=1 \
     -v "${HOME}/projects:/workspaces/projects" \
     ghcr.io/oraios/serena:latest \
     serena start-mcp-server \
     --context claude-code \
     --transport stdio
```

Na primeira vez em cada projeto, indexar:
```bash
cd /caminho/do/seu/projeto
docker run --rm -v "${PWD}:/workspaces/project" ghcr.io/oraios/serena:latest \
  serena project index /workspaces/project
```

⚠️ Não instalar via marketplace de plugin genérico — os comandos lá costumam estar desatualizados. Seguir o Quick Start oficial em `github.com/oraios/serena`.

---

## 3. Boas práticas para excelência de código com Claude Code

- **Mantenha um `CLAUDE.md`** na raiz do projeto com: contexto do domínio (regras de dia útil, estrutura de conciliação), convenções de código, e decisões arquiteturais já tomadas. Isso substitui reexplicar tudo a cada sessão.
- **Sessão nova em vez de resumida** quando o contexto ficar muito longo ou pesado — evita degradação de qualidade por acúmulo de contexto irrelevante.
- **Padrões que você já usa em outros projetos (Aionis)** valem aqui também: Registry pattern para integrações (ex.: leitor de extrato bancário como um provider plugável), Result objects para retorno de operações (sucesso/erro estruturado), jobs em background com idempotência para qualquer processamento assíncrono (importação de extrato, geração de recorrências).
- **Regra de negócio centralizada, nunca espalhada**: a lógica de "sábado/domingo não conta como dia útil" deve viver em um único lugar (ex.: um serviço `DiaUtilCalculator`), nunca duplicada em vários pontos do código.
- **Revisão incremental**: ao final de cada módulo (conciliação, notas, contas a pagar/receber), peça ao Claude Code uma revisão de código focada em segurança e edge cases antes de seguir pro próximo.
- **Testes desde o início**: mesmo no MVP, cobrir pelo menos a lógica de recorrência e de matching de conciliação com testes automatizados — são os pontos mais propensos a bug silencioso.
