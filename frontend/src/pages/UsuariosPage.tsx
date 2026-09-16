import { Fragment, useEffect, useState, type FormEvent } from 'react'
import { api } from '../lib/api'
import { extractApiError } from '../lib/apiError'
import type { PapelUsuario, Usuario } from '../types'

const papeis: PapelUsuario[] = ['sub', 'financeiro', 'admin', 'master']

const papelLabel: Record<PapelUsuario, string> = {
  financeiro: 'Financeiro',
  admin: 'Administrador',
  master: 'Master',
  sub: 'Sub',
}

function EditarUsuarioForm({ usuario, onSalvo, onCancelar }: { usuario: Usuario; onSalvo: () => void; onCancelar: () => void }) {
  const [papel, setPapel] = useState(usuario.papel)
  const [novaSenha, setNovaSenha] = useState('')
  const [salvando, setSalvando] = useState(false)
  const [erro, setErro] = useState<string | null>(null)

  async function salvar() {
    setErro(null)
    setSalvando(true)
    try {
      await api.patch(`/usuarios/${usuario.id}`, {
        papel,
        ...(novaSenha ? { senha: novaSenha } : {}),
      })
      onSalvo()
    } catch (err) {
      setErro(extractApiError(err, 'Não foi possível salvar'))
    } finally {
      setSalvando(false)
    }
  }

  return (
    <div className="mt-2 flex flex-wrap items-end gap-2 rounded bg-slate-50 p-3">
      <div>
        <label className="mb-1 block text-xs font-medium text-slate-600">Papel</label>
        <select
          value={papel}
          onChange={(e) => setPapel(e.target.value as PapelUsuario)}
          className="rounded border border-slate-300 px-2 py-1 text-sm"
        >
          {papeis.map((p) => (
            <option key={p} value={p}>
              {papelLabel[p]}
            </option>
          ))}
        </select>
      </div>
      <div>
        <label className="mb-1 block text-xs font-medium text-slate-600">Nova senha (opcional)</label>
        <input
          type="password"
          value={novaSenha}
          onChange={(e) => setNovaSenha(e.target.value)}
          placeholder="deixe em branco pra não trocar"
          className="w-56 rounded border border-slate-300 px-2 py-1 text-sm"
        />
      </div>
      <button
        onClick={salvar}
        disabled={salvando}
        className="rounded bg-emerald-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-emerald-700 disabled:opacity-50"
      >
        Salvar
      </button>
      <button onClick={onCancelar} className="rounded px-3 py-1.5 text-xs text-slate-500 hover:bg-slate-200">
        Cancelar
      </button>
      {erro && <p className="w-full text-xs text-red-600">{erro}</p>}
    </div>
  )
}

