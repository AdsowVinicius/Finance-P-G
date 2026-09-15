import { useEffect, useState, type FormEvent } from 'react'
import { api } from '../lib/api'
import type { Parceiro, TipoParceiro } from '../types'

const tipos: TipoParceiro[] = ['fornecedor', 'cliente', 'ambos']

export function ParceirosPage() {
  const [parceiros, setParceiros] = useState<Parceiro[]>([])
  const [carregando, setCarregando] = useState(true)
  const [mostrarForm, setMostrarForm] = useState(false)
  const [razaoSocial, setRazaoSocial] = useState('')
  const [nomeFantasia, setNomeFantasia] = useState('')
  const [cnpjCpf, setCnpjCpf] = useState('')
  const [tipo, setTipo] = useState<TipoParceiro>('fornecedor')
  const [erro, setErro] = useState<string | null>(null)

  async function carregar() {
    setCarregando(true)
    const { data } = await api.get<Parceiro[]>('/parceiros')
    setParceiros(data)
    setCarregando(false)
  }

  useEffect(() => {
    carregar()
  }, [])

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setErro(null)
    try {
      await api.post('/parceiros', {
        razao_social: razaoSocial,
        nome_fantasia: nomeFantasia || null,
        cnpj_cpf: cnpjCpf || null,
        tipo,
      })
      setRazaoSocial('')
      setNomeFantasia('')
      setCnpjCpf('')
      setTipo('fornecedor')
      setMostrarForm(false)
      await carregar()
    } catch {
      setErro('Não foi possível salvar o parceiro')
    }
  }

  async function desativar(id: string) {
    await api.delete(`/parceiros/${id}`)
    await carregar()
  }

  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-lg font-semibold text-slate-800">Parceiros</h2>
        <button
          onClick={() => setMostrarForm((v) => !v)}
          className="rounded bg-brand-700 px-3 py-1.5 text-sm text-white hover:bg-brand-800"
        >
          {mostrarForm ? 'Cancelar' : 'Novo parceiro'}
        </button>
      </div>

      {mostrarForm && (
        <form onSubmit={handleSubmit} className="mb-6 rounded-lg bg-white p-4 shadow">
          {erro && <div className="mb-3 rounded bg-red-50 px-3 py-2 text-sm text-red-700">{erro}</div>}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="mb-1 block text-sm font-medium text-slate-700">Razão social *</label>
              <input
                required
                value={razaoSocial}
                onChange={(e) => setRazaoSocial(e.target.value)}
                className="w-full rounded border border-slate-300 px-3 py-2 text-sm"
              />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-slate-700">Nome fantasia</label>
              <input
                value={nomeFantasia}
                onChange={(e) => setNomeFantasia(e.target.value)}
                className="w-full rounded border border-slate-300 px-3 py-2 text-sm"
              />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-slate-700">CNPJ/CPF</label>
              <input
                value={cnpjCpf}
                onChange={(e) => setCnpjCpf(e.target.value)}
                className="w-full rounded border border-slate-300 px-3 py-2 text-sm"
              />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-slate-700">Tipo</label>
              <select
                value={tipo}
                onChange={(e) => setTipo(e.target.value as TipoParceiro)}
                className="w-full rounded border border-slate-300 px-3 py-2 text-sm"
              >
                {tipos.map((t) => (
                  <option key={t} value={t}>
                    {t}
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
              <th className="px-4 py-2">Razão social</th>
              <th className="px-4 py-2">Nome fantasia</th>
              <th className="px-4 py-2">CNPJ/CPF</th>
              <th className="px-4 py-2">Tipo</th>
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
            {!carregando && parceiros.length === 0 && (
              <tr>
                <td className="px-4 py-3 text-slate-400" colSpan={5}>
                  Nenhum parceiro cadastrado
                </td>
              </tr>
            )}
            {parceiros.map((p) => (
              <tr key={p.id} className="border-t border-slate-100">
                <td className="px-4 py-2">{p.razao_social}</td>
                <td className="px-4 py-2">{p.nome_fantasia ?? '—'}</td>
                <td className="px-4 py-2">{p.cnpj_cpf ?? '—'}</td>
                <td className="px-4 py-2 capitalize">{p.tipo}</td>
                <td className="px-4 py-2 text-right">
                  <button onClick={() => desativar(p.id)} className="text-red-600 hover:underline">
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
