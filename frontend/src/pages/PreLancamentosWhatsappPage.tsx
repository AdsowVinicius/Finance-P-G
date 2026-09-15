import { MessageCircle } from 'lucide-react'
import { useEffect, useState, type FormEvent } from 'react'
import { api } from '../lib/api'
import type { CentroCusto, Parceiro, PreLancamentoWhatsapp, Usuario } from '../types'

function formatarMoeda(valor: string | null): string {
  if (valor === null) return '—'
  return Number(valor).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })
}

function formatarDataHora(iso: string): string {
  return new Date(iso).toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' })
}

function VincularTelefone() {
  const [usuario, setUsuario] = useState<Usuario | null>(null)
  const [telefone, setTelefone] = useState('')
  const [salvando, setSalvando] = useState(false)
  const [erro, setErro] = useState<string | null>(null)
  const [sucesso, setSucesso] = useState(false)

  async function carregar() {
    const { data } = await api.get<Usuario>('/auth/me')
    setUsuario(data)
    setTelefone(data.telefone_whatsapp ?? '')
  }

  useEffect(() => {
    carregar()
  }, [])

  async function salvar(e: FormEvent) {
    e.preventDefault()
    setErro(null)
    setSucesso(false)
    setSalvando(true)
    try {
      await api.patch('/auth/me/telefone-whatsapp', { telefone_whatsapp: telefone.replace(/\D/g, '') })
      setSucesso(true)
      await carregar()
    } catch (err) {
      const detail = (err as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail
      setErro(typeof detail === 'string' ? detail : 'Não foi possível vincular esse número')
    } finally {
      setSalvando(false)
    }
  }

  return (
    <div className="rounded-xl bg-white p-5 shadow-sm ring-1 ring-slate-200/70">
      <div className="mb-3 flex items-center gap-2">
        <MessageCircle size={18} className="text-brand-700" />
        <h3 className="text-sm font-semibold text-slate-700">Seu número de WhatsApp</h3>
      </div>
      <p className="mb-3 text-xs text-slate-500">
        Vincule seu WhatsApp para poder consultar e lançar despesas por lá. Formato: DDI+DDD+número, só números (ex:
        5512988887777).
      </p>
      <form onSubmit={salvar} className="flex flex-wrap items-end gap-2">
        <input
          value={telefone}
          onChange={(e) => setTelefone(e.target.value)}
          placeholder="5512988887777"
          className="w-56 rounded border border-slate-300 px-3 py-2 text-sm"
        />
        <button
          type="submit"
          disabled={salvando || telefone.trim().length < 10}
          className="rounded bg-brand-700 px-3 py-2 text-sm text-white hover:bg-brand-800 disabled:opacity-50"
        >
          {salvando ? 'Salvando...' : 'Vincular'}
        </button>
        {usuario?.telefone_whatsapp && (
          <span className="text-xs text-emerald-600">Vinculado: {usuario.telefone_whatsapp}</span>
        )}
      </form>
      {erro && <p className="mt-2 text-xs text-red-600">{erro}</p>}
      {sucesso && <p className="mt-2 text-xs text-emerald-600">Número vinculado com sucesso.</p>}
    </div>
  )
}

interface RevisaoFormProps {
  pre: PreLancamentoWhatsapp
  parceiros: Parceiro[]
  centros: CentroCusto[]
  onResolvido: () => void
}

function RevisaoForm({ pre, parceiros, centros, onResolvido }: RevisaoFormProps) {
  const [parceiroId, setParceiroId] = useState('')
  const [centroCustoId, setCentroCustoId] = useState('')
  const [valor, setValor] = useState(pre.valor ?? '')
  const [descricao, setDescricao] = useState(pre.descricao ?? '')
  const [dataVencimento, setDataVencimento] = useState(new Date().toISOString().slice(0, 10))
  const [enviando, setEnviando] = useState(false)
  const [erro, setErro] = useState<string | null>(null)

  async function confirmar() {
    setErro(null)
    setEnviando(true)
    try {
      await api.post(`/pre-lancamentos-whatsapp/${pre.id}/confirmar`, {
        parceiro_id: parceiroId,
        centro_custo_id: centroCustoId,
        valor,
        descricao,
        data_vencimento: dataVencimento,
      })
      onResolvido()
    } catch (err) {
      const detail = (err as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail
      setErro(typeof detail === 'string' ? detail : 'Não foi possível confirmar')
    } finally {
      setEnviando(false)
    }
  }

  async function descartar() {
    setEnviando(true)
    try {
      await api.post(`/pre-lancamentos-whatsapp/${pre.id}/descartar`)
      onResolvido()
    } finally {
      setEnviando(false)
    }
  }

  return (
    <li className="px-4 py-4">
      <p className="text-xs text-slate-400">
        {formatarDataHora(pre.created_at)} · {pre.telefone}
      </p>
      <p className="mt-1 text-sm italic text-slate-600">"{pre.mensagem_original}"</p>
      <p className="mt-1 text-sm text-slate-800">
        <span className="font-semibold">{pre.tipo_operacao === 'saida' ? 'Despesa' : 'Receita'}</span>
        {' · '}
        {pre.descricao} {pre.fornecedor_texto && `· ${pre.fornecedor_texto}`} · {formatarMoeda(pre.valor)}
      </p>

      <div className="mt-3 grid grid-cols-2 gap-2 rounded bg-slate-50 p-3 sm:grid-cols-5">
        <select
          value={parceiroId}
          onChange={(e) => setParceiroId(e.target.value)}
          className="rounded border border-slate-300 px-2 py-1.5 text-xs sm:col-span-2"
        >
          <option value="">Parceiro...</option>
          {parceiros.map((p) => (
            <option key={p.id} value={p.id}>
              {p.razao_social}
            </option>
          ))}
        </select>
        <select
          value={centroCustoId}
          onChange={(e) => setCentroCustoId(e.target.value)}
          className="rounded border border-slate-300 px-2 py-1.5 text-xs"
        >
          <option value="">Centro de custo...</option>
          {centros.map((c) => (
            <option key={c.id} value={c.id}>
              {c.nome}
            </option>
          ))}
        </select>
        <input
          type="number"
          step="0.01"
          value={valor}
          onChange={(e) => setValor(e.target.value)}
          className="rounded border border-slate-300 px-2 py-1.5 text-xs"
        />
        <input
          type="date"
          value={dataVencimento}
          onChange={(e) => setDataVencimento(e.target.value)}
          className="rounded border border-slate-300 px-2 py-1.5 text-xs"
        />
        <input
          value={descricao}
          onChange={(e) => setDescricao(e.target.value)}
          placeholder="Descrição"
          className="rounded border border-slate-300 px-2 py-1.5 text-xs sm:col-span-3"
        />
        <div className="flex gap-2 sm:col-span-2">
          <button
            onClick={confirmar}
            disabled={enviando || !parceiroId || !centroCustoId || !valor || !descricao}
            className="flex-1 rounded bg-emerald-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-emerald-700 disabled:opacity-50"
          >
            Confirmar
          </button>
          <button
            onClick={descartar}
            disabled={enviando}
            className="rounded px-3 py-1.5 text-xs text-slate-500 hover:bg-slate-200"
          >
            Descartar
          </button>
        </div>
      </div>
      {erro && <p className="mt-2 text-xs text-red-600">{erro}</p>}
    </li>
  )
}

export function PreLancamentosWhatsappPage() {
  const [pendentes, setPendentes] = useState<PreLancamentoWhatsapp[]>([])
  const [parceiros, setParceiros] = useState<Parceiro[]>([])
  const [centros, setCentros] = useState<CentroCusto[]>([])
  const [carregando, setCarregando] = useState(true)

  async function carregar() {
    const [pendentesRes, parceirosRes, centrosRes] = await Promise.all([
      api.get<PreLancamentoWhatsapp[]>('/pre-lancamentos-whatsapp'),
      api.get<Parceiro[]>('/parceiros'),
      api.get<CentroCusto[]>('/centros-custo'),
    ])
    setPendentes(pendentesRes.data)
    setParceiros(parceirosRes.data)
    setCentros(centrosRes.data)
    setCarregando(false)
  }

  useEffect(() => {
    carregar()
  }, [])

  return (
    <div>
      <div className="mb-4">
        <h2 className="text-lg font-semibold text-slate-800">WhatsApp</h2>
        <p className="text-sm text-slate-500">
          Lance despesas informais e consulte suas finanças direto pelo WhatsApp — cada lançamento fica pendente de
          revisão aqui antes de virar conta a pagar/receber de verdade.
        </p>
      </div>

      <div className="mb-6">
        <VincularTelefone />
      </div>

      <div className="rounded-xl bg-white shadow-sm ring-1 ring-slate-200/70">
        <div className="flex items-center justify-between rounded-t-lg bg-amber-100 px-4 py-3 text-amber-800">
          <h3 className="font-semibold">Pendentes de revisão</h3>
          <span className="text-sm font-medium">{pendentes.length}</span>
        </div>
        {carregando ? (
          <p className="px-4 py-4 text-sm text-slate-400">Carregando...</p>
        ) : pendentes.length === 0 ? (
          <p className="px-4 py-4 text-sm text-slate-400">Nada pendente por aqui.</p>
        ) : (
          <ul className="divide-y divide-slate-100">
            {pendentes.map((pre) => (
              <RevisaoForm key={pre.id} pre={pre} parceiros={parceiros} centros={centros} onResolvido={carregar} />
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}
