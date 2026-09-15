import { AlertCircle, ArrowDownCircle, ArrowUpCircle, TrendingUp, Wallet } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { KpiCard } from '../components/KpiCard'
import { useAuth } from '../contexts/AuthContext'
import { api } from '../lib/api'
import type { CentroCusto, NotaCentroCusto, OrcamentoCentroCusto, PontoCurvaS, ResumoCentroCusto } from '../types'

function formatarMoeda(valor: string): string {
  return Number(valor).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })
}

function formatarMoedaCompacta(valor: number): string {
  return valor.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL', notation: 'compact' })
}

function formatarMes(mes: string): string {
  const [ano, m] = mes.split('-')
  const nomes = ['jan', 'fev', 'mar', 'abr', 'mai', 'jun', 'jul', 'ago', 'set', 'out', 'nov', 'dez']
  return `${nomes[Number(m) - 1]}/${ano.slice(2)}`
}

function formatarDataHora(iso: string): string {
  return new Date(iso).toLocaleString('pt-BR', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' })
}

interface LinhaOrcamentoProps {
  item: OrcamentoCentroCusto
  podeEditar: boolean
  onSalvar: (valor: string) => Promise<void>
}

function LinhaOrcamento({ item, podeEditar, onSalvar }: LinhaOrcamentoProps) {
  const [valor, setValor] = useState(item.valor_planejado)
  const [salvando, setSalvando] = useState(false)

  async function salvar() {
    setSalvando(true)
    try {
      await onSalvar(valor)
    } finally {
      setSalvando(false)
    }
  }

  return (
    <tr className="border-t border-slate-100">
      <td className="px-3 py-1.5 text-sm text-slate-700">{formatarMes(item.mes_referencia.slice(0, 7))}</td>
      <td className="px-3 py-1.5">
        <input
          type="number"
          step="0.01"
          value={valor}
          onChange={(e) => setValor(e.target.value)}
          disabled={!podeEditar}
          className="w-32 rounded border border-slate-300 px-2 py-1 text-sm disabled:bg-slate-50 disabled:text-slate-400"
        />
      </td>
      <td className="px-3 py-1.5">
        {podeEditar && (
          <button
            onClick={salvar}
            disabled={salvando || valor === item.valor_planejado}
            className="rounded bg-brand-700 px-2.5 py-1 text-xs font-medium text-white hover:bg-brand-800 disabled:opacity-40"
          >
            {salvando ? 'Salvando...' : 'Salvar'}
          </button>
        )}
      </td>
    </tr>
  )
}

export function AnaliseCentroCustoPage() {
  const { usuario } = useAuth()
  const navigate = useNavigate()
  const podeEditar = usuario?.papel !== 'sub'

  const [centros, setCentros] = useState<CentroCusto[]>([])
  const [centroCustoId, setCentroCustoId] = useState('')
  const [resumo, setResumo] = useState<ResumoCentroCusto | null>(null)
  const [curvaS, setCurvaS] = useState<PontoCurvaS[]>([])
  const [orcamento, setOrcamento] = useState<OrcamentoCentroCusto[]>([])
  const [notas, setNotas] = useState<NotaCentroCusto[]>([])
  const [carregando, setCarregando] = useState(true)

  const [novoMesOrcamento, setNovoMesOrcamento] = useState('')
  const [novoValorOrcamento, setNovoValorOrcamento] = useState('')

  const [novaNota, setNovaNota] = useState('')
  const [enviandoNota, setEnviandoNota] = useState(false)

  useEffect(() => {
    api.get<CentroCusto[]>('/centros-custo').then(({ data }) => {
      setCentros(data)
      if (data.length > 0) setCentroCustoId(data[0].id)
      else setCarregando(false)
    })
  }, [])

  useEffect(() => {
    if (!centroCustoId) return
    carregarAnalise(centroCustoId)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [centroCustoId])

  async function carregarAnalise(id: string) {
    setCarregando(true)
    const [resumoRes, curvaRes, orcamentoRes, notasRes] = await Promise.all([
      api.get<ResumoCentroCusto>(`/centros-custo/${id}/resumo`),
      api.get<PontoCurvaS[]>(`/centros-custo/${id}/curva-s`),
      api.get<OrcamentoCentroCusto[]>(`/centros-custo/${id}/orcamento`),
      api.get<NotaCentroCusto[]>(`/centros-custo/${id}/notas`),
    ])
    setResumo(resumoRes.data)
    setCurvaS(curvaRes.data)
    setOrcamento(orcamentoRes.data)
    setNotas(notasRes.data)
    setCarregando(false)
  }

  async function salvarOrcamentoMes(mes: string, valor: string) {
    await api.put(`/centros-custo/${centroCustoId}/orcamento`, { mes_referencia: `${mes}-01`, valor_planejado: valor })
    await carregarAnalise(centroCustoId)
  }

  async function adicionarMesOrcamento() {
    if (!novoMesOrcamento || !novoValorOrcamento) return
    await salvarOrcamentoMes(novoMesOrcamento, novoValorOrcamento)
    setNovoMesOrcamento('')
    setNovoValorOrcamento('')
  }

  async function enviarNota() {
    if (!novaNota.trim()) return
    setEnviandoNota(true)
    try {
      await api.post(`/centros-custo/${centroCustoId}/notas`, { texto: novaNota.trim() })
      setNovaNota('')
      const { data } = await api.get<NotaCentroCusto[]>(`/centros-custo/${centroCustoId}/notas`)
      setNotas(data)
    } finally {
      setEnviandoNota(false)
    }
  }

  function irParaRelatorios(params: Record<string, string>) {
    navigate(`/relatorios?${new URLSearchParams({ centro_custo_id: centroCustoId, ...params }).toString()}`)
  }

  if (centros.length === 0 && !carregando) {
    return <p className="text-sm text-slate-400">Cadastre um centro de custo pra ver a análise por obra.</p>
  }

  const dadosCurva = curvaS.map((p) => ({
    mes: formatarMes(p.mes),
    Planejado: Number(p.planejado_acumulado),
    Realizado: Number(p.realizado_acumulado),
  }))

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-slate-800">Análise por Centro de Custo</h2>
          <p className="text-sm text-slate-500">Curva S, receitas futuras e notas da obra — por projeto.</p>
        </div>
        <div>
          <label className="mb-1 block text-xs font-medium text-slate-600">Obra / centro de custo</label>
          <select
            value={centroCustoId}
            onChange={(e) => setCentroCustoId(e.target.value)}
            className="rounded border border-slate-300 px-2 py-1.5 text-sm"
          >
            {centros.map((c) => (
              <option key={c.id} value={c.id}>
                {c.nome}
              </option>
            ))}
          </select>
        </div>
      </div>

      {carregando || !resumo ? (
        <p className="text-sm text-slate-400">Carregando...</p>
      ) : (
        <>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-5">
            <KpiCard
              titulo="Despesas realizadas"
              valor={formatarMoeda(resumo.despesas_realizadas)}
              icone={ArrowUpCircle}
              corIcone="text-red-600"
              corFundo="bg-red-100"
              onClick={() => irParaRelatorios({ tipo_operacao: 'entrada', status_conta: 'pago' })}
            />
            <KpiCard
              titulo="Receitas realizadas"
              valor={formatarMoeda(resumo.receitas_realizadas)}
              icone={ArrowDownCircle}
              corIcone="text-emerald-600"
              corFundo="bg-emerald-100"
              onClick={() => irParaRelatorios({ tipo_operacao: 'saida', status_conta: 'pago' })}
            />
            <KpiCard
              titulo="Saldo realizado"
              valor={formatarMoeda(resumo.saldo_realizado)}
              icone={Wallet}
              corIcone="text-brand-700"
              corFundo="bg-brand-100"
              onClick={() => irParaRelatorios({})}
            />
            <KpiCard
              titulo="Despesas futuras"
              valor={formatarMoeda(resumo.despesas_futuras)}
              icone={AlertCircle}
              corIcone="text-amber-600"
              corFundo="bg-amber-100"
              onClick={() => irParaRelatorios({ tipo_operacao: 'entrada', status_conta: 'pendente' })}
            />
            <KpiCard
              titulo="Receitas futuras"
              valor={formatarMoeda(resumo.receitas_futuras)}
              icone={TrendingUp}
              corIcone="text-sky-600"
              corFundo="bg-sky-100"
              onClick={() => irParaRelatorios({ tipo_operacao: 'saida', status_conta: 'pendente' })}
            />
          </div>

          <div className="mt-6 rounded-xl bg-white p-5 shadow-sm ring-1 ring-slate-200/70">
            <h3 className="mb-1 text-sm font-semibold text-slate-700">Curva S — planejado x realizado (despesa acumulada)</h3>
            <p className="mb-4 text-xs text-slate-500">
              Planejado vem do orçamento mensal cadastrado abaixo. Sem orçamento cadastrado, só a linha de realizado aparece.
            </p>
            {dadosCurva.length === 0 ? (
              <p className="py-10 text-center text-sm text-slate-400">
                Sem orçamento nem despesas lançadas ainda pra essa obra.
              </p>
            ) : (
              <ResponsiveContainer width="100%" height={300}>
                <LineChart data={dadosCurva}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical={false} />
                  <XAxis dataKey="mes" tick={{ fontSize: 12, fill: '#64748b' }} axisLine={false} tickLine={false} />
                  <YAxis
                    tick={{ fontSize: 12, fill: '#64748b' }}
                    axisLine={false}
                    tickLine={false}
                    tickFormatter={(v) => formatarMoedaCompacta(v)}
                  />
                  <Tooltip formatter={(v: number) => formatarMoeda(String(v))} />
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                  <Line type="monotone" dataKey="Planejado" stroke="#64748b" strokeWidth={2} strokeDasharray="6 4" dot={{ r: 3 }} />
                  <Line type="monotone" dataKey="Realizado" stroke="#dc2626" strokeWidth={2} dot={{ r: 3 }} />
                </LineChart>
              </ResponsiveContainer>
            )}
          </div>

          <div className="mt-6 grid grid-cols-1 gap-4 lg:grid-cols-2">
            <div className="rounded-xl bg-white p-5 shadow-sm ring-1 ring-slate-200/70">
              <h3 className="mb-4 text-sm font-semibold text-slate-700">Orçamento mensal (planejado)</h3>
              {orcamento.length === 0 ? (
                <p className="mb-3 text-sm text-slate-400">Nenhum mês orçado ainda.</p>
              ) : (
                <table className="mb-3 w-full text-sm">
                  <thead className="text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                    <tr>
                      <th className="px-3 py-1.5">Mês</th>
                      <th className="px-3 py-1.5">Valor planejado</th>
                      <th className="px-3 py-1.5" />
                    </tr>
                  </thead>
                  <tbody>
                    {orcamento.map((o) => (
                      <LinhaOrcamento
                        key={o.id}
                        item={o}
                        podeEditar={podeEditar}
                        onSalvar={(valor) => salvarOrcamentoMes(o.mes_referencia.slice(0, 7), valor)}
                      />
                    ))}
                  </tbody>
                </table>
              )}
              {podeEditar && (
                <div className="flex flex-wrap items-end gap-2 border-t border-slate-100 pt-3">
                  <div>
                    <label className="mb-1 block text-xs font-medium text-slate-600">Novo mês</label>
                    <input
                      type="month"
                      value={novoMesOrcamento}
                      onChange={(e) => setNovoMesOrcamento(e.target.value)}
                      className="rounded border border-slate-300 px-2 py-1 text-sm"
                    />
                  </div>
                  <div>
                    <label className="mb-1 block text-xs font-medium text-slate-600">Valor planejado</label>
                    <input
                      type="number"
                      step="0.01"
                      value={novoValorOrcamento}
                      onChange={(e) => setNovoValorOrcamento(e.target.value)}
                      className="w-32 rounded border border-slate-300 px-2 py-1 text-sm"
                    />
                  </div>
                  <button
                    onClick={adicionarMesOrcamento}
                    disabled={!novoMesOrcamento || !novoValorOrcamento}
                    className="rounded bg-brand-700 px-3 py-1.5 text-sm text-white hover:bg-brand-800 disabled:opacity-40"
                  >
                    Adicionar
                  </button>
                </div>
              )}
            </div>

            <div className="rounded-xl bg-white p-5 shadow-sm ring-1 ring-slate-200/70">
              <h3 className="mb-4 text-sm font-semibold text-slate-700">Notas da obra — visível pra todo mundo</h3>
              {podeEditar && (
                <div className="mb-4 flex items-start gap-2">
                  <textarea
                    value={novaNota}
                    onChange={(e) => setNovaNota(e.target.value)}
                    placeholder="Escreva uma nota sobre essa obra..."
                    rows={2}
                    className="flex-1 rounded border border-slate-300 px-3 py-2 text-sm"
                  />
                  <button
                    onClick={enviarNota}
                    disabled={enviandoNota || !novaNota.trim()}
                    className="rounded bg-brand-700 px-3 py-2 text-sm text-white hover:bg-brand-800 disabled:opacity-50"
                  >
                    {enviandoNota ? 'Enviando...' : 'Adicionar'}
                  </button>
                </div>
              )}
              {notas.length === 0 ? (
                <p className="py-6 text-center text-sm text-slate-400">Nenhuma nota ainda.</p>
              ) : (
                <ul className="max-h-80 space-y-3 overflow-y-auto">
                  {notas.map((n) => (
                    <li key={n.id} className="rounded-lg bg-slate-50 p-3">
                      <p className="whitespace-pre-wrap text-sm text-slate-700">{n.texto}</p>
                      <p className="mt-1 text-xs text-slate-400">
                        {n.usuario_nome} · {formatarDataHora(n.created_at)}
                      </p>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  )
}
