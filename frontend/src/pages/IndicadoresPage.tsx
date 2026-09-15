import { AlertTriangle, ArrowDownCircle, ArrowUpCircle, Wallet } from 'lucide-react'
import { useEffect, useState } from 'react'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { api } from '../lib/api'
import type { ItemCentroCusto, ItemStatusNota, PontoEvolucaoMensal, ResumoIndicadores } from '../types'

const CORES_STATUS: Record<string, string> = {
  pendente: '#94a3b8',
  parcialmente_conciliada: '#f59e0b',
  conciliada: '#10b981',
  cancelada: '#ef4444',
}

const STATUS_LABEL: Record<string, string> = {
  pendente: 'Pendente',
  parcialmente_conciliada: 'Parcialmente conciliada',
  conciliada: 'Conciliada',
  cancelada: 'Cancelada',
}

const CORES_CENTRO_CUSTO = ['#1e3a5f', '#2563eb', '#0ea5e9', '#14b8a6', '#84cc16', '#f59e0b', '#f97316', '#ef4444']

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

interface KpiCardProps {
  titulo: string
  valor: string
  icone: React.ElementType
  corIcone: string
  corFundo: string
}

function KpiCard({ titulo, valor, icone: Icone, corIcone, corFundo }: KpiCardProps) {
  return (
    <div className="rounded-xl bg-white p-5 shadow-sm ring-1 ring-slate-200/70">
      <div className="flex items-start gap-3">
        <div className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-full ${corFundo}`}>
          <Icone size={20} className={corIcone} />
        </div>
        <div className="min-w-0">
          <p className="text-xs font-medium uppercase tracking-wide text-slate-500">{titulo}</p>
          <p className="text-lg font-semibold leading-tight text-slate-800">{valor}</p>
        </div>
      </div>
    </div>
  )
}

export function IndicadoresPage() {
  const [resumo, setResumo] = useState<ResumoIndicadores | null>(null)
  const [evolucao, setEvolucao] = useState<PontoEvolucaoMensal[]>([])
  const [porCentroCusto, setPorCentroCusto] = useState<ItemCentroCusto[]>([])
  const [notasPorStatus, setNotasPorStatus] = useState<ItemStatusNota[]>([])
  const [carregando, setCarregando] = useState(true)

  useEffect(() => {
    async function carregar() {
      const [resumoRes, evolucaoRes, centroCustoRes, notasRes] = await Promise.all([
        api.get<ResumoIndicadores>('/indicadores/resumo'),
        api.get<PontoEvolucaoMensal[]>('/indicadores/evolucao-mensal', { params: { meses: 6 } }),
        api.get<ItemCentroCusto[]>('/indicadores/por-centro-custo'),
        api.get<ItemStatusNota[]>('/indicadores/notas-por-status'),
      ])
      setResumo(resumoRes.data)
      setEvolucao(evolucaoRes.data)
      setPorCentroCusto(centroCustoRes.data)
      setNotasPorStatus(notasRes.data)
      setCarregando(false)
    }
    carregar()
  }, [])

  if (carregando || !resumo) {
    return <p className="text-sm text-slate-400">Carregando...</p>
  }

  const dadosEvolucao = evolucao.map((p) => ({
    mes: formatarMes(p.mes),
    Pago: Number(p.total_pago),
    Recebido: Number(p.total_recebido),
  }))

  const dadosCentroCusto = porCentroCusto.map((c) => ({ nome: c.centro_custo, valor: Number(c.total) }))
  const dadosStatus = notasPorStatus.map((s) => ({
    nome: STATUS_LABEL[s.status] ?? s.status,
    valor: s.quantidade,
    cor: CORES_STATUS[s.status] ?? '#94a3b8',
  }))

  return (
    <div>
      <div className="mb-4">
        <h2 className="text-lg font-semibold text-slate-800">Indicadores</h2>
        <p className="text-sm text-slate-500">Visão geral financeira — saldo, evolução e distribuição por centro de custo.</p>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <KpiCard
          titulo="Saldo do mês"
          valor={formatarMoeda(resumo.saldo_mes)}
          icone={Wallet}
          corIcone="text-brand-700"
          corFundo="bg-brand-100"
        />
        <KpiCard
          titulo="A pagar (em aberto)"
          valor={formatarMoeda(resumo.total_a_pagar_aberto)}
          icone={ArrowUpCircle}
          corIcone="text-red-600"
          corFundo="bg-red-100"
        />
        <KpiCard
          titulo="A receber (em aberto)"
          valor={formatarMoeda(resumo.total_a_receber_aberto)}
          icone={ArrowDownCircle}
          corIcone="text-emerald-600"
          corFundo="bg-emerald-100"
        />
        <KpiCard
          titulo="Atrasadas"
          valor={`${resumo.contas_atrasadas_qtd} · ${formatarMoeda(resumo.contas_atrasadas_total)}`}
          icone={AlertTriangle}
          corIcone="text-amber-600"
          corFundo="bg-amber-100"
        />
      </div>

      <div className="mt-6 grid grid-cols-1 gap-4 lg:grid-cols-3">
        <div className="rounded-xl bg-white p-5 shadow-sm ring-1 ring-slate-200/70 lg:col-span-2">
          <h3 className="mb-4 text-sm font-semibold text-slate-700">Evolução mensal — pago vs. recebido</h3>
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={dadosEvolucao}>
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
              <Bar dataKey="Recebido" fill="#10b981" radius={[4, 4, 0, 0]} />
              <Bar dataKey="Pago" fill="#dc2626" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="rounded-xl bg-white p-5 shadow-sm ring-1 ring-slate-200/70">
          <h3 className="mb-4 text-sm font-semibold text-slate-700">Notas fiscais por status</h3>
          {dadosStatus.length === 0 ? (
            <p className="py-10 text-center text-sm text-slate-400">Sem notas cadastradas.</p>
          ) : (
            <ResponsiveContainer width="100%" height={280}>
              <PieChart>
                <Pie data={dadosStatus} dataKey="valor" nameKey="nome" innerRadius={55} outerRadius={90} paddingAngle={2}>
                  {dadosStatus.map((entrada, i) => (
                    <Cell key={i} fill={entrada.cor} />
                  ))}
                </Pie>
                <Tooltip />
                <Legend wrapperStyle={{ fontSize: 12 }} />
              </PieChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>

      <div className="mt-6 rounded-xl bg-white p-5 shadow-sm ring-1 ring-slate-200/70">
        <h3 className="mb-4 text-sm font-semibold text-slate-700">Gastos do mês por centro de custo</h3>
        {dadosCentroCusto.length === 0 ? (
          <p className="py-10 text-center text-sm text-slate-400">Sem gastos lançados esse mês.</p>
        ) : (
          <ResponsiveContainer width="100%" height={Math.max(dadosCentroCusto.length * 44, 120)}>
            <BarChart data={dadosCentroCusto} layout="vertical" margin={{ left: 24 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" horizontal={false} />
              <XAxis
                type="number"
                tick={{ fontSize: 12, fill: '#64748b' }}
                axisLine={false}
                tickLine={false}
                tickFormatter={(v) => formatarMoedaCompacta(v)}
              />
              <YAxis dataKey="nome" type="category" width={160} tick={{ fontSize: 12, fill: '#334155' }} axisLine={false} tickLine={false} />
              <Tooltip formatter={(v: number) => formatarMoeda(String(v))} />
              <Bar dataKey="valor" radius={[0, 4, 4, 0]}>
                {dadosCentroCusto.map((_, i) => (
                  <Cell key={i} fill={CORES_CENTRO_CUSTO[i % CORES_CENTRO_CUSTO.length]} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  )
}
