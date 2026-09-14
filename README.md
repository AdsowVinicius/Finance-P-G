# Finance P&G

Sistema financeiro interno da P&G Engenharia — conciliação bancária, notas fiscais e contas a pagar/receber. Ver [`CLAUDE.md`](CLAUDE.md) para contexto completo e regras de negócio.

## Stack

- **Backend**: Python 3.12 + FastAPI + SQLAlchemy + Alembic + PostgreSQL 15+
- **Fila**: Celery + Redis
- **Frontend**: React 19 + Vite + TypeScript + Tailwind CSS v4

## Estrutura

```
backend/
  app/
    routers/    # endpoints FastAPI (finos — só validação/orquestração)
    services/   # regra de negócio pura: DiaUtilCalculator, RecorrenciaService,
                # NotaFiscalService, NfeConsultaClient, ExtratoParserService,
                # ConciliacaoMatcher, auth_service
    models/     # modelos SQLAlchemy (espelham schema.sql)
    schemas/    # schemas Pydantic (request/response)
    workers/    # Celery app + as 2 tasks essenciais (processar_nota_fiscal,
                # processar_importacao_extrato)
    core/       # dependências transversais (auth JWT, RBAC, storage de arquivos)
  alembic/      # migrations — a inicial aplica schema.sql literalmente
  scripts/      # scripts utilitários (seed do primeiro usuário)
  tests/services/  # testes unitários das regras de negócio (sem banco, sem framework)
frontend/
  src/
    pages/       # login, dashboard de vencimento, notas fiscais, extrato/
                 # conciliação, lançamentos recorrentes, parceiros, centros
                 # de custo, contas bancárias
    components/  # Layout, ProtectedRoute
    contexts/    # AuthContext (JWT em localStorage)
    lib/         # cliente axios
schema.sql, *.mermaid, *.md   # documentação e fonte da verdade do schema (raiz do projeto)
```

## Testes

```bash
cd backend
.venv\Scripts\pytest tests/ -v
```

60 testes unitários (sem banco, sem framework) cobrindo os pontos de maior risco: `DiaUtilCalculator` (8), `RecorrenciaService` (14), extração de chave de PDF (`NotaFiscalService`, 5), `ConciliacaoMatcher` (14 — exato, tolerância, parcial/split, nunca tolerância de valor), `ExtratoParserService` (9 — OFX e CSV) e `NfeConsultaClient` (10 — parse de XML e o fluxo HTTP inteiro mockado, sem bater na API real nos testes).

**Bug real pego pelo teste**: a primeira versão de `RecorrenciaService` acumulava `relativedelta` sobre a ocorrência anterior — uma recorrência mensal começando dia 31 perdia essa referência ao passar por fevereiro (virava dia 28 pra sempre, em vez de voltar pro dia 31 em março). Corrigido calculando cada ocorrência sempre a partir da data-âncora original.

## Ambiente local

> Esta máquina não tinha Docker/WSL2. Por decisão do usuário, Postgres e Redis rodam nativos no Windows em vez de containers. O `docker-compose.yml` na raiz continua disponível para quando houver Docker (ex: deploy).

### 1. Banco de dados (PostgreSQL)

Esta máquina já tinha um **PostgreSQL 16** instalado (de outro projeto, porta 5432 padrão) — em vez de instalar uma segunda instância, foi criado um banco e um usuário dedicados **isolados** nele:

```sql
CREATE ROLE pgfinance WITH LOGIN PASSWORD 'SUA_SENHA_AQUI';
CREATE DATABASE pgfinance OWNER pgfinance;
```

Connection string (já em `backend/.env`): `postgresql+psycopg2://pgfinance:SUA_SENHA_AQUI@localhost:5432/pgfinance`.

Se for rodar em outra máquina sem Postgres nenhum: instale a versão 15+ (`winget install PostgreSQL.PostgreSQL.15`) e ajuste `DATABASE_URL` em `backend/.env`.

### 2. Redis (fila do Celery)

Sem Docker nesta máquina, o Redis roda via **redis-windows** (build portátil, sem serviço/instalação):

