import { Download, Search, X } from 'lucide-react'
import { useEffect, useState } from 'react'
import { api } from '../lib/api'
import { FORMA_PAGAMENTO_LABEL } from '../lib/formaPagamento'
import type { CentroCusto, ContaFinanceira, FormaPagamento, Parceiro, StatusConta, TipoOperacaoNota } from '../types'

const STATUS_LABEL: Record<StatusConta, string> = {
  pendente: 'Pendente',
  pago: 'Pago',
  atrasado: 'Atrasado',
  cancelado: 'Cancelado',
}

const STATUS_COR: Record<StatusConta, string> = {
  pendente: 'bg-slate-100 text-slate-700',
  pago: 'bg-emerald-100 text-emerald-800',
  atrasado: 'bg-red-100 text-red-800',
  cancelado: 'bg-slate-200 text-slate-500',
}

interface Filtros {
  tipoOperacao: TipoOperacaoNota | ''
  statusConta: StatusConta | ''
  parceiroId: string
  centroCustoId: string
  formaPagamento: FormaPagamento | ''
  dataInicio: string
  dataFim: string
  valorMin: string
  valorMax: string
  busca: string
}

const FILTROS_VAZIOS: Filtros = {
  tipoOperacao: '',
  statusConta: '',
  parceiroId: '',
  centroCustoId: '',
  formaPagamento: '',
  dataInicio: '',
  dataFim: '',
  valorMin: '',
  valorMax: '',
  busca: '',
}

function formatarMoeda(valor: string): string {
  return Number(valor).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })
}

function formatarData(data: string): string {
  const [ano, mes, dia] = data.split('-')
  return `${dia}/${mes}/${ano}`
}

function paramsDeFiltros(filtros: Filtros): Record<string, string> {
  const params: Record<string, string> = {}
  if (filtros.tipoOperacao) params.tipo_operacao = filtros.tipoOperacao
  if (filtros.statusConta) params.status_conta = filtros.statusConta
  if (filtros.parceiroId) params.parceiro_id = filtros.parceiroId
  if (filtros.centroCustoId) params.centro_custo_id = filtros.centroCustoId
  if (filtros.formaPagamento) params.forma_pagamento = filtros.formaPagamento
  if (filtros.dataInicio) params.data_inicio = filtros.dataInicio
  if (filtros.dataFim) params.data_fim = filtros.dataFim
  if (filtros.valorMin) params.valor_min = filtros.valorMin
  if (filtros.valorMax) params.valor_max = filtros.valorMax
  if (filtros.busca) params.busca = filtros.busca
  return params
}

