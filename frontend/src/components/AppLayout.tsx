import { Layout, Menu, Dropdown, Avatar, Typography } from 'antd'
import {
  DashboardOutlined, TeamOutlined, CoffeeOutlined, SafetyCertificateOutlined,
  CalendarOutlined, ProfileOutlined, BarChartOutlined, FileTextOutlined,
  UserOutlined, LogoutOutlined,
} from '@ant-design/icons'
import { Outlet, useLocation, useNavigate } from 'react-router-dom'
import { useAuthStore } from '../store/auth'

const { Header, Sider, Content } = Layout

const MENU = [
  { key: '/', icon: <DashboardOutlined />, label: '工作台' },
  { key: '/elders', icon: <TeamOutlined />, label: '老人档案' },
  { key: '/plans', icon: <ProfileOutlined />, label: '配餐方案' },
  { key: '/calendar', icon: <CalendarOutlined />, label: '排餐日历' },
  { key: '/food', icon: <CoffeeOutlined />, label: '菜品营养库' },
  { key: '/rules', icon: <SafetyCertificateOutlined />, label: '禁忌规则' },
  { key: '/reports', icon: <BarChartOutlined />, label: '报告与对比' },
  { key: '/logs', icon: <FileTextOutlined />, label: '操作日志' },
]

export default function AppLayout() {
  const nav = useNavigate()
  const loc = useLocation()
  const { user, logout } = useAuthStore()
  const selected =
    MENU.map((m) => m.key).filter((k) => k !== '/' && loc.pathname.startsWith(k))[0] ||
    (loc.pathname === '/' ? '/' : '/')

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider theme="dark" width={210} breakpoint="lg" collapsedWidth={64}>
        <div
          style={{
            color: '#fff', fontSize: 15, fontWeight: 700, padding: '18px 20px',
            whiteSpace: 'nowrap', overflow: 'hidden',
          }}
        >
          🥗 颐养配餐系统
        </div>
        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={[selected]}
          items={MENU}
          onClick={(e) => nav(e.key)}
        />
      </Sider>
      <Layout>
        <Header
          style={{
            background: '#fff', padding: '0 24px', display: 'flex',
            justifyContent: 'space-between', alignItems: 'center',
            boxShadow: '0 1px 4px rgba(0,0,0,0.06)',
          }}
        >
          <Typography.Text strong style={{ fontSize: 15 }}>
            老年营养与慢病配餐优化管理系统
          </Typography.Text>
          <Dropdown
            menu={{
              items: [
                {
                  key: 'logout', icon: <LogoutOutlined />, label: '退出登录',
                  onClick: () => { logout(); nav('/login') },
                },
              ],
            }}
          >
            <span style={{ cursor: 'pointer' }}>
              <Avatar size="small" icon={<UserOutlined />} style={{ marginRight: 8 }} />
              {user?.full_name || user?.username}
              <span style={{ color: '#999', marginLeft: 8 }}>
                ({user?.role === 'admin' ? '管理员' : '营养师'})
              </span>
            </span>
          </Dropdown>
        </Header>
        <Content style={{ margin: 16 }}>
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  )
}
