import { useState } from 'react'
import { Card, Table, Tag, Input, Space, Typography } from 'antd'
import dayjs from 'dayjs'
import { useAuditLogs } from '../api/hooks'

const ACTION_COLORS: Record<string, string> = {
  elder: 'blue', dish: 'cyan', ingredient: 'teal', rule: 'purple',
  plan: 'gold', task: 'orange', report: 'green',
}

export default function AuditLogsPage() {
  const { data, isLoading } = useAuditLogs(200)
  const [actionQ, setActionQ] = useState('')
  const rows = (data || []).filter((r) =>
    !actionQ || r.action.includes(actionQ) || r.username.includes(actionQ))

  return (
    <Card
      title="操作审计日志"
      extra={
        <Space>
          <Input.Search placeholder="按动作/用户过滤，如 plan / elder" allowClear
            style={{ width: 280 }} onChange={(e) => setActionQ(e.target.value)} />
        </Space>
      }
    >
      <Typography.Paragraph type="secondary">
        记录档案/菜品/规则/方案/报告导出等全部关键操作；方案类日志附规则版本，
        与方案内"求解器参数快照"共同保证审计完整性与指标一致性。
      </Typography.Paragraph>
      <Table
        rowKey="id" loading={isLoading} dataSource={rows} size="small"
        pagination={{ pageSize: 30 }}
        columns={[
          { title: '时间', dataIndex: 'created_at', width: 170,
            render: (v: string) => dayjs(v).format('YYYY-MM-DD HH:mm:ss') },
          { title: '用户', dataIndex: 'username', width: 120 },
          { title: '动作', dataIndex: 'action', width: 200,
            render: (v: string) => {
              const prefix = v.split('.')[0]
              return <Tag color={ACTION_COLORS[prefix] || 'default'}>{v}</Tag>
            } },
          { title: '对象', width: 140,
            render: (_: unknown, r) => `${r.entity_type}#${r.entity_id}` },
          { title: '规则版本', dataIndex: 'rule_version', width: 110,
            render: (v: string) => v || '—' },
          { title: '详情', render: (_: unknown, r) => (
            <Typography.Text code style={{ fontSize: 12 }}>
              {JSON.stringify(r.detail)}
            </Typography.Text>) },
        ]}
      />
    </Card>
  )
}
