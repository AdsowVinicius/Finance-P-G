import { Fragment, useEffect, useState, type FormEvent } from 'react'
import { useAuth } from '../contexts/AuthContext'
import { api } from '../lib/api'
import type { ContaBancaria, ContaFinanceira, ExtratoImportado, FormatoExtrato, LancamentoExtrato } from '../types'

function formatarMoeda(valor: string): string {
  return Number(valor).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })
}

function formatarData(data: string): string {
  const [ano, mes, dia] = data.split('-')
  return `${dia}/${mes}/${ano}`
}

function CandidatoConciliacao({ lancamento, onResolvido }: { lancamento: LancamentoExtrato; onResolvido: () => void }) {
  const [candidatas, setCandidatas] = useState<ContaFinanceira[] | null>(null)
  const [selecionadas, setSelecionadas] = useState<Set<string>>(new Set())
  const [enviando, setEnviando] = useState(false)
  const [erro, setErro] = useState<string | null>(null)

  useEffect(() => {
    api.get<ContaFinanceira[]>(`/conciliacoes/${lancamento.id}/candidatas`).then((res) => setCandidatas(res.data))
  }, [lancamento.id])

  function alternar(id: string) {
    setSelecionadas((atual) => {
      const novo = new Set(atual)
      if (novo.has(id)) novo.delete(id)
      else novo.add(id)
      return novo
    })
  }

  const soma = (candidatas ?? [])
    .filter((c) => selecionadas.has(c.id))
    .reduce((s, c) => s + Number(c.valor), 0)
  const bate = Math.abs(soma - Number(lancamento.valor)) < 0.001 && selecionadas.size > 0

  async function confirmar() {
    setErro(null)
    setEnviando(true)
    try {
      await api.post(`/conciliacoes/${lancamento.id}/confirmar`, { contas_financeira_ids: [...selecionadas] })
      onResolvido()
    } catch (err) {
      const detail = (err as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail
      setErro(typeof detail === 'string' ? detail : 'Não foi possível confirmar a conciliação')
    } finally {
      setEnviando(false)
    }
  }

  async function ignorar() {
    setEnviando(true)
    try {
      await api.post(`/conciliacoes/${lancamento.id}/ignorar`)
      onResolvido()
    } finally {
      setEnviando(false)
    }
  }

  return (
    <div className="mt-2 rounded bg-slate-50 p-3">
      <p className="mb-2 text-xs text-slate-500">
        Selecione a(s) conta(s) que somam exatamente {formatarMoeda(lancamento.valor)} (o valor do lançamento) — pode
        marcar mais de uma pra quitar um pagamento dividido em parcelas.
      </p>
      {candidatas === null && <p className="text-xs text-slate-400">Carregando candidatas...</p>}
      {candidatas !== null && candidatas.length === 0 && (
        <p className="text-xs text-slate-400">Nenhuma conta pendente na mesma direção pra conciliar.</p>
      )}
      {candidatas !== null && candidatas.length > 0 && (
        <ul className="max-h-64 space-y-1 overflow-y-auto">
          {candidatas.map((c) => (
            <li key={c.id}>
              <label className="flex cursor-pointer items-center gap-2 rounded px-2 py-1 text-xs hover:bg-white">
                <input type="checkbox" checked={selecionadas.has(c.id)} onChange={() => alternar(c.id)} />
                <span className="flex-1">
                  {c.descricao}
                  {c.total_parcelas > 1 && (
                    <span className="text-slate-400">
                      {' '}
                      ({c.numero_parcela}/{c.total_parcelas})
                    </span>
                  )}
                  {' · vence '}
                  {formatarData(c.data_vencimento)}
                  {c.status === 'atrasado' && <span className="text-red-600"> (atrasado)</span>}
                </span>
                <span className="font-medium">{formatarMoeda(c.valor)}</span>
              </label>
            </li>
          ))}
        </ul>
      )}
      <div className="mt-2 flex items-center justify-between gap-2">
        <span className={`text-xs font-medium ${bate ? 'text-emerald-600' : 'text-slate-500'}`}>
          Selecionado: {formatarMoeda(String(soma))} / {formatarMoeda(lancamento.valor)}
        </span>
        <div className="flex gap-2">
          <button
            onClick={ignorar}
            disabled={enviando}
            className="rounded px-3 py-1.5 text-xs text-slate-500 hover:bg-slate-200 disabled:opacity-50"
          >
            Ignorar lançamento
          </button>
          <button
            onClick={confirmar}
            disabled={enviando || !bate}
            className="rounded bg-emerald-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-emerald-700 disabled:opacity-50"
          >
            Confirmar conciliação
          </button>
        </div>
      </div>
      {erro && <p className="mt-2 text-xs text-red-600">{erro}</p>}
    </div>
  )
}

function ConciliacaoManualSection({ contasBancarias }: { contasBancarias: ContaBancaria[] }) {
  const { usuario } = useAuth()
  const podeExcluir = usuario?.papel === 'admin' || usuario?.papel === 'master'
  const [pendentes, setPendentes] = useState<LancamentoExtrato[]>([])
  const [carregando, setCarregando] = useState(true)
  const [expandido, setExpandido] = useState<string | null>(null)

  async function carregar() {
    setCarregando(true)
    const { data } = await api.get<LancamentoExtrato[]>('/conciliacoes/pendentes')
    setPendentes(data)
    setCarregando(false)
  }

  useEffect(() => {
    carregar()
  }, [])

  function nomeConta(id: string): string {
    return contasBancarias.find((c) => c.id === id)?.apelido ?? '—'
  }

  async function excluir(lancamento: LancamentoExtrato) {
    const confirmado = window.confirm(
      `Excluir de vez o lançamento "${lancamento.descricao ?? 'sem descrição'}" (${formatarMoeda(lancamento.valor)})? ` +
        'Essa ação não pode ser desfeita (fica registrada na auditoria).',
    )
    if (!confirmado) return
    await api.delete(`/extratos/lancamentos/${lancamento.id}`)
    carregar()
  }

  if (!carregando && pendentes.length === 0) return null

  return (
    <div className="mb-6 overflow-hidden rounded-xl bg-white shadow-sm ring-1 ring-slate-200/70">
      <div className="flex items-center justify-between rounded-t-lg bg-amber-100 px-4 py-3 text-amber-800">
        <h3 className="font-semibold">Conciliação manual pendente</h3>
        <span className="text-sm font-medium">{pendentes.length}</span>
      </div>
      {carregando ? (
        <p className="px-4 py-4 text-sm text-slate-400">Carregando...</p>
      ) : (
        <ul className="divide-y divide-slate-100">
          {pendentes.map((l) => (
            <li key={l.id} className="px-4 py-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <p className="text-sm font-medium text-slate-800">{l.descricao ?? 'Sem descrição'}</p>
                  <p className="text-xs text-slate-500">
                    {nomeConta(l.conta_bancaria_id)} · {formatarData(l.data)} ·{' '}
                    {l.tipo === 'credito' ? 'Entrou na conta' : 'Saiu da conta'}
                  </p>
                </div>
                <div className="flex items-center gap-3">
                  <span className="text-sm font-semibold text-slate-800">{formatarMoeda(l.valor)}</span>
                  <button
                    onClick={() => setExpandido(expandido === l.id ? null : l.id)}
                    className="rounded bg-brand-700 px-3 py-1.5 text-xs font-medium text-white hover:bg-brand-800"
                  >
                    {expandido === l.id ? 'Ocultar' : 'Conciliar'}
                  </button>
                  {podeExcluir && (
                    <button
                      onClick={() => excluir(l)}
                      className="rounded px-3 py-1.5 text-xs text-red-600 hover:bg-red-50"
                    >
                      Excluir
                    </button>
                  )}
                </div>
              </div>
              {expandido === l.id && (
                <CandidatoConciliacao
                  lancamento={l}
                  onResolvido={() => {
                    setExpandido(null)
                    carregar()
                  }}
                />
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

const statusLabel: Record<ExtratoImportado['status'], string> = {
  processando: 'Processando...',
  concluido: 'Concluído',
  erro: 'Erro',
}

const statusCor: Record<ExtratoImportado['status'], string> = {
  processando: 'bg-blue-100 text-blue-800',
  concluido: 'bg-emerald-100 text-emerald-800',
  erro: 'bg-red-100 text-red-800',
}

const conciliacaoLabel: Record<LancamentoExtrato['status_conciliacao'], string> = {
  pendente: 'Pendente',
  conciliado: 'Conciliado',
  parcial: 'Parcial',
  divergente: 'Divergente',
  ignorado: 'Ignorado',
}

function LancamentosDoExtrato({ extratoId }: { extratoId: string }) {
  const [lancamentos, setLancamentos] = useState<LancamentoExtrato[] | null>(null)

  useEffect(() => {
    api.get<LancamentoExtrato[]>(`/extratos/${extratoId}/lancamentos`).then((res) => setLancamentos(res.data))
  }, [extratoId])

  if (lancamentos === null) return <p className="px-4 py-2 text-xs text-slate-400">Carregando lançamentos...</p>
  if (lancamentos.length === 0) return <p className="px-4 py-2 text-xs text-slate-400">Nenhum lançamento novo (já importado antes?)</p>

  return (
    <table className="w-full text-xs">
      <thead className="bg-slate-50 text-left text-slate-500">
        <tr>
          <th className="px-4 py-1.5">Data</th>
          <th className="px-4 py-1.5">Descrição</th>
          <th className="px-4 py-1.5">Valor</th>
          <th className="px-4 py-1.5">Tipo</th>
          <th className="px-4 py-1.5">Conciliação</th>
        </tr>
      </thead>
      <tbody>
        {lancamentos.map((l) => (
          <tr key={l.id} className="border-t border-slate-100">
            <td className="px-4 py-1.5">{l.data}</td>
            <td className="px-4 py-1.5">{l.descricao ?? '—'}</td>
            <td className="px-4 py-1.5">
              {Number(l.valor).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })}
            </td>
            <td className="px-4 py-1.5 capitalize">{l.tipo}</td>
            <td className="px-4 py-1.5">
              <span
                className={
                  l.status_conciliacao === 'conciliado'
                    ? 'rounded bg-emerald-100 px-2 py-0.5 text-emerald-800'
                    : 'rounded bg-amber-100 px-2 py-0.5 text-amber-800'
                }
              >
                {conciliacaoLabel[l.status_conciliacao]}
              </span>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

export function ExtratosPage() {
  const [extratos, setExtratos] = useState<ExtratoImportado[]>([])
  const [contas, setContas] = useState<ContaBancaria[]>([])
  const [carregando, setCarregando] = useState(true)
  const [mostrarForm, setMostrarForm] = useState(false)
  const [enviando, setEnviando] = useState(false)
  const [erro, setErro] = useState<string | null>(null)
  const [expandido, setExpandido] = useState<string | null>(null)

  const [arquivo, setArquivo] = useState<File | null>(null)
  const [contaBancariaId, setContaBancariaId] = useState('')
  const [formato, setFormato] = useState<FormatoExtrato>('ofx')

  async function carregar() {
    setCarregando(true)
    const [extratosRes, contasRes] = await Promise.all([
      api.get<ExtratoImportado[]>('/extratos'),
      api.get<ContaBancaria[]>('/contas-bancarias'),
    ])
    setExtratos(extratosRes.data)
    setContas(contasRes.data)
    setCarregando(false)
  }

  useEffect(() => {
    carregar()
  }, [])

  function nomeConta(id: string): string {
    return contas.find((c) => c.id === id)?.apelido ?? '—'
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setErro(null)
    if (!arquivo) {
      setErro('Selecione o arquivo do extrato (.ofx ou .csv)')
      return
    }
    setEnviando(true)
    try {
      const form = new FormData()
      form.append('arquivo', arquivo)
      form.append('conta_bancaria_id', contaBancariaId)
      form.append('formato', formato)

      await api.post('/extratos', form)

      setArquivo(null)
      setMostrarForm(false)
      await carregar()
    } catch (err) {
      const detail = (err as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail
      setErro(typeof detail === 'string' ? detail : 'Não foi possível importar o extrato')
    } finally {
      setEnviando(false)
    }
  }

  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-lg font-semibold text-slate-800">Extrato Bancário / Conciliação</h2>
        <button
          onClick={() => setMostrarForm((v) => !v)}
          className="rounded bg-brand-700 px-3 py-1.5 text-sm text-white hover:bg-brand-800"
        >
          {mostrarForm ? 'Cancelar' : 'Importar extrato'}
        </button>
      </div>

      {mostrarForm && (
        <form onSubmit={handleSubmit} className="mb-6 rounded-lg bg-white p-4 shadow">
          {erro && <div className="mb-3 rounded bg-red-50 px-3 py-2 text-sm text-red-700">{erro}</div>}
          <div className="grid grid-cols-3 gap-4">
            <div>
              <label className="mb-1 block text-sm font-medium text-slate-700">Conta bancária *</label>
              <select
                required
                value={contaBancariaId}
                onChange={(e) => setContaBancariaId(e.target.value)}
                className="w-full rounded border border-slate-300 px-3 py-2 text-sm"
              >
                <option value="">Selecione...</option>
                {contas.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.apelido}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-slate-700">Formato</label>
              <select
                value={formato}
                onChange={(e) => setFormato(e.target.value as FormatoExtrato)}
                className="w-full rounded border border-slate-300 px-3 py-2 text-sm"
              >
                <option value="ofx">OFX</option>
                <option value="csv">CSV</option>
              </select>
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-slate-700">Arquivo *</label>
              <input
                required
                type="file"
                accept={formato === 'ofx' ? '.ofx' : '.csv'}
                onChange={(e) => setArquivo(e.target.files?.[0] ?? null)}
                className="block w-full text-sm"
              />
            </div>
          </div>
          <p className="mt-2 text-xs text-slate-500">
            A conciliação (valor exato + tolerância de data, com matching parcial/split) roda automaticamente em
            background assim que o arquivo é importado.
          </p>
          <button
            type="submit"
            disabled={enviando}
            className="mt-4 rounded bg-brand-700 px-4 py-2 text-sm text-white hover:bg-brand-800 disabled:opacity-50"
          >
            {enviando ? 'Enviando...' : 'Importar'}
          </button>
        </form>
      )}

      <ConciliacaoManualSection contasBancarias={contas} />

      <div className="overflow-hidden rounded-xl bg-white shadow-sm ring-1 ring-slate-200/70">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
            <tr>
              <th className="px-4 py-2">Conta</th>
              <th className="px-4 py-2">Formato</th>
              <th className="px-4 py-2">Importado em</th>
              <th className="px-4 py-2">Status</th>
              <th className="px-4 py-2" />
            </tr>
          </thead>
          <tbody>
            {carregando && (
              <tr>
                <td className="px-4 py-3 text-slate-400" colSpan={5}>
                  Carregando...
                </td>
              </tr>
            )}
            {!carregando && extratos.length === 0 && (
              <tr>
                <td className="px-4 py-3 text-slate-400" colSpan={5}>
                  Nenhum extrato importado ainda
                </td>
              </tr>
            )}
            {extratos.map((ext) => (
              <Fragment key={ext.id}>
                <tr className="border-t border-slate-100">
                  <td className="px-4 py-2">{nomeConta(ext.conta_bancaria_id)}</td>
                  <td className="px-4 py-2 uppercase">{ext.formato}</td>
                  <td className="px-4 py-2">{new Date(ext.created_at).toLocaleString('pt-BR')}</td>
                  <td className="px-4 py-2">
                    <span className={`rounded px-2 py-0.5 text-xs ${statusCor[ext.status]}`}>
                      {statusLabel[ext.status]}
                    </span>
                    {ext.mensagem_erro && <p className="mt-1 text-xs text-red-600">{ext.mensagem_erro}</p>}
                  </td>
                  <td className="px-4 py-2 text-right">
                    <button
                      onClick={() => setExpandido(expandido === ext.id ? null : ext.id)}
                      className="text-slate-600 underline"
                    >
                      {expandido === ext.id ? 'ocultar' : 'ver lançamentos'}
                    </button>
                  </td>
                </tr>
                {expandido === ext.id && (
                  <tr>
                    <td colSpan={5} className="bg-slate-50 p-0">
                      <LancamentosDoExtrato extratoId={ext.id} />
                    </td>
                  </tr>
                )}
              </Fragment>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
