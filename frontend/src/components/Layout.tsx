import {
  ArrowLeftRight,
  BarChart3,
  Bot,
  Building2,
  FileText,
  LayoutDashboard,
  LogOut,
  MessageCircle,
  Repeat,
  Tag,
  UserCog,
  Users,
} from 'lucide-react'
import { NavLink, Outlet } from 'react-router-dom'
import logoPg from '../assets/logo-pg.webp'
import { useAuth } from '../contexts/AuthContext'

const links = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/indicadores', label: 'Indicadores', icon: BarChart3 },
  { to: '/assistente', label: 'Assistente', icon: Bot },
  { to: '/whatsapp', label: 'WhatsApp', icon: MessageCircle },
  { to: '/notas-fiscais', label: 'Notas Fiscais', icon: FileText },
  { to: '/extratos', label: 'Extrato / Conciliação', icon: ArrowLeftRight },
  { to: '/lancamentos-recorrentes', label: 'Recorrências', icon: Repeat },
  { to: '/parceiros', label: 'Parceiros', icon: Users },
  { to: '/centros-custo', label: 'Centros de Custo', icon: Tag },
  { to: '/contas-bancarias', label: 'Contas Bancárias', icon: Building2 },
]

const linksAdmin = [{ to: '/usuarios', label: 'Usuários', icon: UserCog }]

const papelLabel: Record<string, string> = {
  financeiro: 'Financeiro',
  admin: 'Administrador',
  master: 'Master',
  sub: 'Sub',
}

export function Layout() {
  const { usuario, logout } = useAuth()

  return (
    <div className="flex min-h-screen bg-slate-50">
      <aside className="fixed inset-y-0 left-0 z-20 flex w-64 flex-col bg-brand-900">
        <div className="flex items-center gap-3 px-5 py-6">
          <img src={logoPg} alt="P&G Engenharia" className="h-10 w-auto rounded bg-white/95 p-1" />
        </div>

        <nav className="flex-1 space-y-1 px-3">
          {[...links, ...(usuario && ['admin', 'master'].includes(usuario.papel) ? linksAdmin : [])].map((link) => {
            const Icon = link.icon
            return (
              <NavLink
                key={link.to}
                to={link.to}
                end={link.to === '/'}
                className={({ isActive }) =>
                  `flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors ${
                    isActive
                      ? 'bg-brand-600 text-white shadow-sm'
                      : 'text-brand-100/80 hover:bg-brand-800 hover:text-white'
                  }`
                }
              >
                <Icon size={18} strokeWidth={2} />
                {link.label}
              </NavLink>
            )
          })}
        </nav>

        <div className="border-t border-brand-800 px-4 py-4">
          <div className="mb-3 flex items-center gap-2.5">
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-brand-600 text-sm font-semibold text-white">
              {usuario?.nome?.[0]?.toUpperCase() ?? '?'}
            </div>
            <div className="min-w-0">
              <p className="truncate text-sm font-medium text-white">{usuario?.nome}</p>
              <p className="text-xs text-brand-300">{usuario && (papelLabel[usuario.papel] ?? usuario.papel)}</p>
            </div>
          </div>
          <button
            onClick={logout}
            className="flex w-full items-center justify-center gap-2 rounded-lg bg-brand-800 px-3 py-2 text-sm font-medium text-brand-100 transition-colors hover:bg-brand-700 hover:text-white"
          >
            <LogOut size={16} />
            Sair
          </button>
        </div>
      </aside>

      <div className="flex min-h-screen flex-1 flex-col pl-64">
        <main className="mx-auto w-full max-w-6xl flex-1 px-8 py-8">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
