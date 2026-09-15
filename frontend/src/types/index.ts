export type PapelUsuario = 'financeiro' | 'admin' | 'master' | 'sub'

export interface Usuario {
  id: string
  nome: string
  email: string
  papel: PapelUsuario
  ativo: boolean
  telefone_whatsapp: string | null
}

export type TipoParceiro = 'fornecedor' | 'cliente' | 'ambos'

export interface Parceiro {
  id: string
  tipo: TipoParceiro
  cnpj_cpf: string | null
  razao_social: string
  nome_fantasia: string | null
  email: string | null
  telefone: string | null
  ativo: boolean
}

export interface CentroCusto {
  id: string
  codigo: string | null
  nome: string
  ativo: boolean
}

export interface ContaBancaria {
  id: string
  apelido: string
  banco: string | null
  agencia: string | null
  numero_conta: string | null
  tipo_conta: string | null
  saldo_inicial: string
  ativo: boolean
}

export type TipoOperacaoNota = 'entrada' | 'saida'
export type Periodicidade = 'mensal' | 'quinzenal' | 'semanal' | 'anual' | 'personalizada_dias'
export type StatusConta = 'pendente' | 'pago' | 'atrasado' | 'cancelado'
export type FormaBaixa = 'manual' | 'conciliacao_automatica'
export type FormaPagamento = 'pix' | 'dinheiro' | 'cartao_credito' | 'cartao_debito' | 'boleto' | 'transferencia' | 'outro'
export type TipoNota = 'nfe' | 'nfse'
export type StatusNota = 'pendente' | 'parcialmente_conciliada' | 'conciliada' | 'cancelada'
export type StatusProcessamentoNota =
  | 'aguardando_extracao'
  | 'chave_nao_encontrada'
  | 'consultando_api'
  | 'concluido'
  | 'erro_api'

export interface LancamentoRecorrente {
  id: string
  tipo_operacao: TipoOperacaoNota
  descricao: string
  parceiro_id: string | null
  centro_custo_id: string | null
  conta_bancaria_id: string | null
  valor_parcela: string
  numero_ocorrencias: number | null
  data_fim: string | null
  periodicidade: Periodicidade
  intervalo_dias: number | null
  data_inicio: string
  ativo: boolean
}

export interface ContaFinanceira {
  id: string
  tipo_operacao: TipoOperacaoNota
  lancamento_recorrente_id: string | null
  nota_fiscal_id: string | null
  parceiro_id: string
  centro_custo_id: string | null
  descricao: string
  numero_parcela: number
  total_parcelas: number
  valor: string
  data_vencimento_original: string
  data_vencimento: string
  data_pagamento: string | null
  valor_pago: string | null
  juros_pago: string | null
  status: StatusConta
  forma_baixa: FormaBaixa | null
  forma_pagamento: FormaPagamento | null
  boleto_linha_digitavel: string | null
  boleto_codigo_barras: string | null
  boleto_arquivo_path: string | null
  conta_bancaria_id: string | null
}

export interface DashboardVencimento {
  atrasado: ContaFinanceira[]
  hoje: ContaFinanceira[]
  semana: ContaFinanceira[]
  total_atrasado: string
  total_hoje: string
  total_semana: string
}

export type FormatoExtrato = 'ofx' | 'csv'
export type StatusImportacao = 'processando' | 'concluido' | 'erro'
export type TipoLancamentoExtrato = 'credito' | 'debito'
export type StatusConciliacaoLinha = 'pendente' | 'conciliado' | 'parcial' | 'divergente' | 'ignorado'

export interface ExtratoImportado {
  id: string
  conta_bancaria_id: string
  formato: FormatoExtrato
  status: StatusImportacao
  mensagem_erro: string | null
  created_at: string
}

export interface LancamentoExtrato {
  id: string
  extrato_importado_id: string
  conta_bancaria_id: string
  data: string
  descricao: string | null
  valor: string
  tipo: TipoLancamentoExtrato
  fitid: string | null
  status_conciliacao: StatusConciliacaoLinha
}

export type StatusPreLancamentoWhatsapp = 'pendente_revisao' | 'confirmado' | 'descartado'

export interface PreLancamentoWhatsapp {
  id: string
  telefone: string
  usuario_id: string | null
  mensagem_original: string
  tipo_operacao: TipoOperacaoNota
  valor: string | null
  descricao: string | null
  fornecedor_texto: string | null
  forma_pagamento: FormaPagamento | null
  parceiro_id: string | null
  centro_custo_id: string | null
  conta_financeira_id: string | null
  status: StatusPreLancamentoWhatsapp
  created_at: string
}

export interface ResumoIndicadores {
  saldo_mes: string
  total_a_pagar_aberto: string
  total_a_receber_aberto: string
  contas_atrasadas_qtd: number
  contas_atrasadas_total: string
  juros_pagos_mes: string
}

export interface PontoEvolucaoMensal {
  mes: string
  total_pago: string
  total_recebido: string
}

export interface ItemCentroCusto {
  centro_custo: string
  total: string
}

export interface ItemStatusNota {
  status: StatusNota
  quantidade: number
}

export interface LogAuditoria {
  id: string
  usuario_id: string
  acao: string
  entidade: string
  entidade_id: string
  dados_antes: Record<string, unknown> | null
  dados_depois: Record<string, unknown> | null
  created_at: string
}

export interface NotaFiscal {
  id: string
  parceiro_id: string
  centro_custo_id: string | null
  tipo: TipoNota
  tipo_operacao: TipoOperacaoNota
  numero_nota: string | null
  serie: string | null
  chave_acesso: string | null
  valor_total: string
  data_emissao: string
  despesa_fixa: boolean
  despesa_parcelada: boolean
  numero_parcelas: number
  arquivo_xml_path: string | null
  arquivo_pdf_path: string | null
  status: StatusNota
  status_processamento: StatusProcessamentoNota
}
