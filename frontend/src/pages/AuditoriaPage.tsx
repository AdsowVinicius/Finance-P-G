import { Fragment, useEffect, useState } from 'react'
import { api } from '../lib/api'
import type { LogAuditoria, Usuario } from '../types'

const entidadeLabel: Record<string, string> = {
  parceiros: 'Parceiro',
  centros_custo: 'Centro de custo',
  contas_bancarias: 'Conta bancária',
  contas_financeiras: 'Conta financeira',
  lancamentos_recorrentes: 'Lançamento recorrente',
  notas_fiscais: 'Nota fiscal',
  usuarios: 'Usuário',
  pre_lancamentos_whatsapp: 'Pré-lançamento WhatsApp',
  lancamentos_extrato: 'Lançamento de extrato',
  extratos_importados: 'Extrato importado',
}

const acaoLabel: Record<string, string> = {
  criacao: 'Criação',
  edicao: 'Edição',
  exclusao: 'Exclusão',
}

const acaoCor: Record<string, string> = {
  criacao: 'bg-emerald-100 text-emerald-800',
  edicao: 'bg-amber-100 text-amber-800',
  exclusao: 'bg-red-100 text-red-800',
}

function formatarDataHora(iso: string): string {
  return new Date(iso).toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'medium' })
}

function formatarValor(v: unknown): string {
  if (v === null || v === undefined) return '—'
  if (typeof v === 'boolean') return v ? 'sim' : 'não'
  return String(v)
}

function Diferencas({ antes, depois }: { antes: Record<string, unknown> | null; depois: Record<string, unknown> | null }) {
  if (antes && depois) {
    const campos = Object.keys(depois).filter((campo) => JSON.stringify(antes[campo]) !== JSON.stringify(depois[campo]))
    if (campos.length === 0) return <p className="text-xs text-slate-400">Nenhum campo mudou.</p>
    return (
      <table className="text-xs">
        <thead className="text-left text-slate-500">
          <tr>
            <th className="pr-4 py-1">Campo</th>
            <th className="pr-4 py-1">Antes</th>
            <th className="py-1">Depois</th>
          </tr>
        </thead>
        <tbody>
          {campos.map((campo) => (
            <tr key={campo} className="border-t border-slate-100">
              <td className="pr-4 py-1 font-medium text-slate-700">{campo}</td>
              <td className="pr-4 py-1 text-red-700">{formatarValor(antes[campo])}</td>
              <td className="py-1 text-emerald-700">{formatarValor(depois[campo])}</td>
            </tr>
          ))}
        </tbody>
      </table>
    )
  }

  const dados = depois ?? antes
  if (!dados) return null
  return (
    <table className="text-xs">
      <tbody>
        {Object.entries(dados).map(([campo, valor]) => (
          <tr key={campo} className="border-t border-slate-100">
            <td className="pr-4 py-1 font-medium text-slate-700">{campo}</td>
            <td className="py-1 text-slate-600">{formatarValor(valor)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

export function AuditoriaPage() {
  const [logs, setLogs] = useState<LogAuditoria[]>([])
  const [usuarios, setUsuarios] = useState<Usuario[]>([])
  const [carregando, setCarregando] = useState(true)
  const [expandido, setExpandido] = useState<string | null>(null)
  const [filtroEntidade, setFiltroEntidade] = useState('')

  async function carregar(entidade: string) {
    setCarregando(true)
    const [logsRes, usuariosRes] = await Promise.all([
      api.get<LogAuditoria[]>('/auditoria', { params: entidade ? { entidade } : {} }),
      api.get<Usuario[]>('/usuarios'),
    ])
    setLogs(logsRes.data)
    setUsuarios(usuariosRes.data)
    setCarregando(false)
  }

  useEffect(() => {
    carregar('')
  }, [])

  function nomeUsuario(id: string): string {
    return usuarios.find((u) => u.id === id)?.nome ?? '—'
  }

  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-slate-800">Auditoria</h2>
          <p className="text-sm text-slate-500">
            Toda criação, edição e exclusão feita na aplicação — quem, quando, e o que mudou.
          </p>
        </div>
        <select
          value={filtroEntidade}
          onChange={(e) => {
            setFiltroEntidade(e.target.value)
            carregar(e.target.value)
          }}
          className="rounded border border-slate-300 px-3 py-1.5 text-sm"
        >
          <option value="">Todas as entidades</option>
          {Object.entries(entidadeLabel).map(([valor, label]) => (
            <option key={valor} value={valor}>
              {label}
            </option>
          ))}
        </select>
      </div>

      <div className="overflow-hidden rounded-xl bg-white shadow-sm ring-1 ring-slate-200/70">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
            <tr>
              <th className="px-4 py-2">Quando</th>
              <th className="px-4 py-2">Usuário</th>
              <th className="px-4 py-2">Ação</th>
              <th className="px-4 py-2">Entidade</th>
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
            {!carregando && logs.length === 0 && (
              <tr>
                <td className="px-4 py-3 text-slate-400" colSpan={5}>
                  Nada registrado ainda.
                </td>
              </tr>
            )}
            {logs.map((log) => (
              <Fragment key={log.id}>
                <tr className="border-t border-slate-100">
                  <td className="px-4 py-2 text-slate-500">{formatarDataHora(log.created_at)}</td>
                  <td className="px-4 py-2">{nomeUsuario(log.usuario_id)}</td>
                  <td className="px-4 py-2">
                    <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${acaoCor[log.acao] ?? 'bg-slate-100 text-slate-700'}`}>
                      {acaoLabel[log.acao] ?? log.acao}
                    </span>
                  </td>
                  <td className="px-4 py-2">{entidadeLabel[log.entidade] ?? log.entidade}</td>
                  <td className="px-4 py-2 text-right">
                    <button
                      onClick={() => setExpandido(expandido === log.id ? null : log.id)}
                      className="text-brand-700 hover:underline"
                    >
                      {expandido === log.id ? 'ocultar' : 'ver detalhes'}
                    </button>
                  </td>
                </tr>
                {expandido === log.id && (
                  <tr className="border-t border-slate-100 bg-slate-50">
                    <td colSpan={5} className="px-4 py-3">
                      <Diferencas antes={log.dados_antes as Record<string, unknown> | null} depois={log.dados_depois as Record<string, unknown> | null} />
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
