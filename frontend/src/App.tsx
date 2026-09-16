import { Navigate, Route, Routes } from 'react-router-dom'
import { Layout } from './components/Layout'
import { ProtectedRoute } from './components/ProtectedRoute'
import { useAuth } from './contexts/AuthContext'
import { AnaliseCentroCustoPage } from './pages/AnaliseCentroCustoPage'
import { AssistentePage } from './pages/AssistentePage'
import { AuditoriaPage } from './pages/AuditoriaPage'
import { CentrosCustoPage } from './pages/CentrosCustoPage'
import { ContasBancariasPage } from './pages/ContasBancariasPage'
import { DashboardPage } from './pages/DashboardPage'
import { ExtratosPage } from './pages/ExtratosPage'
import { IndicadoresPage } from './pages/IndicadoresPage'
import { LancamentosRecorrentesPage } from './pages/LancamentosRecorrentesPage'
import { LoginPage } from './pages/LoginPage'
import { NotasFiscaisPage } from './pages/NotasFiscaisPage'
import { ParceirosPage } from './pages/ParceirosPage'
import { PreLancamentosWhatsappPage } from './pages/PreLancamentosWhatsappPage'
import { RelatoriosPage } from './pages/RelatoriosPage'
import { UsuariosPage } from './pages/UsuariosPage'

function App() {
  const { usuario } = useAuth()

  return (
    <Routes>
      <Route path="/login" element={usuario ? <Navigate to="/" replace /> : <LoginPage />} />
      <Route
        element={
          <ProtectedRoute>
            <Layout />
          </ProtectedRoute>
        }
      >
        <Route path="/" element={<DashboardPage />} />
        <Route path="/indicadores" element={<IndicadoresPage />} />
        <Route path="/analise-centro-custo" element={<AnaliseCentroCustoPage />} />
        <Route path="/relatorios" element={<RelatoriosPage />} />
        <Route path="/assistente" element={<AssistentePage />} />
        <Route path="/whatsapp" element={<PreLancamentosWhatsappPage />} />
        <Route path="/parceiros" element={<ParceirosPage />} />
        <Route path="/centros-custo" element={<CentrosCustoPage />} />
        <Route path="/contas-bancarias" element={<ContasBancariasPage />} />
        <Route
          path="/usuarios"
          element={
            <ProtectedRoute roles={['admin', 'master']}>
              <UsuariosPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/auditoria"
          element={
            <ProtectedRoute roles={['admin', 'master']}>
              <AuditoriaPage />
            </ProtectedRoute>
          }
        />
        <Route path="/lancamentos-recorrentes" element={<LancamentosRecorrentesPage />} />
        <Route path="/notas-fiscais" element={<NotasFiscaisPage />} />
        <Route path="/extratos" element={<ExtratosPage />} />
      </Route>
    </Routes>
  )
}

export default App