```powershell
winget install taizod1024.redis-windows-fork
# depois, para subir (fica em primeiro plano; abra um terminal dedicado):
& "$env:LOCALAPPDATA\Microsoft\WinGet\Packages\taizod1024.redis-windows-fork_Microsoft.Winget.Source_8wekyb3d8bbwe\Redis-8.10.1-Windows-x64-msys2\redis-server.exe" --port 6379 --bind 127.0.0.1
```

(O `Memurai.MemuraiDeveloper` via winget falhou na instalação nesta máquina — erro do instalador MSI ao criar diretório temporário, possivelmente por causa do OneDrive sincronizando o perfil do usuário. O `redis-windows-fork` contorna isso por ser um zip portátil, sem instalador MSI.)

### 3. Backend

```bash
cd backend
py -3.12 -m venv .venv
.venv\Scripts\pip install -r requirements.txt
copy .env.example .env   # edite DATABASE_URL/JWT_SECRET_KEY se necessário
.venv\Scripts\alembic upgrade head
.venv\Scripts\python -m scripts.seed_usuario_inicial --email admin@pg.com --senha "TrocarDepois123!" --nome Admin --papel master
.venv\Scripts\uvicorn app.main:app --reload --port 8000
```

API em `http://localhost:8000`, docs interativas em `http://localhost:8000/docs`.

### 4. Frontend

```bash
cd frontend
npm install
copy .env.example .env   # VITE_API_URL=http://localhost:8000
npm run dev
```

App em `http://localhost:5173`. Login com o usuário criado no passo 3 (seed).

### 5. Worker do Celery (upload de nota fiscal e importação de extrato)

```bash
cd backend
.venv\Scripts\celery.exe -A app.workers.celery_app worker --loglevel=info --pool=solo
```

`--pool=solo` porque o pool padrão do Celery (prefork) não roda no Windows (sem `os.fork`). Sem o worker rodando, upload de nota fiscal e importação de extrato ficam em `processando`/`consultando_api` indefinidamente — a criação da task só é enfileirada, quem processa é o worker.

Scripts prontos na raiz do projeto pra cada um desses 4 serviços (`iniciar_redis.bat`, `iniciar_backend.bat`, `iniciar_frontend.bat`, `iniciar_celery.bat`) — um terminal por serviço.

## Papéis de acesso (RF01)

`financeiro`, `admin`, `master`, `sub` — definidos em `app/models/enums.py::PapelUsuario`. Regra aplicada em todos os módulos (cadastros base + contas a pagar/receber + notas fiscais): leitura liberada para qualquer usuário autenticado; escrita (criar/editar/desativar/dar baixa/anexar boleto) restrita a `financeiro`/`admin`/`master`. Criação de novos usuários restrita a `admin`/`master`. Esta é uma decisão de implementação (não estava explícita nos requisitos) — ajustar se não refletir o esperado.

## Contas a pagar/receber e notas fiscais (bloco "Amanhã de manhã")

- **`DiaUtilCalculator`** (`app/services/dia_util_calculator.py`): único lugar que decide dia útil (sábado/domingo/feriado nacional via `workalendar`). Usado por toda geração de data de vencimento.
- **`RecorrenciaService`** (`app/services/recorrencia_service.py`): gera as parcelas de `lancamentos_recorrentes` (para em `numero_ocorrencias` OU `data_fim`, o que vier primeiro) e também as parcelas de uma nota fiscal parcelada (`gerar_parcelas_valor_total`, sempre mensal, divide o `valor_total` sem perder centavo — a última parcela absorve o resto da divisão).
- **Periodicidades**: `mensal`/`anual` via `dateutil.relativedelta` (preserva o dia original mesmo atravessando meses mais curtos); `semanal` = +7 dias; `quinzenal` = +15 dias (decisão de implementação — não estava detalhado no requisito); `personalizada_dias` = intervalo livre.
- **Dashboard de vencimento** (`GET /contas-financeiras/dashboard`, RF11): 3 categorias (atrasado/hoje/semana), usa o índice `idx_contas_vencimento_status`. Botão manual "Atualizar atrasados" (`POST /contas-financeiras/atualizar-atrasados`) marca `status='atrasado'` — substitui o Celery Beat diário, que ficou pro corte de escopo combinado.
- **Upload de nota fiscal** (`POST /notas-fiscais`, multipart): extrai a chave de acesso do PDF via regex (`pypdf` + `app/services/nota_fiscal_service.py`), sem chamar API externa ainda (isso é o bloco da tarde). Idempotente: upload com a mesma chave já cadastrada retorna 409. Fallback não-bloqueante: `PATCH /notas-fiscais/{id}/chave-acesso` para colar a chave manualmente quando a extração falha (ex: PDF escaneado). Gera as parcelas de `contas_financeiras` no cadastro (não espera a resolução da chave/API — o valor e o parcelamento já foram informados manualmente pelo usuário).
- **Assunção de implementação**: a primeira parcela de uma nota fiscal parcelada vence na própria `data_emissao` (não há campo de "data de vencimento" na nota — só nas parcelas geradas). Ajustar no `NotaFiscalService`/router se o esperado for outro (ex: +30 dias).
- **Boleto anexado**: `POST /contas-financeiras/{id}/boleto` (multipart) — arquivo servido depois em `/storage/boletos/...`.

