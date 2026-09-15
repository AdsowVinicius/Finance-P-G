import { Fragment, useEffect, useState, type FormEvent } from 'react'
import { useSearchParams } from 'react-router-dom'
import { api } from '../lib/api'
import type { CentroCusto, ContaFinanceira, NotaFiscal, Parceiro, StatusNota, TipoNota, TipoOperacaoNota } from '../types'

const API_URL = (import.meta.env.VITE_API_URL as string) ?? 'http://localhost:8000'

const CONCILIACAO_LABEL: Record<StatusNota, string> = {
  pendente: 'Pendente',
  parcialmente_conciliada: 'Parcialmente conciliada',
  conciliada: 'Conciliada',
  cancelada: 'Cancelada',
}

const CONCILIACAO_COR: Record<StatusNota, string> = {
  pendente: 'bg-slate-100 text-slate-700',
  parcialmente_conciliada: 'bg-amber-100 text-amber-800',
  conciliada: 'bg-emerald-100 text-emerald-800',
  cancelada: 'bg-red-100 text-red-800',
}

const statusLabel: Record<NotaFiscal['status_processamento'], string> = {
  aguardando_extracao: 'Aguardando extração',
  chave_nao_encontrada: 'Chave não encontrada — cole manualmente',
  consultando_api: 'Consultando API...',
  concluido: 'Concluída',
  erro_api: 'Erro na consulta',
}

const statusCor: Record<NotaFiscal['status_processamento'], string> = {
  aguardando_extracao: 'bg-slate-100 text-slate-700',
  chave_nao_encontrada: 'bg-amber-100 text-amber-800',
  consultando_api: 'bg-blue-100 text-blue-800',
  concluido: 'bg-emerald-100 text-emerald-800',
  erro_api: 'bg-red-100 text-red-800',
}

