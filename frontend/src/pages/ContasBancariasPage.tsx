import { useEffect, useState, type FormEvent } from 'react'
import { api } from '../lib/api'
import type { ContaBancaria } from '../types'

export function ContasBancariasPage() {
  const [contas, setContas] = useState<ContaBancaria[]>([])
  const [carregando, setCarregando] = useState(true)
  const [mostrarForm, setMostrarForm] = useState(false)
  const [apelido, setApelido] = useState('')
  const [banco, setBanco] = useState('')
  const [agencia, setAgencia] = useState('')
  const [numeroConta, setNumeroConta] = useState('')
  const [saldoInicial, setSaldoInicial] = useState('0')
  const [erro, setErro] = useState<string | null>(null)

  async function carregar() {
    setCarregando(true)
    const { data } = await api.get<ContaBancaria[]>('/contas-bancarias')
    setContas(data)
    setCarregando(false)
  }

  useEffect(() => {
    carregar()
  }, [])

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setErro(null)
    try {
      await api.post('/contas-bancarias', {
        apelido,
        banco: banco || null,
        agencia: agencia || null,
        numero_conta: numeroConta || null,
        saldo_inicial: saldoInicial,
      })
      setApelido('')
      setBanco('')
      setAgencia('')
      setNumeroConta('')
      setSaldoInicial('0')
      setMostrarForm(false)
      await carregar()
    } catch {
      setErro('Não foi possível salvar a conta bancária')
    }
  }

  async function desativar(id: string) {
    await api.delete(`/contas-bancarias/${id}`)
    await carregar()
  }

  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-lg font-semibold text-slate-800">Contas Bancárias</h2>
        <button
          onClick={() => setMostrarForm((v) => !v)}
          className="rounded bg-brand-700 px-3 py-1.5 text-sm text-white hover:bg-brand-800"
        >
          {mostrarForm ? 'Cancelar' : 'Nova conta bancária'}
        </button>
      </div>

      {mostrarForm && (
        <form onSubmit={handleSubmit} className="mb-6 rounded-lg bg-white p-4 shadow">
          {erro && <div className="mb-3 rounded bg-red-50 px-3 py-2 text-sm text-red-700">{erro}</div>}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="mb-1 block text-sm font-medium text-slate-700">Apelido *</label>
              <input
                required
                value={apelido}
                onChange={(e) => setApelido(e.target.value)}
                placeholder="ex: Itaú CC Principal"
                className="w-full rounded border border-slate-300 px-3 py-2 text-sm"
              />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-slate-700">Banco</label>
              <input
                value={banco}
                onChange={(e) => setBanco(e.target.value)}
                className="w-full rounded border border-slate-300 px-3 py-2 text-sm"
              />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-slate-700">Agência</label>
              <input
                value={agencia}
                onChange={(e) => setAgencia(e.target.value)}
                className="w-full rounded border border-slate-300 px-3 py-2 text-sm"
              />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-slate-700">Número da conta</label>
              <input
                value={numeroConta}
                onChange={(e) => setNumeroConta(e.target.value)}
                className="w-full rounded border border-slate-300 px-3 py-2 text-sm"
              />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-slate-700">Saldo inicial</label>
              <input
                type="number"
                step="0.01"
                value={saldoInicial}
                onChange={(e) => setSaldoInicial(e.target.value)}
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
              <th className="px-4 py-2">Apelido</th>
              <th className="px-4 py-2">Banco</th>
              <th className="px-4 py-2">Agência</th>
              <th className="px-4 py-2">Conta</th>
              <th className="px-4 py-2">Saldo inicial</th>
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
            {!carregando && contas.length === 0 && (
              <tr>
                <td className="px-4 py-3 text-slate-400" colSpan={6}>
                  Nenhuma conta bancária cadastrada
                </td>
              </tr>
            )}
            {contas.map((c) => (
              <tr key={c.id} className="border-t border-slate-100">
                <td className="px-4 py-2">{c.apelido}</td>
                <td className="px-4 py-2">{c.banco ?? '—'}</td>
                <td className="px-4 py-2">{c.agencia ?? '—'}</td>
                <td className="px-4 py-2">{c.numero_conta ?? '—'}</td>
                <td className="px-4 py-2">
                  {Number(c.saldo_inicial).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })}
                </td>
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
