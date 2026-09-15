import { AlertTriangle, ArrowDownCircle, ArrowUpCircle, Info, Percent, Wallet } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
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
import { KpiCard } from '../components/KpiCard'
import { api } from '../lib/api'
import type {
  ItemCentroCusto,
  ItemGastoPrevistoDia,
  ItemLucroCentroCusto,
  ItemStatusNota,
  PontoEvolucaoMensal,
  ResumoIndicadores,
  SaudeFinanceira,
} from '../types'

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

type Granularidade = 'dia' | 'semana' | 'dia_semana'

const DIAS_SEMANA_LABEL = ['Dom', 'Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb']
const ORDEM_SEMANA = [1, 2, 3, 4, 5, 6, 0] // reordena getDay() (0=dom) pra começar na segunda

function diaDoMes(dataIso: string): number {
  return Number(dataIso.slice(8, 10))
}

function diaDaSemana(dataIso: string): number {
  const [ano, mes, dia] = dataIso.split('-').map(Number)
  return new Date(ano, mes - 1, dia).getDay()
}

function ultimoDiaDoMes(mesReferencia: string): number {
  const [ano, mes] = mesReferencia.split('-').map(Number)
  return new Date(ano, mes, 0).getDate()
}

function dataDoDia(mesReferencia: string, dia: number): string {
  const [ano, mes] = mesReferencia.split('-').map(Number)
  return `${ano}-${String(mes).padStart(2, '0')}-${String(dia).padStart(2, '0')}`
}

interface BucketGastoPrevisto {
  rotulo: string
  valor: number
  dataInicio: string | null
  dataFim: string | null
}

function agruparGastosPrevistos(
  mesReferencia: string,
  itens: ItemGastoPrevistoDia[],
  granularidade: Granularidade,
): BucketGastoPrevisto[] {
  if (!mesReferencia) return []
  const ultimoDia = ultimoDiaDoMes(mesReferencia)

  if (granularidade === 'dia') {
    const totalPorDia = new Map(itens.map((i) => [diaDoMes(i.data), Number(i.total)]))
    return Array.from({ length: ultimoDia }, (_, idx) => {
      const dia = idx + 1
      const data = dataDoDia(mesReferencia, dia)
      return { rotulo: String(dia), valor: totalPorDia.get(dia) ?? 0, dataInicio: data, dataFim: data }
    })
  }

  if (granularidade === 'semana') {
    const numSemanas = Math.ceil(ultimoDia / 7)
    const totais = Array.from({ length: numSemanas }, () => 0)
    for (const item of itens) {
      totais[Math.ceil(diaDoMes(item.data) / 7) - 1] += Number(item.total)
    }
    return totais.map((valor, idx) => ({
      rotulo: `Sem ${idx + 1}`,
      valor,
      dataInicio: dataDoDia(mesReferencia, idx * 7 + 1),
      dataFim: dataDoDia(mesReferencia, Math.min((idx + 1) * 7, ultimoDia)),
    }))
  }

  const totais = new Array(7).fill(0)
  for (const item of itens) {
    totais[diaDaSemana(item.data)] += Number(item.total)
  }
  // dia da semana agrega datas espalhadas pelo mês inteiro — não dá pra
  // representar como um único intervalo, então não é clicável.
  return ORDEM_SEMANA.map((idx) => ({ rotulo: DIAS_SEMANA_LABEL[idx], valor: totais[idx], dataInicio: null, dataFim: null }))
}

type Situacao = 'bom' | 'atencao' | 'ruim' | 'neutro'

const SITUACAO_COR: Record<Situacao, string> = {
  bom: 'bg-emerald-100 text-emerald-800',
  atencao: 'bg-amber-100 text-amber-800',
  ruim: 'bg-red-100 text-red-800',
  neutro: 'bg-slate-100 text-slate-600',
}

const SITUACAO_LABEL: Record<Situacao, string> = {
  bom: 'Dentro do benchmark',
  atencao: 'Atenção',
  ruim: 'Fora do benchmark',
  neutro: 'Informativo',
}

interface BenchmarkCardProps {
  titulo: string
  valor: string
  situacao: Situacao
  referencia: string
}

function BenchmarkCard({ titulo, valor, situacao, referencia }: BenchmarkCardProps) {
  return (
    <div className="rounded-xl bg-white p-5 shadow-sm ring-1 ring-slate-200/70">
      <p className="text-xs font-medium uppercase tracking-wide text-slate-500">{titulo}</p>
      <p className="mt-1 text-2xl font-semibold text-slate-800">{valor}</p>
      <div className="mt-2 flex items-start gap-1.5">
        <span className={`shrink-0 rounded-full px-2 py-0.5 text-xs font-medium ${SITUACAO_COR[situacao]}`}>
          {SITUACAO_LABEL[situacao]}
        </span>
      </div>
      <p className="mt-2 text-xs leading-snug text-slate-400">{referencia}</p>
    </div>
  )
}