export function UsuariosPage() {
  const [usuarios, setUsuarios] = useState<Usuario[]>([])
  const [carregando, setCarregando] = useState(true)
  const [mostrarForm, setMostrarForm] = useState(false)
  const [editandoId, setEditandoId] = useState<string | null>(null)

  const [nome, setNome] = useState('')
  const [email, setEmail] = useState('')
  const [senha, setSenha] = useState('')
  const [papel, setPapel] = useState<PapelUsuario>('sub')
  const [erro, setErro] = useState<string | null>(null)

  async function carregar() {
    setCarregando(true)
    const { data } = await api.get<Usuario[]>('/usuarios')
    setUsuarios(data)
    setCarregando(false)
  }

  useEffect(() => {
    carregar()
  }, [])

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setErro(null)
    try {
      await api.post('/usuarios', { nome, email, senha, papel })
      setNome('')
      setEmail('')
      setSenha('')
      setPapel('sub')
      setMostrarForm(false)
      await carregar()
    } catch (err) {
      setErro(extractApiError(err, 'Não foi possível criar o usuário'))
    }
  }

  async function alternarAtivo(usuario: Usuario) {
    await api.patch(`/usuarios/${usuario.id}`, { ativo: !usuario.ativo })
    await carregar()
  }

  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-lg font-semibold text-slate-800">Usuários</h2>
        <button
          onClick={() => setMostrarForm((v) => !v)}
          className="rounded bg-brand-700 px-3 py-1.5 text-sm text-white hover:bg-brand-800"
        >
          {mostrarForm ? 'Cancelar' : 'Novo usuário'}
        </button>
      </div>

      {mostrarForm && (
        <form onSubmit={handleSubmit} className="mb-6 rounded-lg bg-white p-4 shadow">
          {erro && <div className="mb-3 rounded bg-red-50 px-3 py-2 text-sm text-red-700">{erro}</div>}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="mb-1 block text-sm font-medium text-slate-700">Nome *</label>
              <input
                required
                value={nome}
                onChange={(e) => setNome(e.target.value)}
                className="w-full rounded border border-slate-300 px-3 py-2 text-sm"
              />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-slate-700">Email *</label>
              <input
                required
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full rounded border border-slate-300 px-3 py-2 text-sm"
              />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-slate-700">Senha *</label>
              <input
                required
                type="password"
                minLength={8}
                value={senha}
                onChange={(e) => setSenha(e.target.value)}
                className="w-full rounded border border-slate-300 px-3 py-2 text-sm"
              />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-slate-700">Papel</label>
              <select
                value={papel}
                onChange={(e) => setPapel(e.target.value as PapelUsuario)}
                className="w-full rounded border border-slate-300 px-3 py-2 text-sm"
              >
                {papeis.map((p) => (
                  <option key={p} value={p}>
                    {papelLabel[p]}
                  </option>
                ))}
              </select>
            </div>
          </div>
          <button
            type="submit"
            className="mt-4 rounded bg-brand-700 px-4 py-2 text-sm text-white hover:bg-brand-800"
          >
            Salvar
          </button>
        </form>
      )}

      <div className="overflow-hidden rounded-xl bg-white shadow-sm ring-1 ring-slate-200/70">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
            <tr>
              <th className="px-4 py-2">Nome</th>
              <th className="px-4 py-2">Email</th>
              <th className="px-4 py-2">Papel</th>
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
            {!carregando && usuarios.length === 0 && (
              <tr>
                <td className="px-4 py-3 text-slate-400" colSpan={5}>
                  Nenhum usuário cadastrado
                </td>
              </tr>
            )}
            {usuarios.map((u) => (
              <Fragment key={u.id}>
                <tr className="border-t border-slate-100">
                  <td className="px-4 py-2">{u.nome}</td>
                  <td className="px-4 py-2 text-slate-500">{u.email}</td>
                  <td className="px-4 py-2">{papelLabel[u.papel]}</td>
                  <td className="px-4 py-2">
                    <span
                      className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                        u.ativo ? 'bg-emerald-100 text-emerald-800' : 'bg-slate-100 text-slate-500'
                      }`}
                    >
                      {u.ativo ? 'Ativo' : 'Inativo'}
                    </span>
                  </td>
                  <td className="px-4 py-2 text-right">
                    <div className="flex justify-end gap-3">
                      <button
                        onClick={() => setEditandoId(editandoId === u.id ? null : u.id)}
                        className="text-brand-700 hover:underline"
                      >
                        Editar
                      </button>
                      <button onClick={() => alternarAtivo(u)} className="text-slate-500 hover:underline">
                        {u.ativo ? 'Desativar' : 'Ativar'}
                      </button>
                    </div>
                  </td>
                </tr>
                {editandoId === u.id && (
                  <tr className="border-t border-slate-100">
                    <td colSpan={5} className="px-4 pb-3">
                      <EditarUsuarioForm
                        usuario={u}
                        onSalvo={() => {
                          setEditandoId(null)
                          carregar()
                        }}
                        onCancelar={() => setEditandoId(null)}
                      />
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
