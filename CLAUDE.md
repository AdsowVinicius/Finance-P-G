# CLAUDE.md — Finance P&G

## Contexto do projeto

Sistema de uso interno da P&G Engenharia (Pindamonhangaba/SP), sem multiempresa. Substitui controle manual em Excel/pasta por conciliação bancária, notas fiscais e contas a pagar/receber automatizadas. Prazo: MVP funcional de ponta a ponta, sem gambiarra visível, em ~1,5 dia.

## Stack

- **Backend**: Python 3.12 + FastAPI + PostgreSQL 15+ + SQLAlchemy + Alembic
- **Fila**: Celery + Redis
- **Frontend**: React (Vite) + Tailwind
- **Libs chave**: `ofxparse` (extrato), `lxml`/`nfelib` (XML de NFe), `workalendar` (dia útil BR), `Decimal` (dinheiro — nunca float)

## Regras de negócio centrais — não duplicar em múltiplos lugares

1. **Dia útil**: sábado/domingo (e feriados nacionais) → empurra pro próximo dia útil. Vive SÓ em `DiaUtilCalculator`. Toda parcela guarda `data_vencimento_original` (pura) e `data_vencimento` (ajustada) — nunca sobrescrever a original.
2. **Recorrência**: para em `numero_ocorrencias` OU `data_fim`, o que vier primeiro. Motor: `RecorrenciaService`, sempre passando pelo `DiaUtilCalculator` pra cada ocorrência gerada.
3. **Conciliação**: matching por **valor exato** + **tolerância de data** (nunca tolerância de valor). Suporta matching parcial via tabela de junção `conciliacoes` (N:N — um lançamento pode casar com várias parcelas e vice-versa). Motor: `ConciliacaoMatcher`.
4. **Nota fiscal**: usuário sobe só o PDF → sistema extrai a chave de acesso (regex, 44 dígitos) → chama a API de consulta externa (opção 3 — sem certificado digital) → recebe o XML → preenche fornecedor/valor/data automaticamente. Fallback: usuário cola a chave manualmente se a extração falhar (não bloqueante). Orquestrado por `NotaFiscalService`, roda em task Celery, **idempotente via `chave_acesso UNIQUE`** — nunca chamar a API de novo pra uma chave já resolvida.
5. **Dinheiro**: sempre `Decimal`/`NUMERIC`, nunca `float`, em nenhuma camada.
6. **Contas a pagar e a receber**: mesma tabela `contas_financeiras` (campo `tipo_operacao`) — não criar tabelas separadas.

## Arquitetura (camadas)

API (FastAPI, fina, só valida e orquestra) → Serviço (regra de negócio pura, testável sem FastAPI/banco) → Workers assíncronos (Celery — tudo que é lento ou depende de terceiro) → PostgreSQL.

Diagrama completo: `arquitetura.mermaid`.

Serviços da camada de negócio: `DiaUtilCalculator`, `RecorrenciaService`, `ConciliacaoMatcher`, `NotaFiscalService`, `ExtratoParserService` (Registry pattern — novo banco/formato de extrato não deve tocar no core).

## Schema

Fonte da verdade: `schema.sql` (já fechado e validado — não redesenhar, só migrar). Diagramas de apoio: `schema-der.mermaid` (físico, com atributos/tipos) e `schema-mer.mermaid` (conceitual, só entidades/relacionamentos).

## Padrões de código

- Registry pattern para providers plugáveis (extrato bancário).
- Result objects pra retorno estruturado de operações (sucesso/erro), evitar exceptions pra fluxo de controle normal.
- Todo job assíncrono é idempotente — reprocessar nunca duplica dado.
- Regra de negócio nunca espalhada pelo código — um serviço, uma responsabilidade, um lugar só.

## Escopo do MVP atual

Ver `requisitos-funcionais-nao-funcionais.md` pra lista completa.

**Dentro do MVP**: conciliação bancária (OFX/CSV), pipeline de nota fiscal (PDF→chave→API→XML), contas a pagar/receber com recorrência, boletos anexados, dashboard de vencimento.

**Fora do MVP (roadmap, não implementar agora)**: funcionários/projetos (mão de obra), receita recorrente por contrato/medição, Open Finance real, certificado digital A1 + Manifestação do Destinatário, multiempresa, OCR de PDF escaneado.

## Testes

Prioridade máxima, unitários, sem banco, sem framework: `DiaUtilCalculator`, `RecorrenciaService`, `ConciliacaoMatcher`. São os três pontos de maior risco de bug silencioso.

## Forma de trabalho

- Sessão nova em vez de resumida quando o contexto ficar pesado/longo.
- Revisão incremental (segurança + edge cases) ao final de cada módulo, antes de seguir pro próximo.
- Cronograma e ordem de execução: ver seção 4 de `documentacao-sistema-financeiro.md`.
