import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { useAuth } from '../contexts/AuthContext'
import { api } from '../lib/api'
import { extractApiError } from '../lib/apiError'
import { formatarMoeda } from '../lib/formatters'
import type { ContaBancaria } from '../types'

// Widget oficial da Pluggy (Pluggy Connect). Se a Pluggy publicar uma versão
// nova, ajuste aqui: https://docs.pluggy.ai/docs/pluggy-connect
const PLUGGY_CONNECT_SCRIPT = 'https://cdn.pluggy.ai/pluggy-connect/v2.7.0/pluggy-connect.js'

interface CertificadoStatus {
  criptografia_configurada: boolean
  ambiente: string
  certificado: {
    id: string
    cnpj: string
    razao_social: string
    valido_ate: string
    ult_nsu: string
    max_nsu: string | null
    ult_sincronizacao: string | null
    ult_mensagem_sefaz: string | null
    bloqueado_ate: string | null
  } | null
  dias_para_vencer: number | null
  vencendo_em_breve: boolean
}

interface NfeRecebida {
  id: string
  chave_acesso: string
  nome_emitente: string | null
  cnpj_emitente: string | null
  valor_total: string | null
  data_emissao: string | null
  tipo_documento: 'resumo' | 'completo'
  nota_cadastrada: boolean
}

interface Conexao {
  id: string
  item_id: string
  conector_nome: string | null
  status: string | null
}

interface ContaVinculada {
  id: string
  apelido: string
  open_finance_conta_id: string
  open_finance_sincronizado_em: string | null
}

interface OpenFinanceStatus {
  configurado: boolean
  conexoes: Conexao[]
  contas_vinculadas: ContaVinculada[]
}

interface ContaRemota {
  id: string
  nome: string | null
  tipo: string | null
  subtipo: string | null
  numero: string | null
  saldo: string | null
}

declare global {
  interface Window {
    PluggyConnect?: new (opts: {
      connectToken: string
      onSuccess: (data: { item: { id: string } }) => void
      onError?: (err: unknown) => void
    }) => { init: () => void }
  }
}

function carregarScriptPluggy(): Promise<void> {
  if (window.PluggyConnect) return Promise.resolve()
  return new Promise((resolve, reject) => {
    const s = document.createElement('script')
    s.src = PLUGGY_CONNECT_SCRIPT
    s.onload = () => resolve()
    s.onerror = () => reject(new Error('Não foi possível carregar o Pluggy Connect'))
    document.body.appendChild(s)
  })
}

const dataHora = (iso: string | null) => (iso ? new Date(iso).toLocaleString('pt-BR') : '—')

function Mensagem({ tipo, texto }: { tipo: 'erro' | 'ok'; texto: string }) {
  const cor = tipo === 'erro' ? 'bg-red-50 text-red-700' : 'bg-green-50 text-green-700'
  return <div className={`mb-3 rounded px-3 py-2 text-sm ${cor}`}>{texto}</div>
}

