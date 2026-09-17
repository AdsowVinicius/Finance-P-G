import type { ReactNode } from 'react'
import { Navigate } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import type { PapelUsuario } from '../types'

export function ProtectedRoute({ children, roles }: { children: ReactNode; roles?: PapelUsuario[] }) {
  const { usuario } = useAuth()
  if (!usuario) {
    return <Navigate to="/login" replace />
  }
  // roles: além de autenticado, restringe a rota a papéis específicos (ex:
  // /usuarios e /auditoria, admin/master only) — sem isso, o backend barra
  // a chamada de API mas a página tenta renderizar e quebra em vez de negar
  // o acesso de forma clara.
  if (roles && !roles.includes(usuario.papel)) {
    return <Navigate to="/" replace />
  }
  return <>{children}</>
}
