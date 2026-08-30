import { Button, Layout, Menu, Space, Spin, Typography } from 'antd'
import type { ReactNode } from 'react'
import {
  Navigate,
  Route,
  Routes,
  useLocation,
  useNavigate,
} from 'react-router-dom'

import { useAuth } from './auth/AuthContext'
import DashboardPage from './pages/DashboardPage'
import EmployeeDetailPage from './pages/EmployeeDetailPage'
import EmployeesPage from './pages/EmployeesPage'
import LoginPage from './pages/LoginPage'

const { Header, Content } = Layout
const { Title } = Typography

export default function App() {
  const { loading } = useAuth()

  // Wait for the first /auth/me before routing, or a signed-in reload flashes
  // the login page on its way to the destination.
  if (loading) {
    return (
      <div style={{ display: 'grid', placeItems: 'center', minHeight: '100vh' }}>
        <Spin size="large" />
      </div>
    )
  }

  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        path="/"
        element={<Navigate to="/employees" replace />}
      />
      <Route
        path="/employees"
        element={
          <RequireAuth>
            <AppShell>
              <EmployeesPage />
            </AppShell>
          </RequireAuth>
        }
      />
      <Route
        path="/employees/:id"
        element={
          <RequireAuth>
            <AppShell>
              <EmployeeDetailPage />
            </AppShell>
          </RequireAuth>
        }
      />
      <Route
        path="/dashboard"
        element={
          <RequireAuth>
            <AppShell>
              <DashboardPage />
            </AppShell>
          </RequireAuth>
        }
      />
      <Route path="*" element={<Navigate to="/employees" replace />} />
    </Routes>
  )
}

function RequireAuth({ children }: { children: ReactNode }) {
  const { user } = useAuth()
  const location = useLocation()

  if (!user) {
    // Remember where they were headed so login can return them there.
    return <Navigate to="/login" replace state={{ from: location.pathname }} />
  }
  return <>{children}</>
}

function AppShell({ children }: { children: ReactNode }) {
  const { user, signOut } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()

  const selected = location.pathname.startsWith('/dashboard')
    ? 'dashboard'
    : 'employees'

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Header style={{ display: 'flex', alignItems: 'center', gap: 24 }}>
        <Title level={5} style={{ color: '#fff', margin: 0, whiteSpace: 'nowrap' }}>
          ACME Salary
        </Title>
        <Menu
          theme="dark"
          mode="horizontal"
          selectedKeys={[selected]}
          style={{ flex: 1, minWidth: 0 }}
          onClick={({ key }) => navigate(`/${key}`)}
          items={[
            { key: 'employees', label: 'Employees' },
            { key: 'dashboard', label: 'Dashboard' },
          ]}
        />
        <Space>
          <Typography.Text style={{ color: 'rgba(255,255,255,0.75)' }}>
            {user?.username}
          </Typography.Text>
          <Button
            size="small"
            onClick={async () => {
              await signOut()
              navigate('/login', { replace: true })
            }}
          >
            Sign out
          </Button>
        </Space>
      </Header>
      <Content style={{ padding: 24 }}>{children}</Content>
    </Layout>
  )
}