## Conciliação bancária e API de NFe (bloco "Amanhã à tarde")

- **API de consulta de NFe (opção 3, sem certificado)**: provedor escolhido foi **Meu Danfe** (`api.meudanfe.com.br/v2`), não o NFe.io original da documentação — o NFe.io exige contratação/ativação separada da "Consulta Irrestrita" (sem preço público, precisa contato comercial); o Meu Danfe tem cadastro self-service e cobra **R$0,03 por consulta de NF-e por chave de acesso** (o resto é grátis). Testado com uma chave de acesso real: busca, polling de status, download do XML oficial e parse de emitente/valor/data — tudo funcionando.
  - Fluxo: `PUT /fd/add/{chave}` dispara a busca (status WAITING/SEARCHING/OK/NOT_FOUND/ERROR) → poll (≥1s de intervalo, exigência do provedor) até resolver → se OK, `GET /fd/get/xml/{chave}` baixa o XML oficial → parse via `lxml` (namespace `http://www.portalfiscal.inf.br/nfe`).
  - Chave em `backend/.env` (`MEUDANFE_API_KEY`) — não commitada.
  - **Decisão de design**: os campos manuais que o usuário já informa no upload (parceiro/valor/data) continuam sendo a fonte da verdade das parcelas geradas — a API não sobrescreve isso. O retorno da consulta vai pra `dados_extraidos_xml` (JSONB), exatamente o propósito documentado dessa coluna no schema: auditoria/conferência, não substituição do que já foi lançado manualmente.
  - Task `processar_nota_fiscal` (Celery) roda esse fluxo assim que a chave é resolvida (upload com chave extraída automaticamente, ou fallback manual). Idempotente: não rechama a API se `status_processamento` já é `concluido`.
- **`ExtratoParserService`** (`app/services/extrato_parser_service.py`): Registry pattern, um provider por formato — `OfxParserProvider` (lib `ofxparse`) e `CsvParserProvider` (formato próprio documentado no código: colunas `data,descricao,valor,tipo`). Novo banco/formato = registrar um provider novo, sem tocar no resto.
- **`ConciliacaoMatcher`** (`app/services/conciliacao_matcher.py`): valor exato + tolerância de data configurável (padrão 5 dias) — nunca tolerância de valor. Três camadas: `automatico_exato` (valor e data iguais), `automatico_tolerancia` (valor igual, data dentro da janela), `parcial` (1 lançamento quita N parcelas via soma exata, busca por combinação bounded a até 8 candidatas). Duas contas idênticas no mesmo dia = ambíguo, não casa sozinho (fica pra conciliação manual, não implementada nesta versão).
  - **Escopo**: o caso inverso (N lançamentos somados quitando 1 parcela) ficou de fora — precisa de estado entre múltiplos lançamentos do mesmo lote, e o cronograma já autorizava cortar matching parcial se a tarde apertasse. O schema (`conciliacoes` N:N) já suporta isso quando for implementado.
- **`POST /extratos`** (multipart: conta bancária + formato + arquivo): salva o arquivo e enfileira `processar_importacao_extrato` (Celery) — parse + matching automático rodam em background. Idempotente via `UNIQUE(conta_bancaria_id, fitid)`: reimportar o mesmo extrato não duplica lançamento nem reprocessa conciliações já feitas.
- Testado ponta a ponta (API real + worker Celery real, não só unitário): upload de nota com chave real → XML baixado e parseado; CSV com 3 lançamentos (exato/tolerância/split) → 3 conciliações automáticas corretas; reimportação do mesmo CSV → zero duplicação.

