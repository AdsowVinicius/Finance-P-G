# Documentação — Finance P&G

## 1. Requisitos (Etapa 1)

- **Uso**: interno, empresa única (P&G Engenharia). Sem multiempresa.
- **Perfis de acesso**: `financeiro`, `admin` (donos), `master` (TI), `sub` (nível abaixo dos donos).
- **Contas bancárias**: 2 a 3.
- **Stack**: Python + FastAPI + PostgreSQL. Frontend a decidir na Etapa 3.
- **Extrato bancário (MVP)**: import manual de OFX/CSV. Open Finance real (conexão automática via agregador homologado tipo Pluggy/Belvo) fica pra fase 2 — não é viável credenciar isso até amanhã.
- **Notas fiscais**: entrada via XML/PDF. Parcelamento extraído automaticamente. Campos manuais mínimos: fornecedor + valor.
- **Conciliação**: matching por **valor exato**, com **tolerância ampla de data** (nota pode ser emitida dias antes do pagamento) e **suporte a matching parcial** (split de pagamento).
- **Despesas**: marcação fixa/variável, parcelamento gera recorrência automaticamente.
- **Contas a pagar**: dashboard de "quanto vence em quantos dias" é prioridade real (dor: juros por atraso). Boletos entram na mesma lista, com baixa manual (checkbox) ou automática via conciliação.
- **Busca**: notas/despesas precisam ser buscáveis no banco (hoje é Excel + pasta).
- **Centro de custo**: obrigatório em toda nota/despesa.
- **Escopo adicional (a avaliar na Etapa 4 se cabe no prazo)**: folha de mão de obra por projeto (contratação/demissão), e receita recorrente de cliente até o fim do contrato (ex: medições quinzenais/mensais).

## 2. Modelagem do banco (Etapa 2)

Arquivos de referência:
- `schema.sql` — DDL completo em PostgreSQL, com comentários de decisão de design.
- `schema-der.mermaid` — Diagrama Entidade-Relacionamento físico (com atributos, tipos, PK/FK).
- `schema-mer.mermaid` — Modelo Entidade-Relacionamento conceitual (entidades e relacionamentos, sem atributos).

### Decisões de design principais

1. **Fornecedor e cliente na mesma tabela** (`parceiros`, com campo `tipo`) — evita duplicação, a mesma pessoa jurídica pode ser as duas coisas.
2. **Regra de dia útil auditável**: toda parcela guarda `data_vencimento_original` (data pura) e `data_vencimento` (após ajuste de fim de semana/feriado). O cálculo em si vive 100% na aplicação, num serviço único `DiaUtilCalculator` (lib `workalendar`, cobre feriados nacionais BR). Não existe tabela de feriados no MVP.
3. **Recorrência com duas condições de parada**: `numero_ocorrencias` (fixo, ex: nota em 3x) OU `data_fim` (aberto, ex: salário/contrato que roda "enquanto durar") — o que vier primeiro encerra a recorrência.
4. **Contas a pagar e a receber na mesma tabela** (`contas_financeiras`, com `tipo_operacao`) — mesma lógica de dashboard de vencimento serve pras duas.
5. **Matching parcial de conciliação via tabela de junção N:N** (`conciliacoes`) — permite 1 pagamento quitar N parcelas, ou N pagamentos quitarem 1 parcela, sem gambiarra.
6. **Projetos como eixo de custo/receita**: `projetos` liga mão de obra contratada (`funcionarios`) e contrato de cliente com faturamento por medição (`lancamentos_recorrentes.projeto_id`) sob o mesmo motor de recorrência.
7. **Reimportação segura de extrato**: `lancamentos_extrato` tem `UNIQUE(conta_bancaria_id, fitid)` — reimportar o mesmo OFX não duplica lançamento.

### Origem do XML de nota fiscal — DECIDIDO para o MVP

**Opção 3 escolhida**: provedor terceirizado (ex: NFe.io "Consulta Irrestrita"). API REST — chave de 44 dígitos entra, XML oficial sai, sem certificado digital, sem precisar ser parte da nota. Viável pro prazo, cobrança por consulta (cotar valor atual com o provedor). Usa os mesmos campos já modelados (`arquivo_xml_path`, `dados_extraidos_xml`) — zero impacto no schema.

Portal público SEFAZ ficou descartado: exige captcha em toda consulta, não automatizável.

### Fluxo de cadastro de nota fiscal — IMPLEMENTADO no MVP

Este é o fluxo real de entrada de nota, substituindo "digitar fornecedor + valor":

