import { useState } from 'react'
import { Button, Card, Form, Input, App } from 'antd'
import { LockOutlined, UserOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import { api, apiError } from '../api/client'
import { useAuthStore } from '../store/auth'

export default function Login() {
  const [loading, setLoading] = useState(false)
  const setAuth = useAuthStore((s) => s.setAuth)
  const nav = useNavigate()
  const { message } = App.useApp()

  const onFinish = async (v: { username: string; password: string }) => {
    setLoading(true)
    try {
      const { data } = await api.post('/api/auth/login', v)
      setAuth(data.access_token, data.user)
      message.success(`欢迎回来，${data.user.name}`)
      nav('/')
    } catch (e) {
      message.error(apiError(e))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center',
                  justifyContent: 'center',
                  background: 'linear-gradient(135deg,#1d3f73,#2f5496)' }}>
      <Card style={{ width: 380, borderRadius: 12 }}
            styles={{ body: { padding: 28 } }}>
        <div style={{ textAlign: 'center', marginBottom: 24 }}>
          <div style={{ fontSize: 40 }}>🍲</div>
          <h2 style={{ margin: '8px 0 4px' }}>老年营养配餐系统</h2>
          <div style={{ color: '#999', fontSize: 12 }}>
            营养 · 慢病 · 吞咽 · 成本 一体化配餐优化
          </div>
        </div>
        <Form onFinish={onFinish} size="large"
              initialValues={{ username: 'dietitian', password: 'Nutri@2026' }}>
          <Form.Item name="username" rules={[{ required: true, message: '请输入用户名' }]}>
            <Input prefix={<UserOutlined />} placeholder="用户名" />
          </Form.Item>
          <Form.Item name="password" rules={[{ required: true, message: '请输入密码' }]}>
            <Input.Password prefix={<LockOutlined />} placeholder="密码" />
          </Form.Item>
          <Button type="primary" htmlType="submit" block loading={loading}>
            登 录
          </Button>
        </Form>
        <div style={{ marginTop: 16, fontSize: 12, color: '#999', lineHeight: 1.9 }}>
          演示账号：<br />
          管理员 admin / Admin@2026<br />
          营养师 dietitian / Nutri@2026<br />
          查看员 viewer / View@2026
        </div>
      </Card>
    </div>
  )
}
