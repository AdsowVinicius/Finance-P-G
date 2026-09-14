import { NavLink, Outlet } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'

const links = [
  { to: '/', label: 'Dashboard' },
  { to: '/notas-fiscais', label: 'Notas Fiscais' },
  { to: '/extratos', label: 'Extrato / Conciliação' },
  { to: '/lancamentos-recorrentes', label: 'Recorrências' },
  { to: '/parceiros', label: 'Parceiros' },
  { to: '/centros-custo', label: 'Centros de Custo' },
  { to: '/contas-bancarias', label: 'Contas Bancárias' },
]

export function Layout() {
  const { usuario, logout } = useAuth()

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="bg-slate-900 text-white">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-y-2 px-4 py-3">
          <div className="flex flex-wrap items-center gap-x-6 gap-y-2">
            <span className="font-semibold">Finance P&amp;G</span>
            <nav className="flex flex-wrap gap-x-4 gap-y-1 text-sm">
              {links.map((link) => (
                <NavLink
                  key={link.to}
                  to={link.to}
                  end={link.to === '/'}
                  className={({ isActive }) =>
                    isActive ? 'text-white font-medium' : 'text-slate-300 hover:text-white'
                  }
                >
                  {link.label}
                </NavLink>
              ))}
            </nav>
          </div>
          <div className="flex items-center gap-3 text-sm">
            <span className="text-slate-300">
              {usuario?.nome} <span className="text-slate-500">({usuario?.papel})</span>
            </span>
            <button
              onClick={logout}
              className="rounded bg-slate-700 px-3 py-1 hover:bg-slate-600"
            >
              Sair
            </button>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-4 py-6">
        <Outlet />
      </main>
    </div>
  )
}
