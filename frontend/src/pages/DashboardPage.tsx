import { Card, Col, Row, Statistic, List, Tag, Button, Typography, Space, Empty } from 'antd'
import { useNavigate } from 'react-router-dom'
import { TeamOutlined, CoffeeOutlined, ProfileOutlined, CheckCircleOutlined } from '@ant-design/icons'
import { useElders, useDishes, usePlans } from '../api/hooks'
import { DISEASE_LABELS, IDDSI_LABELS } from '../lib/types'

export default function DashboardPage() {
  const nav = useNavigate()
  const { data: elders } = useElders()
  const { data: dishes } = useDishes()
  const { data: plans } = usePlans()
  const published = (plans || []).filter((p) => p.status === 'published')
  const drafts = (plans || []).filter((p) => p.status === 'draft')

  return (
    <Space direction="vertical" size={16} style={{ width: '100%' }}>
      <Row gutter={16}>
        <Col span={6}>
          <Card hoverable onClick={() => nav('/elders')}>
            <Statistic title="在册老人" value={elders?.length ?? 0} prefix={<TeamOutlined />} />
          </Card>
        </Col>
        <Col span={6}>
          <Card hoverable onClick={() => nav('/food')}>
            <Statistic title="菜品数量" value={dishes?.length ?? 0} prefix={<CoffeeOutlined />} />
          </Card>
        </Col>
        <Col span={6}>
          <Card hoverable onClick={() => nav('/plans')}>
            <Statistic title="配餐方案" value={plans?.length ?? 0} prefix={<ProfileOutlined />} />
          </Card>
        </Col>
        <Col span={6}>
          <Card hoverable onClick={() => nav('/plans')}>
            <Statistic title="已发布方案" value={published.length}
              prefix={<CheckCircleOutlined />} valueStyle={{ color: '#389e0d' }} />
          </Card>
        </Col>
      </Row>

      <Row gutter={16}>
        <Col span={14}>
          <Card title="老人档案速览" extra={
            <Button type="link" onClick={() => nav('/elders')}>全部档案</Button>}>
            <List
              dataSource={elders || []}
              locale={{ emptyText: <Empty description="暂无老人" /> }}
              renderItem={(e) => (
                <List.Item
                  actions={[
                    <Button key="s" type="link"
                      onClick={() => nav(`/elders/${e.id}`)}>目标</Button>,
                    <Button key="p" type="primary" ghost size="small"
                      onClick={() => nav(`/plans?elder=${e.id}`)}>配餐</Button>,
                  ]}
                >
                  <List.Item.Meta
                    title={<Space>{e.name}
                      <Tag color={e.gender === 'male' ? 'blue' : 'magenta'}>
                        {e.gender === 'male' ? '男' : '女'}
                      </Tag>
                      <Tag>{IDDSI_LABELS[e.iddsi_level]}</Tag>
                    </Space>}
                    description={
                      <Space size={4} wrap>
                        {(e.chronic_diseases ? e.chronic_diseases.split(',').filter(Boolean) : [])
                          .map((d) => <Tag key={d} color="orange">
                            {DISEASE_LABELS[d] || d}</Tag>)}
                        {e.allergies.split(',').filter(Boolean).map((a) =>
                          <Tag key={a} color="red">过敏:{a}</Tag>)}
                        {e.religion !== 'none' && <Tag color="geekblue">{e.religion}</Tag>}
                        <Typography.Text type="secondary">
                          日餐费上限 ¥{e.cost_limit_day}
                        </Typography.Text>
                      </Space>
                    }
                  />
                </List.Item>
              )}
            />
          </Card>
        </Col>
        <Col span={10}>
          <Card title="最近方案" extra={
            <Button type="link" onClick={() => nav('/plans')}>全部方案</Button>}>
            <List
              dataSource={(plans || []).slice(0, 8)}
              locale={{ emptyText: <Empty description="暂无方案，去创建吧" /> }}
              renderItem={(p) => (
                <List.Item
                  actions={[
                    <Button key="open" type="link"
                      onClick={() => nav(`/plans/${p.id}`)}>打开</Button>,
                  ]}
                >
                  <List.Item.Meta
                    title={p.title}
                    description={
                      <Space wrap>
                        <Tag color={p.status === 'published' ? 'green'
                          : p.status === 'archived' ? 'default' : 'gold'}>
                          {p.status === 'published' ? '已发布'
                            : p.status === 'archived' ? '已归档' : '草稿'}
                        </Tag>
                        <Typography.Text type="secondary">
                          {p.period_type === 'week' ? '周方案' : '日方案'} {p.start_date}
                        </Typography.Text>
                        {drafts.includes(p) && <Typography.Text type="warning">草稿</Typography.Text>}
                      </Space>
                    }
                  />
                </List.Item>
              )}
            />
          </Card>
        </Col>
      </Row>
    </Space>
  )
}
