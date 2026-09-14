# Roteiro de apresentação — Finance P&G

Login de demo: `admin@pgengenharia.com.br` / `TrocarDepois123!` (papel `master`)

Antes de começar: suba os 4 serviços (`iniciar_redis.bat`, `iniciar_backend.bat`, `iniciar_frontend.bat`, `iniciar_celery.bat`) e abra `http://localhost:5173`.

## 1. Contexto (30s)

"Hoje isso é Excel + pasta de arquivo. Toda conciliação de banco, toda nota fiscal, todo boleto — manual. Construímos um sistema que automatiza as três dores que mais custam tempo: saber o que vence, lançar nota fiscal sem digitar tudo, e bater o extrato do banco com o que já era esperado."

## 2. Login e papéis (30s)

- Mostrar a tela de login.
- Mencionar os 4 papéis (`financeiro`, `admin`, `master`, `sub`) — `sub` só lê, os outros três escrevem.

## 3. Dashboard de vencimento — a dor #1 (1min)

- Ir direto pro Dashboard (tela inicial).
- "Isso aqui resolve a pergunta que mais custa tempo hoje: o que vence essa semana, o que já venceu. Três categorias: atrasado, hoje, na semana — cada uma com o total."
- Clicar em "Dar baixa" numa conta pra mostrar a baixa manual.
- Mencionar: baixa também acontece **automaticamente** via conciliação bancária (mostrar depois, passo 6).

## 4. Lançamento recorrente — regra de dia útil (1min)

- Ir em Recorrências → Novo lançamento recorrente.
- Criar um lançamento mensal, com data de início caindo num fim de semana (ex: um sábado).
- Salvar e mostrar em Dashboard que a parcela gerada foi automaticamente empurrada pro próximo dia útil — "isso é automático, sábado/domingo/feriado nacional nunca vira data de vencimento real."

## 5. Nota fiscal — o fluxo que mais economiza digitação (2min, a parte mais forte da demo)

- Ir em Notas Fiscais → Cadastrar nota fiscal.
- Subir um PDF de DANFE real (não escaneado).
- "O sistema lê o PDF, acha a chave de acesso de 44 dígitos sozinho via regex — sem digitar nada disso."
- Preencher só os campos mínimos (parceiro, centro de custo, valor, data, parcelamento) e salvar.
- Mostrar o status indo de "Consultando API..." pra "Concluída" em poucos segundos — "isso é uma chamada real pra um provedor terceirizado que devolve o XML oficial da nota, sem precisar de certificado digital."
- Se der tempo: mostrar o caso de PDF escaneado (chave não encontrada) → colar a chave manualmente como fallback.

## 6. Conciliação bancária — fechando o ciclo (2min)

- Ir em Extrato / Conciliação → Importar extrato.
- Subir um OFX ou CSV de exemplo com lançamentos que batem com contas já cadastradas.
- Mostrar o resultado: lançamentos com status "Conciliado".
- Voltar no Dashboard e mostrar que as contas correspondentes já aparecem como pagas — **automaticamente**, sem clicar em nada.
- Mencionar as 3 camadas de matching: valor exato + mesma data, valor exato + tolerância de data, e split (1 pagamento quitando várias parcelas de uma vez).
- "Reimportar o mesmo arquivo não duplica nada — o sistema reconhece que já processou."

## 7. Qualidade (30s, se o público for técnico)

- "As três regras de negócio mais arriscadas de dar bug silencioso — dia útil, recorrência, e o motor de conciliação — têm 60 testes automatizados cobrindo casos de borda: feriado emendando com fim de semana, recorrência que atravessa fevereiro, split de pagamento, tolerância de data sem nunca tolerar diferença de valor."
- Se quiser, mostrar `cd backend && .venv\Scripts\pytest tests\ -v` rodando ao vivo.

## 8. O que ficou fora do MVP (30s — antecipa perguntas)

- Funcionários/projetos (folha de mão de obra) e receita recorrente por contrato — schema já pronto, tela fica pra próxima fase.
- Certificado digital A1 + Manifestação do Destinatário — evolução natural da consulta de NFe atual (mesmo modelo de dados, zero migração).
- Conciliação manual pra casos ambíguos (duas contas idênticas no mesmo dia) — fica pendente, não quebra nada, só não concilia sozinho.

## Perguntas prováveis

**"Isso já tá em produção?"** — Rodando localmente, testado ponta a ponta com dado real (nota fiscal e API de consulta reais). Falta decidir hospedagem.

**"Quanto custa a consulta de nota fiscal?"** — R$0,03 por consulta no provedor atual (Meu Danfe). Praticamente irrelevante em volume.

**"E se a chave da nota não for encontrada no PDF?"** — Fallback manual: usuário cola a chave, não trava o cadastro.

**"O que acontece se o mesmo extrato for importado duas vezes por engano?"** — Nada duplica. Testado.
