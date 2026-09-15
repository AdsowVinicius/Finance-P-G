import { Building2, Lock, Mail } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import logoPg from '../assets/logo-pg.webp'
import { useAuth } from '../contexts/AuthContext'

export function LoginPage() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [senha, setSenha] = useState('')
  const [erro, setErro] = useState<string | null>(null)
  const [carregando, setCarregando] = useState(false)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setErro(null)
    setCarregando(true)
    try {
      await login(email, senha)
      navigate('/')
    } catch {
      setErro('Email ou senha inválidos')
    } finally {
      setCarregando(false)
    }
  }

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-brand-950">
      {/* decoração de fundo — "skyline" sutil remetendo à logo */}
      <div className="pointer-events-none absolute inset-0 opacity-[0.07]">
        <svg viewBox="0 0 800 400" className="h-full w-full" preserveAspectRatio="xMidYMax slice">
          <rect x="40" y="180" width="60" height="220" fill="white" />
          <rect x="120" y="120" width="60" height="280" fill="white" />
          <rect x="200" y="200" width="60" height="200" fill="white" />
          <rect x="620" y="150" width="60" height="250" fill="white" />
          <rect x="700" y="90" width="60" height="310" fill="white" />
        </svg>
      </div>
      <div className="absolute inset-x-0 top-0 h-1.5 bg-gradient-to-r from-brand-500 via-brand-300 to-brand-500" />

      <div className="relative z-10 w-full max-w-sm px-4">
        <div className="mb-6 flex justify-center">
          <div className="rounded-2xl bg-white/95 px-6 py-4 shadow-lg">
            <img src={logoPg} alt="P&G Engenharia" className="h-14 w-auto" />
          </div>
        </div>

        <form onSubmit={handleSubmit} className="rounded-2xl bg-white p-8 shadow-2xl">
          <h1 className="mb-1 text-xl font-bold text-brand-900">Finance P&amp;G</h1>
          <p className="mb-6 text-sm text-slate-500">Gestão financeira interna — entre com sua conta</p>

          {erro && (
            <div className="mb-4 rounded-lg bg-red-50 px-3 py-2.5 text-sm text-red-700">{erro}</div>
          )}

          <label className="mb-1 block text-sm font-medium text-slate-700">Email</label>
          <div className="relative mb-4">
            <Mail size={16} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full rounded-lg border border-slate-300 py-2.5 pl-9 pr-3 text-sm focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-100"
            />
          </div>

          <label className="mb-1 block text-sm font-medium text-slate-700">Senha</label>
          <div className="relative mb-6">
            <Lock size={16} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <input
              type="password"
              required
              value={senha}
              onChange={(e) => setSenha(e.target.value)}
              className="w-full rounded-lg border border-slate-300 py-2.5 pl-9 pr-3 text-sm focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-100"
            />
          </div>

          <button
            type="submit"
            disabled={carregando}
            className="flex w-full items-center justify-center gap-2 rounded-lg bg-brand-700 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-brand-800 disabled:opacity-50"
          >
            <Building2 size={16} />
            {carregando ? 'Entrando...' : 'Entrar'}
          </button>
        </form>

        <p className="mt-6 text-center text-xs text-brand-300">P&amp;G Engenharia — uso interno</p>
      </div>
    </div>
  )
}
