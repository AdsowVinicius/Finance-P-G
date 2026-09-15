import { Navigate, Route, Routes } from 'react-router-dom'
import { Layout } from './components/Layout'
import { ProtectedRoute } from './components/ProtectedRoute'
import { useAuth } from './contexts/AuthContext'
import { AssistentePage } from './pages/AssistentePage'
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
        <Route path="/assistente" element={<AssistentePage />} />
        <Route path="/whatsapp" element={<PreLancamentosWhatsappPage />} />
        <Route path="/parceiros" element={<ParceirosPage />} />
        <Route path="/centros-custo" element={<CentrosCustoPage />} />
        <Route path="/contas-bancarias" element={<ContasBancariasPage />} />
        <Route path="/usuarios" element={<UsuariosPage />} />
        <Route path="/lancamentos-recorrentes" element={<LancamentosRecorrentesPage />} />
        <Route path="/notas-fiscais" element={<NotasFiscaisPage />} />
        <Route path="/extratos" element={<ExtratosPage />} />
      </Route>
    </Routes>
  )
}

export default App