1. Usuário sobe o **PDF** (DANFE) da nota — único input manual.
2. Sistema extrai a **chave de acesso** (44 dígitos) do texto do PDF via regex.
3. Sistema chama a **API de consulta** (opção 3) com essa chave.
4. API retorna o **XML oficial** da nota.
5. Sistema faz o **parse do XML** e preenche fornecedor, valor, data de emissão, parcelamento automaticamente (`notas_fiscais`).
6. PDF e XML ficam **vinculados ao mesmo lançamento** (`arquivo_pdf_path`, `arquivo_xml_path`, `dados_extraidos_xml`) — nenhum arquivo solto.

**Fallback (não bloqueante)**: se a chave não for encontrada no texto do PDF (ex: PDF escaneado/foto, sem camada de texto), o sistema pede pra colar a chave manualmente. **OCR para esse caso fica fora do MVP** — é exceção rara, não vale o tempo de implementação até amanhã.

### Boleto anexado à parcela — IMPLEMENTADO no MVP

Quando a nota é despesa, cada parcela (`contas_financeiras`) pode ter um **arquivo de boleto anexado** (`boleto_arquivo_path`), além da linha digitável/código de barras já modelados. A `data_vencimento` que já existia na parcela é a mesma usada pro relatório — não é campo novo, é reaproveito do que já foi desenhado pro dashboard de vencimento.

Isso fecha o relatório de contas a pagar de forma direta: "boletos vencendo essa semana / hoje / atrasados" é uma query simples em `contas_financeiras` filtrando por `data_vencimento` e `boleto_arquivo_path IS NOT NULL`, usando o índice `idx_contas_vencimento_status` que já existe. Cada boleto na lista já vem com o PDF anexado clicável — resolve a dor de "hoje é Excel e pasta, difícil de achar".

## 3. Arquitetura (Etapa 3)

**Decisões de infraestrutura**: React (Vite) separado consumindo API FastAPI. Hospedagem ainda não definida (fica agnóstico — Docker Compose local pra desenvolver, decide o destino depois sem travar o código). Processamento em background com **Celery + Redis**.

> ⚠️ Registrado pra Etapa 4: React separado + Celery/Redis é a combinação com mais peça de infraestrutura pra montar (broker, worker, fila, auth entre front/back) — entra com peso real na conversa de corte de escopo.

Diagrama de referência: `arquitetura.mermaid`.

### Camadas

1. **Frontend** — React SPA, consome a API via REST.
2. **API (FastAPI)** — routers finos por domínio (auth, notas fiscais, contas a pagar/receber, extrato/conciliação, funcionários/projetos, relatórios). Só validação de entrada e orquestração — nenhuma regra de negócio aqui.
3. **Camada de Serviço** — regra de negócio pura, sem dependência de FastAPI, testável isolada:
   - `DiaUtilCalculator` — único lugar que decide dia útil (workalendar).
   - `RecorrenciaService` — gera as parcelas de `contas_financeiras` a partir de `lancamentos_recorrentes`, parando em `numero_ocorrencias` ou `data_fim`.
   - `ConciliacaoMatcher` — motor de matching (exato, tolerância de data, parcial/split).
   - `NotaFiscalService` — orquestra extração de chave do PDF, chamada da API externa, parse do XML.
   - `ExtratoParserService` — Registry pattern com provider plugável por formato (OFX, CSV) e, no futuro, por banco.
4. **Workers assíncronos (Celery + Redis)**:
   - `processar_nota_fiscal` — roda o pipeline PDF→chave→API→XML sem travar a resposta do upload. Idempotente via `chave_acesso UNIQUE` (reprocessar não duplica).
   - `processar_importacao_extrato` — parseia o arquivo e dispara o `ConciliacaoMatcher` em cada linha.
   - `gerar_ocorrencias_recorrencia` — materializa parcelas futuras.
   - Celery Beat — job diário que varre boletos a vencer (usa o mesmo índice de vencimento do dashboard).
5. **Banco (PostgreSQL)** — schema já fechado nas etapas 1-2.

### Rastreio do pipeline assíncrono (mudança de schema desta etapa)

Adicionado `status_processamento` em `notas_fiscais` (enum: `aguardando_extracao`, `chave_nao_encontrada`, `consultando_api`, `concluido`, `erro_api`) — necessário pra saber em que ponto do pipeline uma nota está e permitir retry manual sem duplicar chamada à API paga. Reflete no `schema.sql` e no `schema-der.mermaid`.

### Testes

- **Unitários** (sem banco, sem framework) nos serviços de maior risco: `DiaUtilCalculator` (casos de sábado/domingo/feriado), `RecorrenciaService` (parada por ocorrências vs. por data), `ConciliacaoMatcher` (exato, tolerância, parcial/split).
- **Integração leve** nos endpoints críticos (upload de nota, importação de extrato) contra banco de teste.
- **Fora do MVP**: E2E completo (Playwright) — fica pra depois do prazo.

## 4. Plano de execução até amanhã (Etapa 4)

