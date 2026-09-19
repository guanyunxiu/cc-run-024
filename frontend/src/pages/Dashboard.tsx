import { Card, Col, Row, Statistic, Table, Tag, Button, Typography, Space, Empty } from 'antd'
import { useQuery } from '@tanstack/react-query'
import { Link, useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import { TeamOutlined, CalendarOutlined, CoffeeOutlined, CheckCircleOutlined } from '@ant-design/icons'

const STATUS: Record<string, { color: string; text: string }> = {
  draft: { color: 'default', text: '草稿' },
  published: { color: 'green', text: '已发布' },
  archived: { color: 'orange', text: '已归档' },
}

export default function Dashboard() {
  const nav = useNavigate()
  const { data: residents } = useQuery({
    queryKey: ['residents'],
    queryFn: async () => (await api.get('/api/residents')).data,
  })
  const { data: plans } = useQuery({
    queryKey: ['plans'],
    queryFn: async () => (await api.get('/api/plans')).data,
  })
  const { data: dishes } = useQuery({
    queryKey: ['dishes-count'],
    queryFn: async () => (await api.get('/api/dishes')).data,
  })

  const published = (plans || []).filter((p: any) => p.status === 'published').length

  return (
    <div className="page-container">
      <Row gutter={16}>
        <Col span={6}>
          <Card className="stat-card">
            <Statistic title="在册老人" value={residents?.length || 0}
                       prefix={<TeamOutlined />} />
          </Card>
        </Col>
        <Col span={6}>
          <Card className="stat-card">
            <Statistic title="配餐方案" value={plans?.length || 0}
                       prefix={<CalendarOutlined />} />
          </Card>
        </Col>
        <Col span={6}>
          <Card className="stat-card">
            <Statistic title="已发布方案" value={published}
                       prefix={<CheckCircleOutlined />} valueStyle={{ color: '#52c41a' }} />
          </Card>
        </Col>
        <Col span={6}>
          <Card className="stat-card">
            <Statistic title="菜品数量" value={dishes?.length || 0}
                       prefix={<CoffeeOutlined />} />
          </Card>
        </Col>
      </Row>

      <Row gutter={16} style={{ marginTop: 16 }}>
        <Col span={14}>
          <Card title="最近配餐方案" extra={<Link to="/plans">全部方案</Link>}>
            <Table rowKey="id" size="small" pagination={{ pageSize: 6 }}
                   dataSource={(plans || []) as any[]}
                   onRow={(r) => ({ onClick: () => nav(`/plans/${r.id}`),
                                    style: { cursor: 'pointer' } })}
                   columns={[
                     { title: '方案', dataIndex: 'name' },
                     { title: '老人', dataIndex: 'resident_name', width: 90 },
                     { title: '天数', dataIndex: 'days', width: 60 },
                     { title: '达标率', width: 90,
                       render: (_, r) =>
                         `${r.score?.avg_attainment_pct?.toFixed?.(0) ?? r.score?.avg_attainment_pct ?? '—'}%` },
                     { title: '状态', dataIndex: 'status', width: 80,
                       render: (s) => <Tag color={STATUS[s]?.color}>{STATUS[s]?.text}</Tag> },
                   ]} />
          </Card>
        </Col>
        <Col span={10}>
          <Card title="在管老人" extra={<Link to="/residents">档案管理</Link>}>
            <Space direction="vertical" style={{ width: '100%' }}>
              {(residents || []).slice(0, 7).map((r: any) => (
                <Card key={r.id} size="small" hoverable
                      onClick={() => nav(`/residents/${r.id}`)}
                      style={{ cursor: 'pointer' }}>
                  <Space style={{ width: '100%', justifyContent: 'space-between' }}>
                    <Space>
                      <Typography.Text strong>{r.name}</Typography.Text>
                      <span style={{ color: '#999' }}>{r.age}岁 · IDDSI {r.swallowing_level}</span>
                    </Space>
                    <Space size={4}>
                      {r.chronic_conditions.slice(0, 3).map((c: string) => (
                        <Tag key={c} color="red">{c}</Tag>
                      ))}
                    </Space>
                  </Space>
                </Card>
              ))}
              {(!residents || residents.length === 0) && <Empty />}
            </Space>
          </Card>
        </Col>
      </Row>

      <Card style={{ marginTop: 16 }}>
        <Space>
          <Button type="primary" onClick={() => nav('/plans')}>进入排餐</Button>
          <Button onClick={() => nav('/residents')}>维护老人档案</Button>
          <Button onClick={() => nav('/rules')}>查看禁忌规则</Button>
        </Space>
      </Card>
    </div>
  )
}