export function RelatoriosPage() {
  const [filtros, setFiltros] = useState<Filtros>(FILTROS_VAZIOS)
  const [contas, setContas] = useState<ContaFinanceira[]>([])
  const [parceiros, setParceiros] = useState<Parceiro[]>([])
  const [centros, setCentros] = useState<CentroCusto[]>([])
  const [nomesParceiros, setNomesParceiros] = useState<Record<string, string>>({})
  const [carregando, setCarregando] = useState(true)
  const [exportando, setExportando] = useState(false)

  useEffect(() => {
    Promise.all([
      api.get<Parceiro[]>('/parceiros', { params: { apenas_ativos: false } }),
      api.get<CentroCusto[]>('/centros-custo'),
    ]).then(([parceirosRes, centrosRes]) => {
      setParceiros(parceirosRes.data)
      setCentros(centrosRes.data)
      setNomesParceiros(Object.fromEntries(parceirosRes.data.map((p) => [p.id, p.razao_social])))
    })
    buscar(FILTROS_VAZIOS)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  async function buscar(f: Filtros) {
    setCarregando(true)
    const { data } = await api.get<ContaFinanceira[]>('/contas-financeiras', { params: paramsDeFiltros(f) })
    setContas(data)
    setCarregando(false)
  }

  function limparFiltros() {
    setFiltros(FILTROS_VAZIOS)
    buscar(FILTROS_VAZIOS)
  }

  async function exportarCsv() {
    setExportando(true)
    try {
      const resposta = await api.get('/contas-financeiras/exportar-csv', {
        params: paramsDeFiltros(filtros),
        responseType: 'blob',
      })
      const url = window.URL.createObjectURL(new Blob([resposta.data]))
      const link = document.createElement('a')
      link.href = url
      link.download = `lancamentos_${new Date().toISOString().slice(0, 10)}.csv`
      document.body.appendChild(link)
      link.click()
      link.remove()
      window.URL.revokeObjectURL(url)
    } finally {
      setExportando(false)
    }
  }

  // entrada = despesa (a pagar), saida = receita (a receber) — schema.sql
  const totalDespesa = contas.filter((c) => c.tipo_operacao === 'entrada').reduce((s, c) => s + Number(c.valor), 0)
  const totalReceita = contas.filter((c) => c.tipo_operacao === 'saida').reduce((s, c) => s + Number(c.valor), 0)
  const totalJuros = contas.reduce((s, c) => s + (c.juros_pago ? Number(c.juros_pago) : 0), 0)

  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-slate-800">Relatórios</h2>
          <p className="text-sm text-slate-500">Busque e filtre todos os lançamentos, e exporte em CSV.</p>
        </div>
        <button
          onClick={exportarCsv}
          disabled={exportando}
          className="flex items-center gap-2 rounded bg-brand-700 px-3 py-1.5 text-sm text-white hover:bg-brand-800 disabled:opacity-50"
        >
          <Download size={16} />
          {exportando ? 'Exportando...' : 'Exportar CSV'}
        </button>
      </div>

      <div className="mb-4 rounded-xl bg-white p-4 shadow-sm ring-1 ring-slate-200/70">
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-600">Busca (descrição)</label>
            <input
              value={filtros.busca}
              onChange={(e) => setFiltros({ ...filtros, busca: e.target.value })}
              className="w-full rounded border border-slate-300 px-2 py-1.5 text-sm"
              placeholder="ex: coxinha"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-600">Tipo</label>
            <select
              value={filtros.tipoOperacao}
              onChange={(e) => setFiltros({ ...filtros, tipoOperacao: e.target.value as Filtros['tipoOperacao'] })}
              className="w-full rounded border border-slate-300 px-2 py-1.5 text-sm"
            >
              <option value="">Todos</option>
              <option value="entrada">Despesa</option>
              <option value="saida">Receita</option>
            </select>
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-600">Status</label>
            <select
              value={filtros.statusConta}
              onChange={(e) => setFiltros({ ...filtros, statusConta: e.target.value as Filtros['statusConta'] })}
              className="w-full rounded border border-slate-300 px-2 py-1.5 text-sm"
            >
              <option value="">Todos</option>
              {(Object.keys(STATUS_LABEL) as StatusConta[]).map((s) => (
                <option key={s} value={s}>
                  {STATUS_LABEL[s]}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-600">Parceiro</label>
            <select
              value={filtros.parceiroId}
              onChange={(e) => setFiltros({ ...filtros, parceiroId: e.target.value })}
              className="w-full rounded border border-slate-300 px-2 py-1.5 text-sm"
            >
              <option value="">Todos</option>
              {parceiros.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.razao_social}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-600">Centro de custo</label>
            <select
              value={filtros.centroCustoId}
              onChange={(e) => setFiltros({ ...filtros, centroCustoId: e.target.value })}
              className="w-full rounded border border-slate-300 px-2 py-1.5 text-sm"
            >
              <option value="">Todos</option>
              {centros.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.nome}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-600">Forma de pagamento</label>
            <select
              value={filtros.formaPagamento}
              onChange={(e) => setFiltros({ ...filtros, formaPagamento: e.target.value as Filtros['formaPagamento'] })}
              className="w-full rounded border border-slate-300 px-2 py-1.5 text-sm"
            >
              <option value="">Todas</option>
              {Object.entries(FORMA_PAGAMENTO_LABEL).map(([valor, label]) => (
                <option key={valor} value={valor}>
                  {label}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-600">Vencimento de</label>
            <input
              type="date"
              value={filtros.dataInicio}
              onChange={(e) => setFiltros({ ...filtros, dataInicio: e.target.value })}
              className="w-full rounded border border-slate-300 px-2 py-1.5 text-sm"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-600">Vencimento até</label>
            <input
              type="date"
              value={filtros.dataFim}
              onChange={(e) => setFiltros({ ...filtros, dataFim: e.target.value })}
              className="w-full rounded border border-slate-300 px-2 py-1.5 text-sm"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-600">Valor mínimo</label>
            <input
              type="number"
              step="0.01"
              value={filtros.valorMin}
              onChange={(e) => setFiltros({ ...filtros, valorMin: e.target.value })}
              className="w-full rounded border border-slate-300 px-2 py-1.5 text-sm"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-600">Valor máximo</label>
            <input
              type="number"
              step="0.01"
              value={filtros.valorMax}
              onChange={(e) => setFiltros({ ...filtros, valorMax: e.target.value })}
              className="w-full rounded border border-slate-300 px-2 py-1.5 text-sm"
            />
          </div>
        </div>
        <div className="mt-3 flex gap-2">
          <button
            onClick={() => buscar(filtros)}
            className="flex items-center gap-2 rounded bg-brand-700 px-4 py-1.5 text-sm text-white hover:bg-brand-800"
          >
            <Search size={14} />
            Buscar
          </button>
          <button
            onClick={limparFiltros}
            className="flex items-center gap-2 rounded bg-slate-100 px-4 py-1.5 text-sm text-slate-600 hover:bg-slate-200"
          >
            <X size={14} />
            Limpar filtros
          </button>
        </div>
      </div>

      <div className="mb-3 flex flex-wrap gap-4 text-sm">
        <span className="text-slate-600">
          <strong>{contas.length}</strong> lançamentos
        </span>
        <span className="text-emerald-700">
          Receitas: <strong>{formatarMoeda(String(totalReceita))}</strong>
        </span>
        <span className="text-red-700">
          Despesas: <strong>{formatarMoeda(String(totalDespesa))}</strong>
        </span>
        <span className="text-slate-800">
          Saldo: <strong>{formatarMoeda(String(totalReceita - totalDespesa))}</strong>
        </span>
        {totalJuros !== 0 && (
          <span className="text-orange-700">
            Juros/Desconto: <strong>{formatarMoeda(String(totalJuros))}</strong>
          </span>
        )}
      </div>

      <div className="overflow-x-auto rounded-xl bg-white shadow-sm ring-1 ring-slate-200/70">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
            <tr>
              <th className="px-4 py-2">Tipo</th>
              <th className="px-4 py-2">Descrição</th>
              <th className="px-4 py-2">Parceiro</th>
              <th className="px-4 py-2">Vencimento</th>
              <th className="px-4 py-2">Status</th>
              <th className="px-4 py-2">Forma pgto.</th>
              <th className="px-4 py-2 text-right">Valor</th>
              <th className="px-4 py-2 text-right">Juros/Desconto</th>
            </tr>
          </thead>
          <tbody>
            {carregando && (
              <tr>
                <td className="px-4 py-3 text-slate-400" colSpan={8}>
                  Carregando...
                </td>
              </tr>
            )}
            {!carregando && contas.length === 0 && (
              <tr>
                <td className="px-4 py-3 text-slate-400" colSpan={8}>
                  Nenhum lançamento encontrado com esses filtros.
                </td>
              </tr>
            )}
            {contas.map((c) => (
              <tr key={c.id} className="border-t border-slate-100">
                <td className="px-4 py-2">
                  <span className={c.tipo_operacao === 'entrada' ? 'text-red-700' : 'text-emerald-700'}>
                    {c.tipo_operacao === 'entrada' ? 'Despesa' : 'Receita'}
                  </span>
                </td>
                <td className="px-4 py-2">
                  {c.descricao}
                  {c.total_parcelas > 1 && (
                    <span className="text-slate-400">
                      {' '}
                      ({c.numero_parcela}/{c.total_parcelas})
                    </span>
                  )}
                </td>
                <td className="px-4 py-2 text-slate-500">{nomesParceiros[c.parceiro_id] ?? '—'}</td>
                <td className="px-4 py-2">{formatarData(c.data_vencimento)}</td>
                <td className="px-4 py-2">
                  <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${STATUS_COR[c.status]}`}>
                    {STATUS_LABEL[c.status]}
                  </span>
                </td>
                <td className="px-4 py-2 text-slate-500">
                  {c.forma_pagamento ? FORMA_PAGAMENTO_LABEL[c.forma_pagamento] : '—'}
                </td>
                <td className="px-4 py-2 text-right font-medium">{formatarMoeda(c.valor)}</td>
                <td className="px-4 py-2 text-right">
                  {c.juros_pago === null ? (
                    <span className="text-slate-300">—</span>
                  ) : (
                    <span className={Number(c.juros_pago) > 0 ? 'text-red-600' : Number(c.juros_pago) < 0 ? 'text-emerald-600' : 'text-slate-400'}>
                      {Number(c.juros_pago) > 0 && '+'}
                      {formatarMoeda(c.juros_pago)}
                    </span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
