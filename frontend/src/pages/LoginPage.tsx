import { useState } from 'react'
import { Card, Form, Input, Button, Typography, Alert, Tabs } from 'antd'
import { UserOutlined, LockOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import { useLogin } from '../api/hooks'
import { useAuthStore } from '../store/auth'

export default function LoginPage() {
  const [err, setErr] = useState('')
  const login = useLogin()
  const setAuth = useAuthStore((s) => s.setAuth)
  const nav = useNavigate()

  const onFinish = (v: { username: string; password: string }) => {
    setErr('')
    login.mutate(v, {
      onSuccess: (data) => {
        setAuth(data.access_token, data.user)
        nav('/')
      },
      onError: (e: unknown) => {
        const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
        setErr(msg || '登录失败')
      },
    })
  }

  return (
    <div
      style={{
        minHeight: '100vh', display: 'flex', alignItems: 'center',
        justifyContent: 'center',
        background: 'linear-gradient(135deg,#1f3a5f 0%,#2f6fb0 60%,#5aa0d8 100%)',
      }}
    >
      <Card style={{ width: 420, boxShadow: '0 12px 40px rgba(0,0,0,0.25)' }}>
        <div style={{ textAlign: 'center', marginBottom: 18 }}>
          <div style={{ fontSize: 34 }}>🥗</div>
          <Typography.Title level={4} style={{ marginBottom: 2 }}>
            颐养配餐系统
          </Typography.Title>
          <Typography.Text type="secondary">
            老年营养与慢病配餐优化管理平台
          </Typography.Text>
        </div>
        {err && <Alert type="error" message={err} style={{ marginBottom: 12 }} showIcon />}
        <Form onFinish={onFinish} size="large" initialValues={{ username: 'nutritionist', password: 'nutri123' }}>
          <Form.Item name="username" rules={[{ required: true, message: '请输入用户名' }]}>
            <Input prefix={<UserOutlined />} placeholder="用户名" />
          </Form.Item>
          <Form.Item name="password" rules={[{ required: true, message: '请输入密码' }]}>
            <Input.Password prefix={<LockOutlined />} placeholder="密码" />
          </Form.Item>
          <Button type="primary" htmlType="submit" block loading={login.isPending}>
            登 录
          </Button>
        </Form>
        <Tabs
          size="small"
          style={{ marginTop: 8 }}
          items={[
            {
              key: 'a', label: '演示账号',
              children: (
                <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                  管理员：admin / admin123<br />
                  营养师：nutritionist / nutri123
                </Typography.Text>
              ),
            },
          ]}
        />
      </Card>
    </div>
  )
}
