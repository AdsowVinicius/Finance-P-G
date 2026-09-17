import { useEffect, useState, type FormEvent } from 'react'
import { useAuth } from '../contexts/AuthContext'
import { api } from '../lib/api'
import { extractApiError } from '../lib/apiError'
import { formatarMoeda } from '../lib/formatters'
import type {
  CategoriaLancamento,
  CentroCusto,
  LancamentoRecorrente,
  Parceiro,
  Periodicidade,
  RegraDiaUtilCategoria,
  TipoOperacaoNota,
} from '../types'

const periodicidades: Periodicidade[] = ['mensal', 'quinzenal', 'semanal', 'anual', 'personalizada_dias']

const REGRA_DIA_UTIL_LABEL: Record<RegraDiaUtilCategoria, string> = {
  funcionario: 'Pagamento de funcionário (sábado conta como dia útil)',
  bancaria: 'Conta de banco (só seg-sex, cai pra sexta anterior)',
}

export function LancamentosRecorrentesPage() {
  const { usuario } = useAuth()
  const podeCriarCategoria = usuario?.papel === 'master'

  const [lancamentos, setLancamentos] = useState<LancamentoRecorrente[]>([])
  const [parceiros, setParceiros] = useState<Parceiro[]>([])
  const [centros, setCentros] = useState<CentroCusto[]>([])
  const [categorias, setCategorias] = useState<CategoriaLancamento[]>([])
  const [carregando, setCarregando] = useState(true)
  const [mostrarForm, setMostrarForm] = useState(false)
  const [erro, setErro] = useState<string | null>(null)

  const [mostrarNovaCategoria, setMostrarNovaCategoria] = useState(false)
  const [novaCategoriaNome, setNovaCategoriaNome] = useState('')
  const [novaCategoriaRegra, setNovaCategoriaRegra] = useState<RegraDiaUtilCategoria>('bancaria')
  const [salvandoCategoria, setSalvandoCategoria] = useState(false)

  const [descricao, setDescricao] = useState('')
  const [tipoOperacao, setTipoOperacao] = useState<TipoOperacaoNota>('entrada')
  const [parceiroId, setParceiroId] = useState('')
  const [centroCustoId, setCentroCustoId] = useState('')
  const [categoriaId, setCategoriaId] = useState('')
  const [valorParcela, setValorParcela] = useState('')
  const [periodicidade, setPeriodicidade] = useState<Periodicidade>('mensal')
  const [intervaloDias, setIntervaloDias] = useState('')
  const [dataInicio, setDataInicio] = useState('')
  const [condicaoParada, setCondicaoParada] = useState<'ocorrencias' | 'data_fim'>('ocorrencias')
  const [numeroOcorrencias, setNumeroOcorrencias] = useState('')
  const [dataFim, setDataFim] = useState('')

  async function carregar() {
    setCarregando(true)
    const [lancRes, parcRes, centrosRes, categoriasRes] = await Promise.all([
      api.get<LancamentoRecorrente[]>('/lancamentos-recorrentes'),
      api.get<Parceiro[]>('/parceiros'),
      api.get<CentroCusto[]>('/centros-custo'),
      api.get<CategoriaLancamento[]>('/categorias-lancamento'),
    ])
    setLancamentos(lancRes.data)
    setParceiros(parcRes.data)
    setCentros(centrosRes.data)
    setCategorias(categoriasRes.data)
    setCarregando(false)
  }

  useEffect(() => {
    carregar()
  }, [])

  function nomeParceiro(id: string | null): string {
    return parceiros.find((p) => p.id === id)?.razao_social ?? '—'
  }

  async function criarCategoria() {
    if (!novaCategoriaNome.trim()) return
    setSalvandoCategoria(true)
    try {
      const { data } = await api.post<CategoriaLancamento>('/categorias-lancamento', {
        nome: novaCategoriaNome.trim(),
        regra_dia_util: novaCategoriaRegra,
      })
      setCategorias((atual) => [...atual, data].sort((a, b) => a.nome.localeCompare(b.nome)))
      setCategoriaId(data.id)
      setNovaCategoriaNome('')
      setNovaCategoriaRegra('bancaria')
      setMostrarNovaCategoria(false)
    } catch (err) {
      setErro(extractApiError(err, 'Não foi possível criar a categoria'))
    } finally {
      setSalvandoCategoria(false)
    }
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setErro(null)
    try {
      await api.post('/lancamentos-recorrentes', {
        descricao,
        tipo_operacao: tipoOperacao,
        parceiro_id: parceiroId,
        centro_custo_id: centroCustoId,
        categoria_id: categoriaId || null,
        valor_parcela: valorParcela,
        periodicidade,
        intervalo_dias: periodicidade === 'personalizada_dias' ? Number(intervaloDias) : null,
        data_inicio: dataInicio,
        numero_ocorrencias: condicaoParada === 'ocorrencias' ? Number(numeroOcorrencias) : null,
        data_fim: condicaoParada === 'data_fim' ? dataFim : null,
      })
      setDescricao('')
      setCategoriaId('')
      setValorParcela('')
      setNumeroOcorrencias('')
      setDataFim('')
      setIntervaloDias('')
      setMostrarForm(false)
      await carregar()
    } catch (err) {
      setErro(extractApiError(err, 'Não foi possível salvar o lançamento recorrente'))
    }
  }

  async function desativar(id: string) {
    await api.delete(`/lancamentos-recorrentes/${id}`)
    await carregar()
  }

  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-lg font-semibold text-slate-800">Lançamentos Recorrentes</h2>
        <button
          onClick={() => setMostrarForm((v) => !v)}
          className="rounded bg-brand-700 px-3 py-1.5 text-sm text-white hover:bg-brand-800"
        >
          {mostrarForm ? 'Cancelar' : 'Novo lançamento recorrente'}
        </button>
      </div>

      {mostrarForm && (
        <form onSubmit={handleSubmit} className="mb-6 rounded-lg bg-white p-4 shadow">
          {erro && <div className="mb-3 rounded bg-red-50 px-3 py-2 text-sm text-red-700">{erro}</div>}
          <div className="grid grid-cols-2 gap-4">
            <div className="col-span-2">
              <label className="mb-1 block text-sm font-medium text-slate-700">Descrição *</label>
              <input
                required
                value={descricao}
                onChange={(e) => setDescricao(e.target.value)}
                placeholder="ex: Aluguel do galpão"
                className="w-full rounded border border-slate-300 px-3 py-2 text-sm"
              />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-slate-700">Tipo</label>
              <select
                value={tipoOperacao}
                onChange={(e) => setTipoOperacao(e.target.value as TipoOperacaoNota)}
                className="w-full rounded border border-slate-300 px-3 py-2 text-sm"
              >
                <option value="entrada">A pagar</option>
                <option value="saida">A receber</option>
              </select>
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-slate-700">Valor da parcela *</label>
              <input
                required
                type="number"
                step="0.01"
                value={valorParcela}
                onChange={(e) => setValorParcela(e.target.value)}
                className="w-full rounded border border-slate-300 px-3 py-2 text-sm"
              />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-slate-700">Parceiro *</label>
              <select
                required
                value={parceiroId}
                onChange={(e) => setParceiroId(e.target.value)}
                className="w-full rounded border border-slate-300 px-3 py-2 text-sm"
              >
                <option value="">Selecione...</option>
                {parceiros.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.razao_social}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-slate-700">Centro de custo *</label>
              <select
                required
                value={centroCustoId}
                onChange={(e) => setCentroCustoId(e.target.value)}
                className="w-full rounded border border-slate-300 px-3 py-2 text-sm"
              >
                <option value="">Selecione...</option>
                {centros.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.nome}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <div className="mb-1 flex items-center justify-between">
                <label className="block text-sm font-medium text-slate-700">Categoria</label>
                {podeCriarCategoria && (
                  <button
                    type="button"
                    onClick={() => setMostrarNovaCategoria((v) => !v)}
                    className="text-xs font-medium text-brand-700 hover:underline"
                  >
                    {mostrarNovaCategoria ? 'cancelar' : '+ nova categoria'}
                  </button>
                )}
              </div>
              <select
                value={categoriaId}
                onChange={(e) => setCategoriaId(e.target.value)}
                className="w-full rounded border border-slate-300 px-3 py-2 text-sm"
              >
                <option value="">Sem categoria (regra padrão de dia útil)</option>
                {categorias.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.nome}
                  </option>
                ))}
              </select>
              {mostrarNovaCategoria && podeCriarCategoria && (
                <div className="mt-2 flex flex-wrap items-end gap-2 rounded bg-slate-50 p-3">
                  <div>
                    <label className="mb-1 block text-xs font-medium text-slate-600">Nome</label>
                    <input
                      value={novaCategoriaNome}
                      onChange={(e) => setNovaCategoriaNome(e.target.value)}
                      placeholder="ex: Folha de pagamento"
                      className="w-48 rounded border border-slate-300 px-2 py-1 text-sm"
                    />
                  </div>
                  <div>
                    <label className="mb-1 block text-xs font-medium text-slate-600">Regra de dia útil</label>
                    <select
                      value={novaCategoriaRegra}
                      onChange={(e) => setNovaCategoriaRegra(e.target.value as RegraDiaUtilCategoria)}
                      className="w-64 rounded border border-slate-300 px-2 py-1 text-sm"
                    >
                      {(Object.entries(REGRA_DIA_UTIL_LABEL) as [RegraDiaUtilCategoria, string][]).map(([valor, label]) => (
                        <option key={valor} value={valor}>
                          {label}
                        </option>
                      ))}
                    </select>
                  </div>
                  <button
                    type="button"
                    onClick={criarCategoria}
                    disabled={salvandoCategoria || !novaCategoriaNome.trim()}
                    className="rounded bg-emerald-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-emerald-700 disabled:opacity-50"
                  >
                    {salvandoCategoria ? 'Salvando...' : 'Salvar categoria'}
                  </button>
                </div>
              )}
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-slate-700">Data de início *</label>
              <input
                required
                type="date"
                value={dataInicio}
                onChange={(e) => setDataInicio(e.target.value)}
                className="w-full rounded border border-slate-300 px-3 py-2 text-sm"
              />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-slate-700">Periodicidade</label>
              <select
                value={periodicidade}
                onChange={(e) => setPeriodicidade(e.target.value as Periodicidade)}
                className="w-full rounded border border-slate-300 px-3 py-2 text-sm"
              >
                {periodicidades.map((p) => (
                  <option key={p} value={p}>
                    {p.replace('_', ' ')}
                  </option>
                ))}
              </select>
            </div>
            {periodicidade === 'personalizada_dias' && (
              <div>
                <label className="mb-1 block text-sm font-medium text-slate-700">Intervalo em dias *</label>
                <input
                  required
                  type="number"
                  min={1}
                  value={intervaloDias}
                  onChange={(e) => setIntervaloDias(e.target.value)}
                  className="w-full rounded border border-slate-300 px-3 py-2 text-sm"
                />
              </div>
            )}
            <div>
              <label className="mb-1 block text-sm font-medium text-slate-700">Condição de parada</label>
              <select
                value={condicaoParada}
                onChange={(e) => setCondicaoParada(e.target.value as 'ocorrencias' | 'data_fim')}
                className="w-full rounded border border-slate-300 px-3 py-2 text-sm"
              >
                <option value="ocorrencias">Número de ocorrências</option>
                <option value="data_fim">Data final</option>
              </select>
            </div>
            {condicaoParada === 'ocorrencias' ? (
              <div>
                <label className="mb-1 block text-sm font-medium text-slate-700">Número de ocorrências *</label>
                <input
                  required
                  type="number"
                  min={1}
                  value={numeroOcorrencias}
                  onChange={(e) => setNumeroOcorrencias(e.target.value)}
                  className="w-full rounded border border-slate-300 px-3 py-2 text-sm"
                />
              </div>
            ) : (
              <div>
                <label className="mb-1 block text-sm font-medium text-slate-700">Data final *</label>
                <input
                  required
                  type="date"
                  value={dataFim}
                  onChange={(e) => setDataFim(e.target.value)}
                  className="w-full rounded border border-slate-300 px-3 py-2 text-sm"
                />
              </div>
            )}
          </div>
          <button
            type="submit"
            className="mt-4 rounded bg-brand-700 px-4 py-2 text-sm text-white hover:bg-brand-800"
          >
            Salvar e gerar parcelas
          </button>
        </form>
      )}

      <div className="overflow-hidden rounded-xl bg-white shadow-sm ring-1 ring-slate-200/70">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
            <tr>
              <th className="px-4 py-2">Descrição</th>
              <th className="px-4 py-2">Parceiro</th>
              <th className="px-4 py-2">Valor/parcela</th>
              <th className="px-4 py-2">Periodicidade</th>
              <th className="px-4 py-2">Início</th>
              <th className="px-4 py-2" />
            </tr>
          </thead>
          <tbody>
            {carregando && (
              <tr>
                <td className="px-4 py-3 text-slate-400" colSpan={6}>
                  Carregando...
                </td>
              </tr>
            )}
            {!carregando && lancamentos.length === 0 && (
              <tr>
                <td className="px-4 py-3 text-slate-400" colSpan={6}>
                  Nenhum lançamento recorrente cadastrado
                </td>
              </tr>
            )}
            {lancamentos.map((l) => (
              <tr key={l.id} className="border-t border-slate-100">
                <td className="px-4 py-2">{l.descricao}</td>
                <td className="px-4 py-2">{nomeParceiro(l.parceiro_id)}</td>
                <td className="px-4 py-2">
                  {formatarMoeda(l.valor_parcela)}
                </td>
                <td className="px-4 py-2 capitalize">{l.periodicidade.replace('_', ' ')}</td>
                <td className="px-4 py-2">{l.data_inicio}</td>
                <td className="px-4 py-2 text-right">
                  <button onClick={() => desativar(l.id)} className="text-red-600 hover:underline">
                    Desativar
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