function ChaveManualForm({ notaId, onSalvo }: { notaId: string; onSalvo: () => void }) {
  const [chave, setChave] = useState('')
  const [erro, setErro] = useState<string | null>(null)

  async function salvar() {
    setErro(null)
    try {
      await api.patch(`/notas-fiscais/${notaId}/chave-acesso`, { chave_acesso: chave })
      setChave('')
      onSalvo()
    } catch (err) {
      const detail = (err as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail
      setErro(typeof detail === 'string' ? detail : 'Chave inválida — precisa ter exatamente 44 dígitos')
    }
  }

  return (
    <div className="mt-2 flex items-center gap-2">
      <input
        value={chave}
        onChange={(e) => setChave(e.target.value.replace(/\D/g, ''))}
        placeholder="Cole os 44 dígitos da chave de acesso"
        maxLength={44}
        className="w-72 rounded border border-slate-300 px-2 py-1 text-xs"
      />
      <button
        onClick={salvar}
        disabled={chave.length !== 44}
        className="rounded bg-brand-700 px-2.5 py-1 text-xs text-white hover:bg-brand-800 disabled:opacity-40"
      >
        Salvar chave
      </button>
      {erro && <span className="text-xs text-red-600">{erro}</span>}
    </div>
  )
}

function CompletarCentroCustoForm({
  notaId,
  centros,
  onSalvo,
}: {
  notaId: string
  centros: CentroCusto[]
  onSalvo: () => void
}) {
  const [centroCustoId, setCentroCustoId] = useState('')
  const [salvando, setSalvando] = useState(false)
  const [erro, setErro] = useState<string | null>(null)

  async function salvar() {
    if (!centroCustoId) return
    setSalvando(true)
    setErro(null)
    try {
      await api.patch(`/notas-fiscais/${notaId}`, { centro_custo_id: centroCustoId })
      onSalvo()
    } catch {
      setErro('Não foi possível salvar o centro de custo')
    } finally {
      setSalvando(false)
    }
  }

  return (
    <div className="flex items-center gap-2">
      <select
        value={centroCustoId}
        onChange={(e) => setCentroCustoId(e.target.value)}
        className="rounded border border-slate-300 px-2 py-1 text-xs"
      >
        <option value="">Definir centro de custo...</option>
        {centros.map((c) => (
          <option key={c.id} value={c.id}>
            {c.nome}
          </option>
        ))}
      </select>
      <button
        onClick={salvar}
        disabled={!centroCustoId || salvando}
        className="rounded bg-brand-700 px-2 py-1 text-xs text-white hover:bg-brand-800 disabled:opacity-40"
      >
        {salvando ? 'Salvando...' : 'Salvar'}
      </button>
      {erro && <span className="text-xs text-red-600">{erro}</span>}
    </div>
  )
}

function ReprocessarButton({ notaId, onReprocessado }: { notaId: string; onReprocessado: () => void }) {
  const [enviando, setEnviando] = useState(false)

  async function reprocessar() {
    setEnviando(true)
    try {
      await api.post(`/notas-fiscais/${notaId}/reprocessar`)
      onReprocessado()
    } finally {
      setEnviando(false)
    }
  }

  return (
    <button
      onClick={reprocessar}
      disabled={enviando}
      className="mt-2 rounded bg-brand-700 px-2.5 py-1 text-xs text-white hover:bg-brand-800 disabled:opacity-40"
    >
      {enviando ? 'Reprocessando...' : 'Tentar de novo'}
    </button>
  )
}

function BoletoForm({ contaId, onSalvo }: { contaId: string; onSalvo: () => void }) {
  const [arquivo, setArquivo] = useState<File | null>(null)
  const [linhaDigitavel, setLinhaDigitavel] = useState('')
  const [codigoBarras, setCodigoBarras] = useState('')
  const [enviando, setEnviando] = useState(false)

  async function salvar() {
    if (!arquivo) return
    setEnviando(true)
    try {
      const form = new FormData()
      form.append('arquivo', arquivo)
      if (linhaDigitavel) form.append('linha_digitavel', linhaDigitavel)
      if (codigoBarras) form.append('codigo_barras', codigoBarras)
      await api.post(`/contas-financeiras/${contaId}/boleto`, form)
      onSalvo()
    } finally {
      setEnviando(false)
    }
  }

  return (
    <div className="mt-1 flex flex-wrap items-end gap-2">
      <input
        type="file"
        accept="application/pdf"
        onChange={(e) => setArquivo(e.target.files?.[0] ?? null)}
        className="text-xs"
      />
      <input
        value={linhaDigitavel}
        onChange={(e) => setLinhaDigitavel(e.target.value)}
        placeholder="Linha digitável"
        className="w-44 rounded border border-slate-300 px-2 py-1 text-xs"
      />
      <button
        onClick={salvar}
        disabled={!arquivo || enviando}
        className="rounded bg-brand-700 px-2 py-1 text-xs text-white hover:bg-brand-800 disabled:opacity-40"
      >
        {enviando ? '...' : 'Salvar'}
      </button>
    </div>
  )
}

const statusContaLabel: Record<ContaFinanceira['status'], string> = {
  pendente: 'Pendente',
  pago: 'Pago',
  atrasado: 'Atrasado',
  cancelado: 'Cancelado',
}

function ParcelasDaNota({ notaId }: { notaId: string }) {
  const [parcelas, setParcelas] = useState<ContaFinanceira[] | null>(null)
  const [boletoAberto, setBoletoAberto] = useState<string | null>(null)

  async function carregar() {
    const res = await api.get<ContaFinanceira[]>('/contas-financeiras', { params: { nota_fiscal_id: notaId } })
    setParcelas(res.data)
  }

  useEffect(() => {
    carregar()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [notaId])

  if (parcelas === null) return <p className="px-4 py-2 text-xs text-slate-400">Carregando parcelas...</p>
  if (parcelas.length === 0) {
    return <p className="px-4 py-2 text-xs text-slate-400">Nenhuma parcela gerada ainda (aguardando a nota concluir o processamento).</p>
  }

  return (
    <table className="w-full text-xs">
      <thead className="bg-slate-50 text-left text-slate-500">
        <tr>
          <th className="px-4 py-1.5">Parcela</th>
          <th className="px-4 py-1.5">Vencimento</th>
          <th className="px-4 py-1.5">Valor</th>
          <th className="px-4 py-1.5">Status</th>
          <th className="px-4 py-1.5">Boleto</th>
        </tr>
      </thead>
      <tbody>
        {parcelas.map((p) => (
          <tr key={p.id} className="border-t border-slate-100">
            <td className="px-4 py-1.5">{p.numero_parcela}/{p.total_parcelas}</td>
            <td className="px-4 py-1.5">{p.data_vencimento}</td>
            <td className="px-4 py-1.5">
              {Number(p.valor).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })}
            </td>
            <td className="px-4 py-1.5">{statusContaLabel[p.status]}</td>
            <td className="px-4 py-1.5">
              {p.boleto_arquivo_path ? (
                <a
                  href={`${API_URL}/storage/${p.boleto_arquivo_path}`}
                  target="_blank"
                  rel="noreferrer"
                  className="text-slate-700 underline"
                >
                  ver boleto
                </a>
              ) : boletoAberto === p.id ? (
                <BoletoForm
                  contaId={p.id}
                  onSalvo={() => {
                    setBoletoAberto(null)
                    carregar()
                  }}
                />
              ) : (
                <button onClick={() => setBoletoAberto(p.id)} className="text-slate-700 underline">
                  anexar boleto
                </button>
              )}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

export function NotasFiscaisPage() {
  const [searchParams] = useSearchParams()
  const [notas, setNotas] = useState<NotaFiscal[]>([])
  const [parceiros, setParceiros] = useState<Parceiro[]>([])
  const [centros, setCentros] = useState<CentroCusto[]>([])
  const [statusFiltro, setStatusFiltro] = useState<StatusNota | ''>((searchParams.get('status') as StatusNota) ?? '')
  const [carregando, setCarregando] = useState(true)
  const [mostrarForm, setMostrarForm] = useState(false)
  const [enviando, setEnviando] = useState(false)
  const [erro, setErro] = useState<string | null>(null)
  const [expandida, setExpandida] = useState<string | null>(null)

  const [arquivo, setArquivo] = useState<File | null>(null)
  const [parceiroId, setParceiroId] = useState('')
  const [centroCustoId, setCentroCustoId] = useState('')
  const [tipo, setTipo] = useState<TipoNota>('nfe')
  const [tipoOperacao, setTipoOperacao] = useState<TipoOperacaoNota>('entrada')
  const [valorTotal, setValorTotal] = useState('')
  const [dataEmissao, setDataEmissao] = useState('')
  const [despesaFixa, setDespesaFixa] = useState(false)
  const [despesaParcelada, setDespesaParcelada] = useState(false)
  const [numeroParcelas, setNumeroParcelas] = useState('1')

  async function carregar(status: StatusNota | '' = statusFiltro) {
    setCarregando(true)
    const [notasRes, parcRes, centrosRes] = await Promise.all([
      api.get<NotaFiscal[]>('/notas-fiscais', { params: status ? { status } : {} }),
      api.get<Parceiro[]>('/parceiros'),
      api.get<CentroCusto[]>('/centros-custo'),
    ])
    setNotas(notasRes.data)
    setParceiros(parcRes.data)
    setCentros(centrosRes.data)
    setCarregando(false)
  }

  useEffect(() => {
    carregar()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  function mudarStatusFiltro(status: StatusNota | '') {
    setStatusFiltro(status)
    carregar(status)
  }

  function nomeParceiro(id: string): string {
    return parceiros.find((p) => p.id === id)?.razao_social ?? '—'
  }

  function nomeCentroCusto(id: string | null): string | null {
    if (!id) return null
    return centros.find((c) => c.id === id)?.nome ?? null
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setErro(null)
    if (!arquivo) {
      setErro('Selecione o PDF da nota')
      return
    }
    setEnviando(true)
    try {
      const form = new FormData()
      form.append('arquivo', arquivo)
      form.append('centro_custo_id', centroCustoId)
      form.append('tipo_operacao', tipoOperacao)
      form.append('tipo', tipo)
      // parceiro/valor/data: opcionais — se a chave for achada no PDF, a API
      // de consulta preenche sozinha. Só manda se o usuário preencheu.
      if (parceiroId) form.append('parceiro_id', parceiroId)
      if (valorTotal) form.append('valor_total', valorTotal)
      if (dataEmissao) form.append('data_emissao', dataEmissao)
      form.append('despesa_fixa', String(despesaFixa))
      form.append('despesa_parcelada', String(despesaParcelada))
      form.append('numero_parcelas', numeroParcelas)

      await api.post('/notas-fiscais', form)

      setArquivo(null)
      setParceiroId('')
      setValorTotal('')
      setDataEmissao('')
      setDespesaFixa(false)
      setDespesaParcelada(false)
      setNumeroParcelas('1')
      setMostrarForm(false)
      await carregar()
    } catch (err) {
      const detail = (err as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail
      setErro(typeof detail === 'string' ? detail : 'Não foi possível cadastrar a nota fiscal')
    } finally {
      setEnviando(false)
    }
  }

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-lg font-semibold text-slate-800">Notas Fiscais</h2>
        <div className="flex items-center gap-2">
          <label className="text-xs font-medium text-slate-600">Conciliação</label>
          <select
            value={statusFiltro}
            onChange={(e) => mudarStatusFiltro(e.target.value as StatusNota | '')}
            className="rounded border border-slate-300 px-2 py-1.5 text-sm"
          >
            <option value="">Todas</option>
            {(Object.keys(CONCILIACAO_LABEL) as StatusNota[]).map((s) => (
              <option key={s} value={s}>
                {CONCILIACAO_LABEL[s]}
              </option>
            ))}
          </select>
          <button
            onClick={() => setMostrarForm((v) => !v)}
            className="rounded bg-brand-700 px-3 py-1.5 text-sm text-white hover:bg-brand-800"
          >
            {mostrarForm ? 'Cancelar' : 'Cadastrar nota fiscal'}
          </button>
        </div>
      </div>

      {mostrarForm && (
        <form onSubmit={handleSubmit} className="mb-6 rounded-lg bg-white p-4 shadow">
          {erro && <div className="mb-3 rounded bg-red-50 px-3 py-2 text-sm text-red-700">{erro}</div>}
          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700">PDF da nota (DANFE) *</label>
            <input
              required
              type="file"
              accept="application/pdf"
              onChange={(e) => setArquivo(e.target.files?.[0] ?? null)}
              className="block w-full text-sm"
            />
            <p className="mt-1 text-xs text-slate-500">
              A chave de acesso é extraída automaticamente do PDF, e o fornecedor/valor/data de emissão vêm
              sozinhos da consulta à API — deixe os campos abaixo em branco pra isso acontecer sem digitar nada.
              Se a chave não for encontrada (ex: PDF escaneado) ou você preferir preencher já, é só digitar.
            </p>
          </div>

          <div className="mt-4 grid grid-cols-2 gap-4">
            <div>
              <label className="mb-1 block text-sm font-medium text-slate-700">Parceiro (opcional)</label>
              <select
                value={parceiroId}
                onChange={(e) => setParceiroId(e.target.value)}
                className="w-full rounded border border-slate-300 px-3 py-2 text-sm"
              >
                <option value="">Deixar a API identificar</option>
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
              <label className="mb-1 block text-sm font-medium text-slate-700">Tipo de documento</label>
              <select
                value={tipo}
                onChange={(e) => setTipo(e.target.value as TipoNota)}
                className="w-full rounded border border-slate-300 px-3 py-2 text-sm"
              >
                <option value="nfe">NF-e</option>
                <option value="nfse">NFS-e</option>
              </select>
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-slate-700">Operação</label>
              <select
                value={tipoOperacao}
                onChange={(e) => setTipoOperacao(e.target.value as TipoOperacaoNota)}
                className="w-full rounded border border-slate-300 px-3 py-2 text-sm"
              >
                <option value="entrada">Despesa (compra)</option>
                <option value="saida">Receita (venda)</option>
              </select>
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-slate-700">Valor total (opcional)</label>
              <input
                type="number"
                step="0.01"
                placeholder="Deixar a API preencher"
                value={valorTotal}
                onChange={(e) => setValorTotal(e.target.value)}
                className="w-full rounded border border-slate-300 px-3 py-2 text-sm"
              />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-slate-700">Data de emissão (opcional)</label>
              <input
                type="date"
                value={dataEmissao}
                onChange={(e) => setDataEmissao(e.target.value)}
                className="w-full rounded border border-slate-300 px-3 py-2 text-sm"
              />
            </div>
            <div className="flex items-center gap-2">
              <input
                id="despesa_fixa"
                type="checkbox"
                checked={despesaFixa}
                onChange={(e) => setDespesaFixa(e.target.checked)}
              />
              <label htmlFor="despesa_fixa" className="text-sm text-slate-700">
                Despesa fixa
              </label>
            </div>
            <div className="flex items-center gap-2">
              <input
                id="despesa_parcelada"
                type="checkbox"
                checked={despesaParcelada}
                onChange={(e) => setDespesaParcelada(e.target.checked)}
              />
              <label htmlFor="despesa_parcelada" className="text-sm text-slate-700">
                Parcelada
              </label>
            </div>
            {despesaParcelada && (
              <div>
                <label className="mb-1 block text-sm font-medium text-slate-700">Número de parcelas</label>
                <input
                  type="number"
                  min={1}
                  value={numeroParcelas}
                  onChange={(e) => setNumeroParcelas(e.target.value)}
                  className="w-full rounded border border-slate-300 px-3 py-2 text-sm"
                />
              </div>
            )}
          </div>

          <button
            type="submit"
            disabled={enviando}
            className="mt-4 rounded bg-brand-700 px-4 py-2 text-sm text-white hover:bg-brand-800 disabled:opacity-50"
          >
            {enviando ? 'Enviando...' : 'Cadastrar'}
          </button>
        </form>
      )}

      <div className="overflow-hidden rounded-xl bg-white shadow-sm ring-1 ring-slate-200/70">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
            <tr>
              <th className="px-4 py-2">Parceiro</th>
              <th className="px-4 py-2">Centro de custo</th>
              <th className="px-4 py-2">Valor</th>
              <th className="px-4 py-2">Emissão</th>
              <th className="px-4 py-2">Parcelas</th>
              <th className="px-4 py-2">PDF</th>
              <th className="px-4 py-2">Processamento</th>
              <th className="px-4 py-2">Conciliação</th>
              <th className="px-4 py-2" />
            </tr>
          </thead>
          <tbody>
            {carregando && (
              <tr>
                <td className="px-4 py-3 text-slate-400" colSpan={9}>
                  Carregando...
                </td>
              </tr>
            )}
            {!carregando && notas.length === 0 && (
              <tr>
                <td className="px-4 py-3 text-slate-400" colSpan={9}>
                  Nenhuma nota fiscal encontrada com esse filtro
                </td>
              </tr>
            )}
            {notas.map((n) => (
              <Fragment key={n.id}>
                <tr className="border-t border-slate-100 align-top">
                  <td className="px-4 py-2">{nomeParceiro(n.parceiro_id)}</td>
                  <td className="px-4 py-2">
                    {nomeCentroCusto(n.centro_custo_id) ?? (
                      <CompletarCentroCustoForm notaId={n.id} centros={centros} onSalvo={carregar} />
                    )}
                  </td>
                  <td className="px-4 py-2">
                    {Number(n.valor_total).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })}
                  </td>
                  <td className="px-4 py-2">{n.data_emissao}</td>
                  <td className="px-4 py-2">{n.despesa_parcelada ? `${n.numero_parcelas}x` : 'à vista'}</td>
                  <td className="px-4 py-2">
                    {n.arquivo_pdf_path && (
                      <a
                        href={`${API_URL}/storage/${n.arquivo_pdf_path}`}
                        target="_blank"
                        rel="noreferrer"
                        className="text-slate-700 underline"
                      >
                        ver PDF
                      </a>
                    )}
                  </td>
                  <td className="px-4 py-2">
                    <span className={`rounded px-2 py-0.5 text-xs ${statusCor[n.status_processamento]}`}>
                      {statusLabel[n.status_processamento]}
                    </span>
                    {n.status_processamento === 'chave_nao_encontrada' && (
                      <ChaveManualForm notaId={n.id} onSalvo={carregar} />
                    )}
                    {n.status_processamento === 'erro_api' && (
                      <div>
                        <ReprocessarButton notaId={n.id} onReprocessado={carregar} />
                      </div>
                    )}
                  </td>
                  <td className="px-4 py-2">
                    <span className={`rounded px-2 py-0.5 text-xs ${CONCILIACAO_COR[n.status]}`}>{CONCILIACAO_LABEL[n.status]}</span>
                  </td>
                  <td className="px-4 py-2 text-right">
                    <button
                      onClick={() => setExpandida(expandida === n.id ? null : n.id)}
                      className="text-slate-600 underline"
                    >
                      {expandida === n.id ? 'ocultar' : 'ver parcelas'}
                    </button>
                  </td>
                </tr>
                {expandida === n.id && (
                  <tr>
                    <td colSpan={9} className="bg-slate-50 p-0">
                      <ParcelasDaNota notaId={n.id} />
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
