import { useEffect, useState, type FormEvent } from 'react'
import { api } from '../lib/api'
import type { CentroCusto } from '../types'

export function CentrosCustoPage() {
  const [centros, setCentros] = useState<CentroCusto[]>([])
  const [carregando, setCarregando] = useState(true)
  const [mostrarForm, setMostrarForm] = useState(false)
  const [nome, setNome] = useState('')
  const [codigo, setCodigo] = useState('')
  const [erro, setErro] = useState<string | null>(null)

  async function carregar() {
    setCarregando(true)
    const { data } = await api.get<CentroCusto[]>('/centros-custo')
    setCentros(data)
    setCarregando(false)
  }

  useEffect(() => {
    carregar()
  }, [])

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setErro(null)
    try {
      await api.post('/centros-custo', { nome, codigo: codigo || null })
      setNome('')
      setCodigo('')
      setMostrarForm(false)
      await carregar()
    } catch {
      setErro('Não foi possível salvar o centro de custo')
    }
  }

  async function desativar(id: string) {
    await api.delete(`/centros-custo/${id}`)
    await carregar()
  }

  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-lg font-semibold text-slate-800">Centros de Custo</h2>
        <button
          onClick={() => setMostrarForm((v) => !v)}
          className="rounded bg-brand-700 px-3 py-1.5 text-sm text-white hover:bg-brand-800"
        >
          {mostrarForm ? 'Cancelar' : 'Novo centro de custo'}
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
              <label className="mb-1 block text-sm font-medium text-slate-700">Código</label>
              <input
                value={codigo}
                onChange={(e) => setCodigo(e.target.value)}
                className="w-full rounded border border-slate-300 px-3 py-2 text-sm"
              />
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
              <th className="px-4 py-2">Código</th>
              <th className="px-4 py-2">Nome</th>
              <th className="px-4 py-2" />
            </tr>
          </thead>
          <tbody>
            {carregando && (
              <tr>
                <td className="px-4 py-3 text-slate-400" colSpan={3}>
                  Carregando...
                </td>
              </tr>
            )}
            {!carregando && centros.length === 0 && (
              <tr>
                <td className="px-4 py-3 text-slate-400" colSpan={3}>
                  Nenhum centro de custo cadastrado
                </td>
              </tr>
            )}
            {centros.map((c) => (
              <tr key={c.id} className="border-t border-slate-100">
                <td className="px-4 py-2">{c.codigo ?? '—'}</td>
                <td className="px-4 py-2">{c.nome}</td>
                <td className="px-4 py-2 text-right">
                  <button onClick={() => desativar(c.id)} className="text-red-600 hover:underline">
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
