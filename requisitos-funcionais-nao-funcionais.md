# Requisitos — Finance P&G

## Requisitos Funcionais (RF)

| # | Requisito |
|---|---|
| RF01 | O sistema deve permitir login com 4 perfis de acesso: financeiro, admin (donos), master (TI), sub. |
| RF02 | O sistema deve permitir cadastro de contas bancárias da empresa (2 a 3 contas). |
| RF03 | O sistema deve permitir importar extrato bancário nos formatos OFX e CSV. |
| RF04 | O sistema deve conciliar automaticamente lançamentos do extrato com notas fiscais e contas a pagar/receber, por valor exato com tolerância de data, incluindo matching parcial (1 pagamento para N parcelas ou N pagamentos para 1 parcela). Divergências não resolvidas automaticamente ficam disponíveis para conciliação manual. |
| RF05 | O sistema deve permitir cadastro de nota fiscal via upload de PDF (DANFE), extraindo automaticamente a chave de acesso e buscando o XML oficial via API externa, preenchendo fornecedor, valor e data de emissão sem digitação manual. Caso a chave não seja identificada no PDF, permite inserção manual da chave como alternativa. |
| RF06 | O sistema deve permitir classificar despesas como fixas ou variáveis, e como parceladas (com número de parcelas), além de exigir centro de custo em toda nota ou despesa lançada. |
| RF07 | O sistema deve gerar automaticamente as parcelas de contas a pagar/receber a partir de uma nota fiscal parcelada ou de um lançamento recorrente configurado. |
| RF08 | O sistema deve permitir configurar lançamentos recorrentes definindo periodicidade (mensal, quinzenal, semanal, anual ou personalizada) e quantidade de ocorrências ou data final. Caso a data de vencimento calculada caia em sábado ou domingo, o sistema deve ajustá-la automaticamente para o próximo dia útil. |
| RF09 | O sistema deve permitir dar baixa em contas a pagar/receber manualmente ou automaticamente via conciliação bancária. |
| RF10 | O sistema deve permitir anexar o arquivo do boleto e seus dados (linha digitável, código de barras) a cada parcela de conta a pagar. |
| RF11 | O sistema deve exibir um painel com as contas a pagar/receber por prazo de vencimento (vencendo hoje, na semana, em atraso). |
| RF12 | O sistema deve permitir buscar notas fiscais e despesas cadastradas por fornecedor, período, centro de custo ou status. |
| RF13 | O sistema deve permitir cadastrar projetos e vincular funcionários contratados a um projeto, registrando data de contratação e de demissão. |
| RF14 | O sistema deve permitir configurar receita recorrente vinculada a um projeto/contrato de cliente (ex: faturamento por medição quinzenal/mensal), com encerramento automático na data de fim do contrato. |
| RF15 | O sistema deve permitir cadastro de parceiros (fornecedores e clientes) e de centros de custo. |

## Requisitos Não Funcionais (RNF)

| # | Requisito |
|---|---|
| RNF01 | O backend deve ser desenvolvido em Python (FastAPI) com banco de dados PostgreSQL; o frontend em React. |
| RNF02 | Tarefas demoradas ou dependentes de serviço externo (extração de nota fiscal, importação de extrato, geração de recorrência) devem ser processadas de forma assíncrona (fila Celery + Redis), sem bloquear a resposta da interface. |
| RNF03 | O reprocessamento de uma tarefa assíncrona (ex: nova tentativa após falha) não deve gerar duplicidade de dados (idempotência garantida por identificadores únicos, ex: chave de acesso da nota, ID da transação bancária). |
| RNF04 | O sistema deve suportar de forma confortável até 20 usuários simultâneos com baixo volume de lançamentos, rodando em VPS com no mínimo 2 vCPU e 4 GB de RAM. |
| RNF05 | O acesso ao sistema deve ser autenticado (JWT) e as ações disponíveis devem respeitar o perfil de acesso do usuário. |
| RNF06 | Toda data de vencimento ajustada pela regra de dia útil deve preservar a data original para fins de auditoria. |
| RNF07 | Todo valor monetário deve ser armazenado e calculado em tipo decimal exato (nunca ponto flutuante), para evitar erro de arredondamento. |
| RNF08 | As regras de negócio críticas (cálculo de dia útil, geração de recorrência, matching de conciliação) devem ser isoladas em camada de serviço testável independentemente da camada web. |
| RNF09 | O sistema é de uso interno de uma única empresa (sem suporte a multiempresa nesta versão). |
| RNF10 | O leitor de extrato bancário deve ser estruturado de forma que suportar um novo formato ou banco não exija alterar a lógica central de conciliação (padrão plugável). |

## Fora do escopo desta versão (roadmap)

- Conexão bancária automática via Open Finance (substituindo o import manual de OFX/CSV).
- Captação automática de nota fiscal via certificado digital A1 + Manifestação do Destinatário (substituindo a consulta por API paga).
- Suporte a múltiplas empresas (multiempresa).
- OCR para extração de chave de acesso em PDFs escaneados/sem camada de texto.