**Janela real disponível**: hoje à noite + amanhã dia inteiro (~14-16h úteis, trabalhando sozinho com Claude Code).

**Cortes de escopo — vão pro roadmap (seção 5), não são descartados**:
- Funcionários/Projetos (RF13) — contratação/demissão de mão de obra por projeto.
- Receita recorrente por contrato/medição (RF14) — schema/engine já prontos, só a tela dedicada fica pra depois.
- Celery Beat (alerta diário automático de boleto) — vira botão manual de atualizar no dashboard.
- Matching parcial na conciliação — corte de última hora se a tarde de amanhã apertar; prioridade é exato + tolerância de data.

### Cronograma

| Bloco | Entregável |
|---|---|
| Hoje à noite | Docker Compose (Postgres+Redis), scaffold FastAPI+React, migração do schema, auth JWT (4 papéis), CRUDs base (parceiros, centro de custo, contas bancárias) |
| Amanhã de manhã | `DiaUtilCalculator` + `RecorrenciaService` com testes, contas a pagar/receber completo (CRUD, baixa manual, anexo de boleto, dashboard de vencimento), upload de PDF + extração de chave (sem API externa ainda) |
| Amanhã à tarde | **Primeiro**: contratar/testar a API de consulta de NFe (opção 3) — único item que depende de terceiro. Depois: parser OFX/CSV + `ConciliacaoMatcher` (exato+tolerância) com testes, Celery com as 2 tasks essenciais |
| Amanhã à noite | Telas React (login, dashboard, notas fiscais, conciliação), teste ponta a ponta com dado real, ensaio da apresentação |

**Por que a API de NFe entra logo na tarde de amanhã**: é o único componente fora do controle direto (cadastro/aprovação/chave de acesso de terceiro). Deixar pro fim do dia elimina a margem de reação se travar.

## 5. Roadmap / Melhorias futuras (fora do MVP)

### 5.1 Captação automática de NFe via Certificado Digital A1 + Manifestação do Destinatário

**O que é**: em vez de depender de uma API paga por consulta (opção 3, em uso no MVP), a empresa obtém um certificado digital A1 própria e se cadastra na **Manifestação do Destinatário** — mecanismo oficial da SEFAZ que notifica automaticamente o CNPJ de toda NFe emitida contra ele. Nenhuma chave de acesso precisa ser digitada ou colada: o sistema consulta o webservice periodicamente e recebe as notas assim que os fornecedores emitem.

**Por que vale a pena depois**:
- Elimina custo por consulta (API paga vira desnecessária a longo prazo).
- Elimina a dependência de alguém copiar/colar a chave de acesso — captação 100% passiva.
- É o mecanismo "oficial" reconhecido pela Receita Federal, dado mais robusto pra auditoria e compliance fiscal.

**Por que ficou fora do MVP**:
- Exige emissão/renovação de certificado digital A1 (processo e custo à parte, dias de prazo).
- Integração é via webservice SOAP da SEFAZ (mais complexa que a API REST simples da opção 3).
- Não cabia no prazo de entrega desta semana.

**Posicionamento pra apresentação**: enquadrar como evolução natural do módulo de notas fiscais — "hoje a captação é sob demanda via API, a evolução é captação automática e passiva direto da Receita Federal, com o mesmo modelo de dados por trás (nenhuma migração de schema necessária)".

### 5.2 Lançamento e consulta via WhatsApp

**O que é**: integração com WhatsApp Business API permitindo conversar direto com o sistema pelo WhatsApp — tanto pra **consultar** (reaproveita o mesmo motor do assistente RF16) quanto pra **lançar despesa informal** em linguagem natural. Ex: usuário manda "gastei 20 reais aqui na padaria do seu Zé" → sistema interpreta e cria um **pré-lançamento** (saída, valor R$20, fornecedor "Padaria do seu Zé") como pendente de revisão — não lança direto, porque falta centro de custo obrigatório e confirmação do fornecedor. O financeiro confirma/completa dentro do sistema antes de virar lançamento de verdade.

**Por que vale a pena depois**: captura despesa informal (sem nota fiscal) no momento em que acontece, no canal que o usuário já usa o dia inteiro — reduz o "esqueci de lançar" que hoje se perde no Excel.

**Por que ficou fora do MVP**: exige conta comercial no WhatsApp Business API (Meta Cloud API ou provedor tipo Twilio/Z-API), webhook público, vínculo do número de WhatsApp ao usuário do sistema, e um fluxo de pré-lançamento/confirmação que ainda não existe na modelagem — é extensão real de escopo, não ajuste pequeno.

**Reaproveitamento técnico**: mesmo motor de linguagem natural do RF16 (Claude Haiku 4.5), só troca o canal de entrada e adiciona uma função de escrita (`criar_pre_lancamento`) às funções de leitura já existentes.
