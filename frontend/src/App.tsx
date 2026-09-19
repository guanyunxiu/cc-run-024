import { Navigate, Route, Routes } from 'react-router-dom'
import MainLayout from './components/MainLayout'
import Login from './pages/Login'
import Dashboard from './pages/Dashboard'
import Residents from './pages/Residents'
import ResidentDetail from './pages/ResidentDetail'
import Dishes from './pages/Dishes'
import DishEdit from './pages/DishEdit'
import Ingredients from './pages/Ingredients'
import Rules from './pages/Rules'
import Plans from './pages/Plans'
import PlanEditor from './pages/PlanEditor'
import Report from './pages/Report'
import AuditLogs from './pages/AuditLogs'
import { useAuthStore } from './store/auth'

function RequireAuth({ children }: { children: JSX.Element }) {
  const token = useAuthStore((s) => s.token)
  return token ? children : <Navigate to="/login" replace />
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route
        path="/"
        element={
          <RequireAuth>
            <MainLayout />
          </RequireAuth>
        }
      >
        <Route index element={<Dashboard />} />
        <Route path="residents" element={<Residents />} />
        <Route path="residents/:id" element={<ResidentDetail />} />
        <Route path="dishes" element={<Dishes />} />
        <Route path="dishes/new" element={<DishEdit />} />
        <Route path="dishes/:id/edit" element={<DishEdit />} />
        <Route path="ingredients" element={<Ingredients />} />
        <Route path="rules" element={<Rules />} />
        <Route path="plans" element={<Plans />} />
        <Route path="plans/:id" element={<PlanEditor />} />
        <Route path="plans/:id/report" element={<Report />} />
        <Route path="audit-logs" element={<AuditLogs />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
