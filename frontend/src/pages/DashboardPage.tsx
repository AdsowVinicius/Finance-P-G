import { AlertTriangle, ArrowDownCircle, ArrowUpCircle, CalendarClock, Clock, Wallet } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { KpiCard } from '../components/KpiCard'
import { api } from '../lib/api'
import { FORMA_PAGAMENTO_LABEL } from '../lib/formaPagamento'
import type { ContaFinanceira, DashboardVencimento, Parceiro, ResumoIndicadores } from '../types'

const API_URL = (import.meta.env.VITE_API_URL as string) ?? 'http://localhost:8000'

function formatarMoeda(valor: string): string {
  return Number(valor).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })
}

function formatarData(data: string): string {
  const [ano, mes, dia] = data.split('-')
  return `${dia}/${mes}/${ano}`
}

interface SecaoProps {
  titulo: string
  icone: React.ElementType
  corClasse: string
  contas: ContaFinanceira[]
  total: string
  nomesParceiros: Record<string, string>
  onMudou: () => void
}

function Secao({ titulo, icone: Icone, corClasse, contas, total, nomesParceiros, onMudou }: SecaoProps) {
  const [contaEmBaixa, setContaEmBaixa] = useState<string | null>(null)
  const [dataPagamento, setDataPagamento] = useState('')
  const [valorPago, setValorPago] = useState('')
  const [formaPagamento, setFormaPagamento] = useState('')

  const [contaEmBoleto, setContaEmBoleto] = useState<string | null>(null)
  const [arquivoBoleto, setArquivoBoleto] = useState<File | null>(null)
  const [linhaDigitavel, setLinhaDigitavel] = useState('')
  const [codigoBarras, setCodigoBarras] = useState('')
  const [enviandoBoleto, setEnviandoBoleto] = useState(false)

  function iniciarBaixa(conta: ContaFinanceira) {
    setContaEmBoleto(null)
    setContaEmBaixa(conta.id)
    setDataPagamento(new Date().toISOString().slice(0, 10))
    setValorPago(conta.valor)
    setFormaPagamento('')
  }

  async function confirmarBaixa(contaId: string) {
    await api.post(`/contas-financeiras/${contaId}/baixa`, {
      data_pagamento: dataPagamento,
      valor_pago: valorPago,
      forma_pagamento: formaPagamento || null,
    })
    setContaEmBaixa(null)
    onMudou()
  }

  function iniciarBoleto(conta: ContaFinanceira) {
    setContaEmBaixa(null)
    setContaEmBoleto(conta.id)
    setArquivoBoleto(null)
    setLinhaDigitavel('')
    setCodigoBarras('')
  }

  async function confirmarBoleto(contaId: string) {
    if (!arquivoBoleto) return
    setEnviandoBoleto(true)
    try {
      const form = new FormData()
      form.append('arquivo', arquivoBoleto)
      if (linhaDigitavel) form.append('linha_digitavel', linhaDigitavel)
      if (codigoBarras) form.append('codigo_barras', codigoBarras)
      await api.post(`/contas-financeiras/${contaId}/boleto`, form)
      setContaEmBoleto(null)
      onMudou()
    } finally {
      setEnviandoBoleto(false)
    }
  }

  return (
    <div className="rounded-xl bg-white shadow-sm ring-1 ring-slate-200/70">
      <div className={`flex items-center justify-between rounded-t-lg px-4 py-3 ${corClasse}`}>
        <h3 className="flex items-center gap-2 font-semibold">
          <Icone size={16} />
          {titulo}
        </h3>
        <span className="text-sm font-medium">
          {contas.length} {contas.length === 1 ? 'conta' : 'contas'} · {formatarMoeda(total)}
        </span>
      </div>
      {contas.length === 0 ? (
        <p className="px-4 py-4 text-sm text-slate-400">Nada por aqui.</p>
      ) : (
        <ul className="divide-y divide-slate-100">
          {contas.map((conta) => (
            <li key={conta.id} className="px-4 py-3">
              <p className="text-sm font-medium text-slate-800">
                {conta.descricao}
                {conta.total_parcelas > 1 && (
                  <span className="text-slate-400"> ({conta.numero_parcela}/{conta.total_parcelas})</span>
                )}
              </p>
              <p className="mt-0.5 text-xs text-slate-500">
                {nomesParceiros[conta.parceiro_id] ?? '—'} · vence {formatarData(conta.data_vencimento)}
                {conta.boleto_arquivo_path && (
                  <>
                    {' · '}
                    <a
                      href={`${API_URL}/storage/${conta.boleto_arquivo_path}`}
                      target="_blank"
                      rel="noreferrer"
                      className="text-brand-700 underline"
                    >
                      ver boleto
                    </a>
                  </>
                )}
              </p>
              <div className="mt-2 flex flex-wrap items-center justify-between gap-2">
                <span className="text-sm font-semibold text-slate-800">{formatarMoeda(conta.valor)}</span>
                {contaEmBaixa !== conta.id && contaEmBoleto !== conta.id && (
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => iniciarBoleto(conta)}
                      className="rounded bg-slate-100 px-2.5 py-1 text-xs text-slate-700 hover:bg-slate-200"
                    >
                      {conta.boleto_arquivo_path ? 'Trocar boleto' : 'Anexar boleto'}
                    </button>
                    <button
                      onClick={() => iniciarBaixa(conta)}
                      className="rounded bg-brand-700 px-2.5 py-1 text-xs text-white hover:bg-brand-800"
                    >
                      Dar baixa
                    </button>
                  </div>
                )}
              </div>
              {contaEmBaixa === conta.id && (
                <div className="mt-3 flex flex-wrap items-end gap-2 rounded bg-slate-50 p-3">
                  <div>
                    <label className="mb-1 block text-xs font-medium text-slate-600">Data do pagamento</label>
                    <input
                      type="date"
                      value={dataPagamento}
                      onChange={(e) => setDataPagamento(e.target.value)}
                      className="rounded border border-slate-300 px-2 py-1 text-sm"
                    />
                  </div>
                  <div>
                    <label className="mb-1 block text-xs font-medium text-slate-600">Valor pago</label>
                    <input
                      type="number"
                      step="0.01"
                      value={valorPago}
                      onChange={(e) => setValorPago(e.target.value)}
                      className="w-28 rounded border border-slate-300 px-2 py-1 text-sm"
                    />
                  </div>
                  <div>
                    <label className="mb-1 block text-xs font-medium text-slate-600">Forma de pagamento</label>
                    <select
                      value={formaPagamento}
                      onChange={(e) => setFormaPagamento(e.target.value)}
                      className="rounded border border-slate-300 px-2 py-1 text-sm"
                    >
                      <option value="">Não informado</option>
                      {Object.entries(FORMA_PAGAMENTO_LABEL).map(([valor, label]) => (
                        <option key={valor} value={valor}>
                          {label}
                        </option>
                      ))}
                    </select>
                  </div>
                  <button
                    onClick={() => confirmarBaixa(conta.id)}
                    className="rounded bg-emerald-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-emerald-700"
                  >
                    Confirmar
                  </button>
                  <button
                    onClick={() => setContaEmBaixa(null)}
                    className="rounded px-3 py-1.5 text-xs text-slate-500 hover:bg-slate-200"
                  >
                    Cancelar
                  </button>
                </div>
              )}
              {contaEmBoleto === conta.id && (
                <div className="mt-3 flex flex-wrap items-end gap-2 rounded bg-slate-50 p-3">
                  <div>
                    <label className="mb-1 block text-xs font-medium text-slate-600">Arquivo do boleto (PDF)</label>
                    <input
                      type="file"
                      accept="application/pdf"
                      onChange={(e) => setArquivoBoleto(e.target.files?.[0] ?? null)}
                      className="text-xs"
                    />
                  </div>
                  <div>
                    <label className="mb-1 block text-xs font-medium text-slate-600">Linha digitável</label>
                    <input
                      value={linhaDigitavel}
                      onChange={(e) => setLinhaDigitavel(e.target.value)}
                      className="w-56 rounded border border-slate-300 px-2 py-1 text-sm"
                    />
                  </div>
                  <div>
                    <label className="mb-1 block text-xs font-medium text-slate-600">Código de barras</label>
                    <input
                      value={codigoBarras}
                      onChange={(e) => setCodigoBarras(e.target.value)}
                      className="w-56 rounded border border-slate-300 px-2 py-1 text-sm"
                    />
                  </div>
                  <button
                    onClick={() => confirmarBoleto(conta.id)}
                    disabled={!arquivoBoleto || enviandoBoleto}
                    className="rounded bg-emerald-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-emerald-700 disabled:opacity-50"
                  >
                    {enviandoBoleto ? 'Enviando...' : 'Salvar boleto'}
                  </button>
                  <button
                    onClick={() => setContaEmBoleto(null)}
                    className="rounded px-3 py-1.5 text-xs text-slate-500 hover:bg-slate-200"
                  >
                    Cancelar
                  </button>
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

export function DashboardPage() {
  const navigate = useNavigate()
  const [dashboard, setDashboard] = useState<DashboardVencimento | null>(null)
  const [resumo, setResumo] = useState<ResumoIndicadores | null>(null)
  const [nomesParceiros, setNomesParceiros] = useState<Record<string, string>>({})
  const [carregando, setCarregando] = useState(true)
  const [atualizando, setAtualizando] = useState(false)

  async function carregar() {
    setCarregando(true)
    const [dashRes, parceirosRes, resumoRes] = await Promise.all([
      api.get<DashboardVencimento>('/contas-financeiras/dashboard'),
      api.get<Parceiro[]>('/parceiros', { params: { apenas_ativos: false } }),
      api.get<ResumoIndicadores>('/indicadores/resumo'),
    ])
    setDashboard(dashRes.data)
    setNomesParceiros(Object.fromEntries(parceirosRes.data.map((p) => [p.id, p.razao_social])))
    setResumo(resumoRes.data)
    setCarregando(false)
  }

  useEffect(() => {
    carregar()
  }, [])

  function irParaRelatorios(params: Record<string, string>) {
    navigate(`/relatorios?${new URLSearchParams(params).toString()}`)
  }

  async function atualizarAtrasados() {
    setAtualizando(true)
    await api.post('/contas-financeiras/atualizar-atrasados')
    await carregar()
    setAtualizando(false)
  }

  if (carregando || !dashboard || !resumo) {
    return <p className="text-sm text-slate-400">Carregando...</p>
  }

  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-slate-800">Visão geral</h2>
          <p className="text-sm text-slate-500">Clique num KPI ou numa conta pra ver os detalhes em Relatórios.</p>
        </div>
        <button
          onClick={atualizarAtrasados}
          disabled={atualizando}
          className="rounded bg-slate-200 px-3 py-1.5 text-sm text-slate-700 hover:bg-slate-300 disabled:opacity-50"
        >
          {atualizando ? 'Atualizando...' : 'Atualizar atrasados'}
        </button>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <KpiCard
          titulo="Saldo do mês"
          valor={formatarMoeda(resumo.saldo_mes)}
          icone={Wallet}
          corIcone="text-brand-700"
          corFundo="bg-brand-100"
          onClick={() => irParaRelatorios({})}
        />
        <KpiCard
          titulo="A pagar (em aberto)"
          valor={formatarMoeda(resumo.total_a_pagar_aberto)}
          icone={ArrowUpCircle}
          corIcone="text-red-600"
          corFundo="bg-red-100"
          onClick={() => irParaRelatorios({ tipo_operacao: 'entrada' })}
        />
        <KpiCard
          titulo="A receber (em aberto)"
          valor={formatarMoeda(resumo.total_a_receber_aberto)}
          icone={ArrowDownCircle}
          corIcone="text-emerald-600"
          corFundo="bg-emerald-100"
          onClick={() => irParaRelatorios({ tipo_operacao: 'saida' })}
        />
        <KpiCard
          titulo="Atrasadas"
          valor={`${resumo.contas_atrasadas_qtd} · ${formatarMoeda(resumo.contas_atrasadas_total)}`}
          icone={AlertTriangle}
          corIcone="text-amber-600"
          corFundo="bg-amber-100"
          onClick={() => irParaRelatorios({ status_conta: 'atrasado' })}
        />
      </div>

      <div className="mt-6 mb-3">
        <h3 className="text-sm font-semibold text-slate-700">Contas a pagar / receber — vencimento</h3>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Secao
          titulo="Atrasado"
          icone={AlertTriangle}
          corClasse="bg-red-100 text-red-800"
          contas={dashboard.atrasado}
          total={dashboard.total_atrasado}
          nomesParceiros={nomesParceiros}
          onMudou={carregar}
        />
        <Secao
          titulo="Vence hoje"
          icone={Clock}
          corClasse="bg-amber-100 text-amber-800"
          contas={dashboard.hoje}
          total={dashboard.total_hoje}
          nomesParceiros={nomesParceiros}
          onMudou={carregar}
        />
        <Secao
          titulo="Vence na semana"
          icone={CalendarClock}
          corClasse="bg-blue-100 text-blue-800"
          contas={dashboard.semana}
          total={dashboard.total_semana}
          nomesParceiros={nomesParceiros}
          onMudou={carregar}
        />
      </div>
    </div>
  )
}