function classificarMargem(pct: number): Situacao {
  if (pct < 0) return 'ruim'
  if (pct < 5) return 'atencao'
  return 'bom'
}

function classificarDso(dias: number): Situacao {
  if (dias <= 35) return 'bom'
  if (dias <= 70) return 'atencao'
  return 'ruim'
}

export function IndicadoresPage() {
  const navigate = useNavigate()

  const [mesReferencia, setMesReferencia] = useState('')
  const [resumo, setResumo] = useState<ResumoIndicadores | null>(null)
  const [evolucao, setEvolucao] = useState<PontoEvolucaoMensal[]>([])
  const [porCentroCusto, setPorCentroCusto] = useState<ItemCentroCusto[]>([])
  const [lucroPorCentro, setLucroPorCentro] = useState<ItemLucroCentroCusto[]>([])
  const [notasPorStatus, setNotasPorStatus] = useState<ItemStatusNota[]>([])
  const [gastosPrevistos, setGastosPrevistos] = useState<ItemGastoPrevistoDia[]>([])
  const [granularidade, setGranularidade] = useState<Granularidade>('dia')
  const [saude, setSaude] = useState<SaudeFinanceira | null>(null)
  const [carregando, setCarregando] = useState(true)

  useEffect(() => {
    async function carregar() {
      const [evolucaoRes, notasRes, saudeRes, dataAtualRes] = await Promise.all([
        api.get<PontoEvolucaoMensal[]>('/indicadores/evolucao-mensal', { params: { meses: 6 } }),
        api.get<ItemStatusNota[]>('/indicadores/notas-por-status'),
        api.get<SaudeFinanceira>('/indicadores/saude-financeira'),
        api.get<{ data: string }>('/sistema/data-atual'),
      ])
      setEvolucao(evolucaoRes.data)
      setNotasPorStatus(notasRes.data)
      setSaude(saudeRes.data)

      const mesAtual = dataAtualRes.data.data.slice(0, 7)
      setMesReferencia(mesAtual)
      await carregarDoMes(mesAtual)
      setCarregando(false)
    }
    carregar()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  async function carregarDoMes(mes: string) {
    const [resumoRes, centroCustoRes, lucroRes, gastosRes] = await Promise.all([
      api.get<ResumoIndicadores>('/indicadores/resumo', { params: { mes } }),
      api.get<ItemCentroCusto[]>('/indicadores/por-centro-custo', { params: { mes } }),
      api.get<ItemLucroCentroCusto[]>('/indicadores/lucro-por-centro-custo', { params: { mes } }),
      api.get<ItemGastoPrevistoDia[]>('/indicadores/gastos-previstos-por-dia', { params: { mes } }),
    ])
    setResumo(resumoRes.data)
    setPorCentroCusto(centroCustoRes.data)
    setLucroPorCentro(lucroRes.data)
    setGastosPrevistos(gastosRes.data)
  }

  async function mudarMesReferencia(mes: string) {
    setMesReferencia(mes)
    if (!mes) return
    await carregarDoMes(mes)
  }

  function irParaRelatorios(params: Record<string, string>) {
    navigate(`/relatorios?${new URLSearchParams(params).toString()}`)
  }

  if (carregando || !resumo) {
    return <p className="text-sm text-slate-400">Carregando...</p>
  }

  const dadosEvolucao = evolucao.map((p) => ({
    mesRaw: p.mes,
    mes: formatarMes(p.mes),
    Pago: Number(p.total_pago),
    Recebido: Number(p.total_recebido),
  }))

  const dadosCentroCusto = porCentroCusto.map((c) => ({ nome: c.centro_custo, valor: Number(c.total), id: c.centro_custo_id }))
  const dadosLucro = lucroPorCentro.map((c) => ({
    nome: c.centro_custo,
    id: c.centro_custo_id,
    Despesa: Number(c.despesa),
    Receita: Number(c.receita),
    lucro: Number(c.receita) - Number(c.despesa),
  }))
  const dadosGastosPrevistos = agruparGastosPrevistos(mesReferencia, gastosPrevistos, granularidade)
  const dadosStatus = notasPorStatus.map((s) => ({
    nome: STATUS_LABEL[s.status] ?? s.status,
    valor: s.quantidade,
    cor: CORES_STATUS[s.status] ?? '#94a3b8',
    statusRaw: s.status,
  }))

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-slate-800">Indicadores</h2>
          <p className="text-sm text-slate-500">
            Clique em um KPI ou numa barra do gráfico pra ver os lançamentos correspondentes em Relatórios.
          </p>
        </div>
        <div>
          <label className="mb-1 block text-xs font-medium text-slate-600">Mês de referência</label>
          <input
            type="month"
            value={mesReferencia}
            onChange={(e) => mudarMesReferencia(e.target.value)}
            className="rounded border border-slate-300 px-2 py-1.5 text-sm"
          />
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-5">
        <KpiCard
          titulo="Saldo do mês"
          valor={formatarMoeda(resumo.saldo_mes)}
          icone={Wallet}
          corIcone="text-brand-700"
          corFundo="bg-brand-100"
          onClick={() => irParaRelatorios({ mes: mesReferencia })}
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
        <KpiCard
          titulo="Juros pagos (mês)"
          valor={formatarMoeda(resumo.juros_pagos_mes)}
          icone={Percent}
          corIcone="text-orange-600"
          corFundo="bg-orange-100"
          onClick={() => irParaRelatorios({ mes: mesReferencia, status_conta: 'pago' })}
        />
      </div>

      {saude && (
        <div className="mt-6">
          <div className="mb-3 flex items-start gap-2">
            <h3 className="text-sm font-semibold text-slate-700">Saúde financeira x benchmark do setor</h3>
            <span className="group relative">
              <Info size={14} className="mt-0.5 text-slate-400" />
              <span className="pointer-events-none absolute left-0 top-5 z-10 hidden w-72 rounded-lg bg-slate-800 p-2.5 text-xs text-slate-100 shadow-lg group-hover:block">
                Portfólio inteiro (não é só o mês selecionado). Benchmarks de margem líquida e DSO vêm de pesquisas do
                setor de construção civil (CFMA Construction Financial Benchmarker 2024; JMCO Performance Benchmarks
                2025) — referência do mercado americano, na falta de um benchmark público consolidado pro setor no
                Brasil.
              </span>
            </span>
          </div>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-5">
            <BenchmarkCard
              titulo="Margem líquida"
              valor={`${Number(saude.margem_liquida_pct).toLocaleString('pt-BR')}%`}
              situacao={classificarMargem(Number(saude.margem_liquida_pct))}
              referencia="Benchmark (construtoras bem geridas): 5–8%"
            />
            <BenchmarkCard
              titulo="Prazo médio de recebimento"
              valor={`${Number(saude.dso_dias).toLocaleString('pt-BR')} dias`}
              situacao={classificarDso(Number(saude.dso_dias))}
              referencia="Benchmark: até 35 dias é saudável"
            />
            <BenchmarkCard
              titulo="Prazo médio de pagamento"
              valor={`${Number(saude.dpo_dias).toLocaleString('pt-BR')} dias`}
              situacao="neutro"
              referencia="Quanto maior, mais a empresa usa fornecedor como crédito"
            />
            <BenchmarkCard
              titulo="Inadimplência (em aberto)"
              valor={`${Number(saude.indice_inadimplencia_pct).toLocaleString('pt-BR')}%`}
              situacao="neutro"
              referencia="Do que está em aberto hoje, quanto já venceu"
            />
            <BenchmarkCard
              titulo="Ticket médio"
              valor={`${formatarMoedaCompacta(Number(saude.ticket_medio_receita))} recebido`}
              situacao="neutro"
              referencia={`vs. ${formatarMoedaCompacta(Number(saude.ticket_medio_despesa))} por despesa — receita bem mais concentrada`}
            />
          </div>
        </div>
      )}

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
              <Bar
                dataKey="Recebido"
                fill="#10b981"
                radius={[4, 4, 0, 0]}
                cursor="pointer"
                onClick={(_, i) => irParaRelatorios({ mes: dadosEvolucao[i].mesRaw, tipo_operacao: 'saida' })}
              />
              <Bar
                dataKey="Pago"
                fill="#dc2626"
                radius={[4, 4, 0, 0]}
                cursor="pointer"
                onClick={(_, i) => irParaRelatorios({ mes: dadosEvolucao[i].mesRaw, tipo_operacao: 'entrada' })}
              />
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
                <Pie
                  data={dadosStatus}
                  dataKey="valor"
                  nameKey="nome"
                  innerRadius={55}
                  outerRadius={90}
                  paddingAngle={2}
                  cursor="pointer"
                  onClick={(_, i) => navigate(`/notas-fiscais?${new URLSearchParams({ status: dadosStatus[i].statusRaw }).toString()}`)}
                >
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
              <Bar
                dataKey="valor"
                radius={[0, 4, 4, 0]}
                cursor="pointer"
                onClick={(_, i) => irParaRelatorios({ centro_custo_id: dadosCentroCusto[i].id, mes: mesReferencia, tipo_operacao: 'entrada' })}
              >
                {dadosCentroCusto.map((_, i) => (
                  <Cell key={i} fill={CORES_CENTRO_CUSTO[i % CORES_CENTRO_CUSTO.length]} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        )}
      </div>

      <div className="mt-6 rounded-xl bg-white p-5 shadow-sm ring-1 ring-slate-200/70">
        <h3 className="mb-4 text-sm font-semibold text-slate-700">Lucro por centro de custo — despesa vs. receita do mês</h3>
        {dadosLucro.length === 0 ? (
          <p className="py-10 text-center text-sm text-slate-400">Sem lançamentos esse mês.</p>
        ) : (
          <ResponsiveContainer width="100%" height={Math.max(dadosLucro.length * 60, 140)}>
            <BarChart data={dadosLucro} layout="vertical" margin={{ left: 24 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" horizontal={false} />
              <XAxis
                type="number"
                tick={{ fontSize: 12, fill: '#64748b' }}
                axisLine={false}
                tickLine={false}
                tickFormatter={(v) => formatarMoedaCompacta(v)}
              />
              <YAxis dataKey="nome" type="category" width={160} tick={{ fontSize: 12, fill: '#334155' }} axisLine={false} tickLine={false} />
              <Tooltip
                formatter={(v: number) => formatarMoeda(String(v))}
                labelFormatter={(nome) => {
                  const item = dadosLucro.find((d) => d.nome === nome)
                  return item ? `${nome} — lucro: ${formatarMoeda(String(item.lucro))}` : nome
                }}
              />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <Bar
                dataKey="Despesa"
                fill="#dc2626"
                radius={[0, 4, 4, 0]}
                cursor="pointer"
                onClick={(_, i) => irParaRelatorios({ centro_custo_id: dadosLucro[i].id, mes: mesReferencia, tipo_operacao: 'entrada' })}
              />
              <Bar
                dataKey="Receita"
                fill="#10b981"
                radius={[0, 4, 4, 0]}
                cursor="pointer"
                onClick={(_, i) => irParaRelatorios({ centro_custo_id: dadosLucro[i].id, mes: mesReferencia, tipo_operacao: 'saida' })}
              />
            </BarChart>
          </ResponsiveContainer>
        )}
      </div>

      <div className="mt-6 rounded-xl bg-white p-5 shadow-sm ring-1 ring-slate-200/70">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <h3 className="text-sm font-semibold text-slate-700">Gastos previstos por dia do mês</h3>
          <select
            value={granularidade}
            onChange={(e) => setGranularidade(e.target.value as Granularidade)}
            className="rounded border border-slate-300 px-2 py-1 text-sm"
          >
            <option value="dia">Por dia</option>
            <option value="semana">Por semana</option>
            <option value="dia_semana">Por dia da semana</option>
          </select>
        </div>
        {dadosGastosPrevistos.every((d) => d.valor === 0) ? (
          <p className="py-10 text-center text-sm text-slate-400">Sem gastos previstos nesse mês.</p>
        ) : (
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={dadosGastosPrevistos}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical={false} />
              <XAxis dataKey="rotulo" tick={{ fontSize: 12, fill: '#64748b' }} axisLine={false} tickLine={false} />
              <YAxis
                tick={{ fontSize: 12, fill: '#64748b' }}
                axisLine={false}
                tickLine={false}
                tickFormatter={(v) => formatarMoedaCompacta(v)}
              />
              <Tooltip formatter={(v: number) => formatarMoeda(String(v))} />
              <Bar
                dataKey="valor"
                fill="#dc2626"
                radius={[4, 4, 0, 0]}
                cursor={granularidade === 'dia_semana' ? 'default' : 'pointer'}
                onClick={(_, i) => {
                  const bucket = dadosGastosPrevistos[i]
                  if (!bucket.dataInicio || !bucket.dataFim) return
                  irParaRelatorios({ data_inicio: bucket.dataInicio, data_fim: bucket.dataFim, tipo_operacao: 'entrada' })
                }}
              />
            </BarChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  )
}