## MCPs (claude-code-setup-financeiro.md)

Configurados em `.mcp.json` (project-scope, não versionado — contém a senha do banco):

- **Context7** e **mcp-server-chart**: testados manualmente, sobem sem erro.
- **Serena**: instalado via `uvx` (sem Docker) em vez do método Docker do documento original, já que esta máquina não tem Docker/WSL2. O servidor MCP sobe normalmente (23 ferramentas expostas, incluindo memória persistente do projeto). **Limitação conhecida**: o `serena project index` (pré-indexação simbólica via LSP) falha nesta máquina — o subprocesso do pyright/typescript-language-server morre ao inicializar. Suspeita: o caractere `&` no nome da pasta de perfil do Windows (`P&G Engenharia`), que já causou o mesmo tipo de problema com `npm`/`npx` e com o instalador do Postgres 15 hoje. Não bloqueia o projeto — memória (`write_memory`/`read_memory`) funciona; só as ferramentas de busca/edição simbólica (`find_symbol` etc.) ficam indisponíveis até isso ser resolvido (provavelmente só com um perfil de Windows sem caracteres especiais, ou rodando dentro do WSL2).
- **Postgres MCP**: conectado ao banco `pgfinance`. O pacote oficial (`@modelcontextprotocol/server-postgres`) está **deprecated** pelos mantenedores — funciona, mas vale reavaliar uma alternativa mantida ativamente.

Para reconfigurar em outra máquina, ver os comandos em `claude-code-setup-financeiro.md` (Serena precisa do `uvx --python 3.12 --from git+https://github.com/oraios/serena ...` em vez do Docker, se Docker não estiver disponível).

## Status

### Bloco "Hoje à noite" — concluído

- [x] docker-compose.yml (Postgres 15 + Redis) — pronto para quando houver Docker
- [x] Migration inicial do Alembic aplicando `schema.sql` literalmente (sem redesenho) — aplicada e validada (12 tabelas)
- [x] Scaffold FastAPI por camada (routers/services/models/workers/core)
- [x] Scaffold React + Vite + TypeScript + Tailwind
- [x] Auth JWT com os 4 papéis — testado (login, RBAC leitura vs. escrita)
- [x] CRUDs: parceiros, centros de custo, contas bancárias (API + telas) — testados ponta a ponta no navegador
- [x] Os 4 MCPs configurados e respondendo (Serena com a limitação de indexação acima)

### Bloco "Amanhã de manhã" — concluído

- [x] `DiaUtilCalculator` com 8 testes unitários
- [x] `RecorrenciaService` com 14 testes unitários (todas periodicidades, as duas condições de parada, ajuste de dia útil, divisão de valor sem perder centavo) — pegou e corrigiu um bug real de acúmulo de `relativedelta`
- [x] Contas a pagar/receber completo: CRUD manual, baixa manual, anexo de boleto, dashboard de vencimento (RF11) — testado ponta a ponta via API e no navegador
- [x] Lançamentos recorrentes: CRUD + geração automática de parcelas — testado via API e UI
- [x] Upload de PDF de nota fiscal + extração de chave por regex (sem API externa ainda) + fallback de chave manual + idempotência (409 em chave duplicada) — testado ponta a ponta com PDF real
- [x] Todos os testes passando

### Bloco "Amanhã à tarde" — concluído

- [x] API de consulta de NFe (opção 3, sem certificado) contratada e testada contra o provedor real (Meu Danfe) com chave de acesso real — busca, polling, download de XML, parse de emitente/valor/data
- [x] `ExtratoParserService` (Registry: OFX via `ofxparse`, CSV em formato próprio) com 9 testes unitários
- [x] `ConciliacaoMatcher` (exato + tolerância de data + parcial/split) com 14 testes unitários — nunca tolerância de valor
- [x] `NfeConsultaClient` com 10 testes unitários (HTTP mockado) + validação real contra a API
- [x] Celery com as 2 tasks essenciais (`processar_nota_fiscal`, `processar_importacao_extrato`) rodando num worker real (`--pool=solo`, Windows)
- [x] Upload de nota fiscal → Celery → API real → XML → parse, testado ponta a ponta
- [x] Importação de extrato CSV → Celery → matching automático (exato/tolerância/parcial) → baixa automática das contas, testado ponta a ponta com idempotência confirmada (reimportação não duplica)
- [x] 60 testes passando no total