function SecaoCertificado({ podeAdministrar, podeEscrever }: { podeAdministrar: boolean; podeEscrever: boolean }) {
  const [status, setStatus] = useState<CertificadoStatus | null>(null)
  const [nfes, setNfes] = useState<NfeRecebida[]>([])
  const [arquivo, setArquivo] = useState<File | null>(null)
  const [senha, setSenha] = useState('')
  const [msg, setMsg] = useState<{ tipo: 'erro' | 'ok'; texto: string } | null>(null)

  const carregar = useCallback(async () => {
    const [st, lista] = await Promise.all([
      api.get<CertificadoStatus>('/certificados/status'),
      api.get<NfeRecebida[]>('/certificados/nfes-recebidas'),
    ])
    setStatus(st.data)
    setNfes(lista.data)
  }, [])

  useEffect(() => {
    carregar()
  }, [carregar])

  async function enviar(e: FormEvent) {
    e.preventDefault()
    if (!arquivo) return
    setMsg(null)
    const form = new FormData()
    form.append('arquivo', arquivo)
    form.append('senha', senha)
    try {
      await api.post('/certificados', form)
      setSenha('')
      setArquivo(null)
      setMsg({ tipo: 'ok', texto: 'Certificado cadastrado' })
      await carregar()
    } catch (err) {
      setMsg({ tipo: 'erro', texto: extractApiError(err, 'Não foi possível cadastrar o certificado') })
    }
  }

  async function sincronizar() {
    setMsg(null)
    try {
      await api.post('/certificados/sincronizar')
      setMsg({ tipo: 'ok', texto: 'Sincronização com a SEFAZ enfileirada — atualize em instantes' })
    } catch (err) {
      setMsg({ tipo: 'erro', texto: extractApiError(err, 'Não foi possível sincronizar') })
    }
  }

  async function desativar(id: string) {
    await api.post(`/certificados/${id}/desativar`)
    await carregar()
  }

  const cert = status?.certificado

  return (
    <section className="mb-8">
      <h2 className="mb-3 text-lg font-semibold text-slate-800">Certificado digital A1 · SEFAZ</h2>
      {msg && <Mensagem {...msg} />}
      {status && !status.criptografia_configurada && (
        <Mensagem tipo="erro" texto="CERT_ENCRYPTION_KEY não configurada no servidor — não é possível cadastrar certificado." />
      )}

      <div className="mb-4 rounded-lg bg-white p-4 shadow">
        {cert ? (
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="text-sm">
              <div className="font-medium text-slate-800">{cert.razao_social}</div>
              <div className="text-slate-500">CNPJ {cert.cnpj}</div>
              <div className={status?.vencendo_em_breve ? 'font-medium text-amber-700' : 'text-slate-500'}>
                Válido até {new Date(cert.valido_ate).toLocaleDateString('pt-BR')} ({status?.dias_para_vencer} dias)
              </div>
              <div className="mt-2 text-xs text-slate-500">
                Ambiente: {status?.ambiente} · NSU {cert.ult_nsu}/{cert.max_nsu ?? '?'} · última sincronização{' '}
                {dataHora(cert.ult_sincronizacao)}
                {cert.ult_mensagem_sefaz && ` · ${cert.ult_mensagem_sefaz}`}
              </div>
              {cert.bloqueado_ate && new Date(cert.bloqueado_ate) > new Date() && (
                <div className="text-xs text-amber-700">SEFAZ pede espera até {dataHora(cert.bloqueado_ate)}</div>
              )}
            </div>
            <div className="flex gap-2">
              {podeEscrever && (
                <button onClick={sincronizar} className="rounded bg-brand-700 px-3 py-1.5 text-sm text-white hover:bg-brand-800">
                  Sincronizar agora
                </button>
              )}
              {podeAdministrar && (
                <button onClick={() => desativar(cert.id)} className="text-sm text-red-600 hover:underline">
                  Desativar
                </button>
              )}
            </div>
          </div>
        ) : (
          <p className="text-sm text-slate-500">Nenhum certificado A1 ativo.</p>
        )}
      </div>

      {podeAdministrar && (
        <form onSubmit={enviar} className="mb-4 flex flex-wrap items-end gap-3 rounded-lg bg-white p-4 shadow">
          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700">Arquivo .pfx / .p12</label>
            <input
              type="file"
              accept=".pfx,.p12"
              required
              onChange={(e) => setArquivo(e.target.files?.[0] ?? null)}
              className="text-sm"
            />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700">Senha do certificado</label>
            <input
              type="password"
              required
              autoComplete="off"
              value={senha}
              onChange={(e) => setSenha(e.target.value)}
              className="rounded border border-slate-300 px-3 py-2 text-sm"
            />
          </div>
          <button
            type="submit"
            disabled={!status?.criptografia_configurada}
            className="rounded bg-brand-700 px-4 py-2 text-sm text-white hover:bg-brand-800 disabled:opacity-50"
          >
            {cert ? 'Substituir certificado' : 'Cadastrar certificado'}
          </button>
        </form>
      )}

      <div className="overflow-hidden rounded-xl bg-white shadow-sm ring-1 ring-slate-200/70">
        <div className="border-b border-slate-100 px-4 py-2 text-sm font-medium text-slate-700">
          NFes emitidas contra o CNPJ (SEFAZ)
        </div>
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
            <tr>
              <th className="px-4 py-2">Emissão</th>
              <th className="px-4 py-2">Emitente</th>
              <th className="px-4 py-2">Valor</th>
              <th className="px-4 py-2">Documento</th>
              <th className="px-4 py-2">Nota cadastrada</th>
            </tr>
          </thead>
          <tbody>
            {nfes.length === 0 && (
              <tr>
                <td className="px-4 py-3 text-slate-400" colSpan={5}>
                  Nenhuma NFe recebida ainda
                </td>
              </tr>
            )}
            {nfes.map((n) => (
              <tr key={n.id} className="border-t border-slate-100">
                <td className="px-4 py-2">{n.data_emissao ? new Date(n.data_emissao + 'T00:00').toLocaleDateString('pt-BR') : '—'}</td>
                <td className="px-4 py-2" title={n.chave_acesso}>
                  {n.nome_emitente ?? n.cnpj_emitente ?? '—'}
                </td>
                <td className="px-4 py-2">{n.valor_total ? formatarMoeda(n.valor_total) : '—'}</td>
                <td className="px-4 py-2">{n.tipo_documento === 'completo' ? 'XML completo' : 'Resumo'}</td>
                <td className="px-4 py-2">{n.nota_cadastrada ? 'Sim' : 'Não'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="mt-2 text-xs text-slate-500">
        Sem Manifestação do Destinatário a SEFAZ entrega só o resumo das NFes de terceiros; o XML completo vem quando
        a manifestação estiver ativa.
      </p>
    </section>
  )
}

function SecaoOpenFinance({ podeEscrever }: { podeEscrever: boolean }) {
  const [status, setStatus] = useState<OpenFinanceStatus | null>(null)
  const [contasBanco, setContasBanco] = useState<ContaBancaria[]>([])
  const [remotas, setRemotas] = useState<Record<string, ContaRemota[]>>({})
  const [escolha, setEscolha] = useState<Record<string, { contaBancariaId: string; remotaId: string }>>({})
  const [msg, setMsg] = useState<{ tipo: 'erro' | 'ok'; texto: string } | null>(null)

  const carregar = useCallback(async () => {
    const [st, cb] = await Promise.all([
      api.get<OpenFinanceStatus>('/open-finance/status'),
      api.get<ContaBancaria[]>('/contas-bancarias'),
    ])
    setStatus(st.data)
    setContasBanco(cb.data)
  }, [])

  useEffect(() => {
    carregar()
  }, [carregar])

  async function conectarBanco() {
    setMsg(null)
    try {
      const { data } = await api.post<{ access_token: string }>('/open-finance/connect-token')
      await carregarScriptPluggy()
      if (!window.PluggyConnect) throw new Error('Pluggy Connect indisponível')
      new window.PluggyConnect({
        connectToken: data.access_token,
        onSuccess: async ({ item }) => {
          try {
            await api.post('/open-finance/conexoes', { item_id: item.id })
            setMsg({ tipo: 'ok', texto: 'Banco conectado. Agora vincule uma conta abaixo.' })
            await carregar()
          } catch (err) {
            setMsg({ tipo: 'erro', texto: extractApiError(err, 'Não foi possível registrar a conexão') })
          }
        },
        onError: () => setMsg({ tipo: 'erro', texto: 'A conexão com o banco não foi concluída' }),
      }).init()
    } catch (err) {
      setMsg({ tipo: 'erro', texto: extractApiError(err, 'Não foi possível abrir o Pluggy Connect') })
    }
  }

  async function carregarRemotas(conexaoId: string) {
    try {
      const { data } = await api.get<ContaRemota[]>(`/open-finance/conexoes/${conexaoId}/contas`)
      setRemotas((r) => ({ ...r, [conexaoId]: data }))
    } catch (err) {
      setMsg({ tipo: 'erro', texto: extractApiError(err, 'Não foi possível listar as contas do banco') })
    }
  }

  async function vincular(conexaoId: string) {
    const e = escolha[conexaoId]
    if (!e?.contaBancariaId || !e?.remotaId) return
    try {
      await api.post(`/open-finance/contas-bancarias/${e.contaBancariaId}/vincular`, {
        conexao_id: conexaoId,
        open_finance_conta_id: e.remotaId,
      })
      setMsg({ tipo: 'ok', texto: 'Conta vinculada' })
      await carregar()
    } catch (err) {
      setMsg({ tipo: 'erro', texto: extractApiError(err, 'Não foi possível vincular') })
    }
  }

  async function sincronizar(contaId: string) {
    try {
      await api.post(`/open-finance/contas-bancarias/${contaId}/sincronizar`)
      setMsg({ tipo: 'ok', texto: 'Sincronização enfileirada — os lançamentos aparecem em Extrato / Conciliação' })
    } catch (err) {
      setMsg({ tipo: 'erro', texto: extractApiError(err, 'Não foi possível sincronizar') })
    }
  }

  async function desvincular(contaId: string) {
    await api.delete(`/open-finance/contas-bancarias/${contaId}/vincular`)
    await carregar()
  }

  return (
    <section>
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-lg font-semibold text-slate-800">Open Finance (Pluggy)</h2>
        {podeEscrever && status?.configurado && (
          <button onClick={conectarBanco} className="rounded bg-brand-700 px-3 py-1.5 text-sm text-white hover:bg-brand-800">
            Conectar banco
          </button>
        )}
      </div>
      {msg && <Mensagem {...msg} />}
      {status && !status.configurado && (
        <Mensagem tipo="erro" texto="PLUGGY_CLIENT_ID/PLUGGY_CLIENT_SECRET não configurados no servidor." />
      )}

      {status?.conexoes.map((c) => (
        <div key={c.id} className="mb-3 rounded-lg bg-white p-4 shadow">
          <div className="flex items-center justify-between">
            <div className="text-sm">
              <span className="font-medium text-slate-800">{c.conector_nome ?? 'Banco'}</span>
              <span className="ml-2 text-xs text-slate-500">{c.status}</span>
            </div>
            {podeEscrever && (
              <button onClick={() => carregarRemotas(c.id)} className="text-sm text-brand-700 hover:underline">
                Listar contas do banco
              </button>
            )}
          </div>
          {remotas[c.id] && podeEscrever && (
            <div className="mt-3 flex flex-wrap items-end gap-3">
              <select
                className="rounded border border-slate-300 px-2 py-2 text-sm"
                value={escolha[c.id]?.remotaId ?? ''}
                onChange={(e) =>
                  setEscolha((s) => ({ ...s, [c.id]: { contaBancariaId: s[c.id]?.contaBancariaId ?? '', remotaId: e.target.value } }))
                }
              >
                <option value="">Conta no banco…</option>
                {remotas[c.id].map((r) => (
                  <option key={r.id} value={r.id}>
                    {r.nome ?? r.subtipo} {r.numero ?? ''} {r.saldo ? `· ${formatarMoeda(r.saldo)}` : ''}
                  </option>
                ))}
              </select>
              <select
                className="rounded border border-slate-300 px-2 py-2 text-sm"
                value={escolha[c.id]?.contaBancariaId ?? ''}
                onChange={(e) =>
                  setEscolha((s) => ({ ...s, [c.id]: { remotaId: s[c.id]?.remotaId ?? '', contaBancariaId: e.target.value } }))
                }
              >
                <option value="">Vincular à conta bancária…</option>
                {contasBanco.map((cb) => (
                  <option key={cb.id} value={cb.id}>
                    {cb.apelido}
                  </option>
                ))}
              </select>
              <button onClick={() => vincular(c.id)} className="rounded bg-brand-700 px-3 py-2 text-sm text-white hover:bg-brand-800">
                Vincular
              </button>
            </div>
          )}
        </div>
      ))}

      <div className="overflow-hidden rounded-xl bg-white shadow-sm ring-1 ring-slate-200/70">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
            <tr>
              <th className="px-4 py-2">Conta bancária</th>
              <th className="px-4 py-2">Última sincronização</th>
              <th className="px-4 py-2" />
            </tr>
          </thead>
          <tbody>
            {status?.contas_vinculadas.length === 0 && (
              <tr>
                <td className="px-4 py-3 text-slate-400" colSpan={3}>
                  Nenhuma conta vinculada ao Open Finance
                </td>
              </tr>
            )}
            {status?.contas_vinculadas.map((c) => (
              <tr key={c.id} className="border-t border-slate-100">
                <td className="px-4 py-2">{c.apelido}</td>
                <td className="px-4 py-2">{dataHora(c.open_finance_sincronizado_em)}</td>
                <td className="space-x-3 px-4 py-2 text-right">
                  {podeEscrever && (
                    <>
                      <button onClick={() => sincronizar(c.id)} className="text-brand-700 hover:underline">
                        Sincronizar
                      </button>
                      <button onClick={() => desvincular(c.id)} className="text-red-600 hover:underline">
                        Desvincular
                      </button>
                    </>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="mt-2 text-xs text-slate-500">
        Sincronização automática a cada 4h (requer o processo Celery beat). Lançamentos entram no mesmo fluxo do
        extrato OFX/CSV e são conciliados automaticamente.
      </p>
    </section>
  )
}

export function IntegracoesPage() {
  const { usuario } = useAuth()
  const papel = usuario?.papel ?? 'sub'
  return (
    <div>
      <SecaoCertificado podeAdministrar={['admin', 'master'].includes(papel)} podeEscrever={['financeiro', 'admin', 'master'].includes(papel)} />
      <SecaoOpenFinance podeEscrever={['financeiro', 'admin', 'master'].includes(papel)} />
    </div>
  )
}
