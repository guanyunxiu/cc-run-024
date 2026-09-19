import { useState } from 'react'
import { Layout, Menu, Dropdown, Avatar, Space, Typography } from 'antd'
import {
  DashboardOutlined, TeamOutlined, CoffeeOutlined, AppstoreOutlined,
  SafetyCertificateOutlined, CalendarOutlined, FileTextOutlined,
  AuditOutlined, LogoutOutlined, UserOutlined, ShopOutlined,
} from '@ant-design/icons'
import { Outlet, useLocation, useNavigate } from 'react-router-dom'
import { ROLE_LABELS, useAuthStore } from '../store/auth'

const { Sider, Header, Content } = Layout

const menu = [
  { key: '/', icon: <DashboardOutlined />, label: '工作台' },
  { key: '/residents', icon: <TeamOutlined />, label: '老人档案' },
  { key: '/plans', icon: <CalendarOutlined />, label: '排餐方案' },
  { key: '/dishes', icon: <CoffeeOutlined />, label: '菜品营养库' },
  { key: '/ingredients', icon: <AppstoreOutlined />, label: '食材库' },
  { key: '/rules', icon: <SafetyCertificateOutlined />, label: '禁忌规则' },
  { key: '/audit-logs', icon: <AuditOutlined />, label: '操作日志' },
]

export default function MainLayout() {
  const [collapsed, setCollapsed] = useState(false)
  const nav = useNavigate()
  const loc = useLocation()
  const { user, logout } = useAuthStore()

  const selected =
    menu
      .map((m) => m.key)
      .filter((k) => (k === '/' ? loc.pathname === '/' : loc.pathname.startsWith(k)))
      .sort((a, b) => b.length - a.length)[0] || '/'

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider collapsible collapsed={collapsed} onCollapse={setCollapsed}
             className={collapsed ? 'sider-collapsed' : ''} width={210}>
        <div className="app-logo">
          <span className="logo-mark">🍲</span>
          <span className="txt">老年营养配餐系统</span>
        </div>
        <Menu theme="dark" mode="inline" selectedKeys={[selected]}
              items={menu} onClick={(e) => nav(e.key)} />
      </Sider>
      <Layout>
        <Header style={{ background: '#fff', padding: '0 20px',
                        display: 'flex', justifyContent: 'space-between',
                        alignItems: 'center', boxShadow: '0 1px 4px rgba(0,21,41,.08)' }}>
          <Typography.Text strong style={{ fontSize: 15 }}>
            老年营养与慢病配餐优化管理系统
          </Typography.Text>
          <Dropdown
            menu={{
              items: [
                { key: 'role', label: `角色：${ROLE_LABELS[user?.role || '']}`,
                  disabled: true, icon: <ShopOutlined /> },
                { type: 'divider' },
                { key: 'logout', label: '退出登录', icon: <LogoutOutlined />,
                  onClick: () => { logout(); nav('/login') } },
              ],
            }}
          >
            <Space style={{ cursor: 'pointer' }}>
              <Avatar icon={<UserOutlined />} style={{ background: '#2f5496' }} />
              <span>{user?.name}</span>
            </Space>
          </Dropdown>
        </Header>
        <Content>
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  )
}