### Bloco "Amanhã à noite" — concluído

- [x] Revisão de segurança e edge cases — 5 problemas achados e corrigidos:
  - Valores monetários (`valor`, `valor_pago`, `valor_parcela`, `valor_total`) aceitavam negativo/zero — adicionado `gt=0` nos schemas
  - `numero_ocorrencias`/`intervalo_dias`/`numero_parcelas` sem validação de mínimo — adicionado `ge=1`
  - Senha de usuário sem tamanho mínimo (nem máximo — bcrypt trava acima de 72 bytes com erro 500 em vez de validação limpa) — adicionado `min_length=8, max_length=72`
  - Upload de arquivo sem limite de tamanho (risco de esgotar disco) — adicionado limite de 15MB
  - Conferido: RBAC presente em 100% dos endpoints de escrita, segredos (`.env`, `.mcp.json`) fora do git, `/storage` não vaza nada além do que foi intencionalmente enviado
- [x] Revisão visual de todas as telas — achado e corrigido: rótulo de status de nota fiscal ainda dizia "(próximo bloco)" pra consulta de API, que já estava funcionando; adicionado botão "Tentar de novo" pra notas com erro na consulta (endpoint já existia, só não estava na tela)
- [x] [`ROTEIRO_APRESENTACAO.md`](ROTEIRO_APRESENTACAO.md) — roteiro de demo com timing, o que mostrar em cada tela, e perguntas prováveis
- [x] **Auditoria completa contra o CLAUDE.md** (pedida explicitamente) — confirmado 100% de aderência em: regra de dia útil isolada, recorrência com as duas condições de parada, conciliação sem tolerância de valor, dinheiro sempre `Decimal`, contas a pagar/receber na mesma tabela, idempotência, Registry pattern, Result objects, RBAC, escopo fora do MVP respeitado. **Um gap real encontrado e corrigido**: o upload de nota fiscal exigia digitar fornecedor/valor/data manualmente mesmo com a API de consulta já funcionando — o CLAUDE.md e a documentação são explícitos ("único input manual é o PDF", "preenche fornecedor/valor/data automaticamente"). Corrigido:
  - `POST /notas-fiscais` agora só exige o PDF + centro de custo + tipo (pagar/receber) — os únicos campos que a nota não tem como inferir sozinha.
  - Quando a chave é achada no PDF e nenhum campo é preenchido na mão: a nota é criada com um parceiro "sentinela" temporário (satisfaz a FK `NOT NULL` do schema, sem redesenhá-lo) enquanto a API resolve; a task do Celery então **acha ou cria automaticamente o parceiro pelo CNPJ do XML**, preenche valor/data reais, e só então gera as parcelas — sem precisar do fornecedor pré-cadastrado.
  - Se a API falhar (chave inválida/não encontrada), a nota fica visível com status "Erro na consulta" e o parceiro sentinela, em vez de simplesmente desaparecer — o botão "Tentar de novo" já existente cobre o retry.
  - Se o usuário preferir preencher na mão (ou a chave não for achada no PDF), o comportamento anterior continua idêntico — nada quebrou pra quem já usava assim.
  - Testado ponta a ponta com a chave de acesso real: upload só com PDF → fornecedor "GCS Comercial LTDA" criado sozinho pelo CNPJ do XML → valor e data reais preenchidos → parcela gerada já com o ajuste de dia útil (05/09, sábado → 08/09, segunda).
- [x] **Nova regra de negócio** (pedida pelo usuário): parcelamento de nota fiscal já deixa todas as parcelas planejadas prontas automaticamente (já existia via `RecorrenciaService`) — faltava só a **tela** para anexar boleto por parcela antes da baixa, pra servir de revisão do lançamento. Adicionado: botão "Anexar boleto" no Dashboard (por parcela, além do "Dar baixa" que já existia) e uma visão expansível "ver parcelas" na tela de Notas Fiscais mostrando todas as parcelas geradas por uma nota com o mesmo controle de anexar boleto — essa é a tela de revisão do lançamento.
