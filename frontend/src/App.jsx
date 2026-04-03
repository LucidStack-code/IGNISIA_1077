import { Navigate, Route, Routes } from 'react-router-dom'
import AdminDashboard from './views/AdminDashboard'
import CustomerView from './views/CustomerView'

export default function App() {
  return (
    <Routes>
      <Route path="/admin" element={<AdminDashboard />} />
      <Route path="/customer" element={<CustomerView />} />
      <Route path="*" element={<Navigate to="/admin" replace />} />
    </Routes>
  )
}
