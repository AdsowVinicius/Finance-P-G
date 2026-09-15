import { Fragment, useEffect, useState } from 'react'
import { api } from '../lib/api'
import type { LogAuditoria, Usuario } from '../types'

const entidadeLabel: Record<string, string> = {
  lancamentos_extrato: 'Lançamento de extrato',
  extratos_importados: 'Extrato importado',
}

const acaoLabel: Record<string, string> = {
  exclusao: 'Exclusão',
}

function formatarDataHora(iso: string): string {
  return new Date(iso).toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'medium' })
}

export function AuditoriaPage() {
  const [logs, setLogs] = useState<LogAuditoria[]>([])
  const [usuarios, setUsuarios] = useState<Usuario[]>([])
  const [carregando, setCarregando] = useState(true)
  const [expandido, setExpandido] = useState<string | null>(null)

  useEffect(() => {
    Promise.all([api.get<LogAuditoria[]>('/auditoria'), api.get<Usuario[]>('/usuarios')]).then(
      ([logsRes, usuariosRes]) => {
        setLogs(logsRes.data)
        setUsuarios(usuariosRes.data)
        setCarregando(false)
      },
    )
  }, [])

  function nomeUsuario(id: string): string {
    return usuarios.find((u) => u.id === id)?.nome ?? '—'
  }

  return (
    <div>
      <div className="mb-4">
        <h2 className="text-lg font-semibold text-slate-800">Auditoria</h2>
        <p className="text-sm text-slate-500">
          Registro de ações destrutivas (exclusões definitivas) — quem, quando, e um retrato completo do que existia
          antes de ser apagado.
        </p>
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
                  Nenhuma exclusão registrada ainda.
                </td>
              </tr>
            )}
            {logs.map((log) => (
              <Fragment key={log.id}>
                <tr className="border-t border-slate-100">
                  <td className="px-4 py-2 text-slate-500">{formatarDataHora(log.created_at)}</td>
                  <td className="px-4 py-2">{nomeUsuario(log.usuario_id)}</td>
                  <td className="px-4 py-2">
                    <span className="rounded-full bg-red-100 px-2 py-0.5 text-xs font-medium text-red-800">
                      {acaoLabel[log.acao] ?? log.acao}
                    </span>
                  </td>
                  <td className="px-4 py-2">{entidadeLabel[log.entidade] ?? log.entidade}</td>
                  <td className="px-4 py-2 text-right">
                    <button
                      onClick={() => setExpandido(expandido === log.id ? null : log.id)}
                      className="text-brand-700 hover:underline"
                    >
                      {expandido === log.id ? 'ocultar' : 'ver dados'}
                    </button>
                  </td>
                </tr>
                {expandido === log.id && (
                  <tr className="border-t border-slate-100 bg-slate-50">
                    <td colSpan={5} className="px-4 py-3">
                      <pre className="overflow-x-auto whitespace-pre-wrap text-xs text-slate-700">
                        {JSON.stringify(log.dados_antes, null, 2)}
                      </pre>
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
