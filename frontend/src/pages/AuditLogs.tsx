import { useState } from 'react'
import { Card, Select, Space, Table, Tag, Typography } from 'antd'
import { useQuery } from '@tanstack/react-query'
import dayjs from 'dayjs'
import { api } from '../api/client'

const ACTION_COLOR: Record<string, string> = {
  create: 'green', update: 'blue', delete: 'red', solve: 'cyan',
  resolve: 'cyan', publish: 'gold', rollback: 'orange', archive: 'default',
  export: 'purple', login: 'default',
}

export default function AuditLogs() {
  const [action, setAction] = useState('')
  const [entity, setEntity] = useState('')
  const [page, setPage] = useState(1)

  const { data } = useQuery({
    queryKey: ['audit-logs', action, entity, page],
    queryFn: async () => (await api.get('/api/audit-logs', {
      params: { action, entity, page, size: 30 },
    })).data,
  })

  const actionLabels = data?.action_labels || {}
  const entityLabels = data?.entity_labels || {}

  return (
    <div className="page-container">
      <Card title="操作审计日志" extra={
        <Space>
          <Select allowClear placeholder="操作类型" style={{ width: 140 }}
                  value={action || undefined} onChange={(v) => { setAction(v || ''); setPage(1) }}
                  options={Object.entries(actionLabels).map(([v, l]: any) =>
                    ({ value: v, label: l }))} />
          <Select allowClear placeholder="对象类型" style={{ width: 140 }}
                  value={entity || undefined} onChange={(v) => { setEntity(v || ''); setPage(1) }}
                  options={Object.entries(entityLabels).map(([v, l]: any) =>
                    ({ value: v, label: l }))} />
        </Space>
      }>
        <Table rowKey="id" size="middle"
               dataSource={(data?.items || []) as any[]}
               pagination={{
                 current: page, pageSize: 30, total: data?.total || 0,
                 showTotal: (t) => `共 ${t} 条`, onChange: setPage,
               }}
               columns={[
                 { title: '时间', dataIndex: 'ts', width: 170,
                   render: (t) => dayjs(t).format('YYYY-MM-DD HH:mm:ss') },
                 { title: '操作人', dataIndex: 'username', width: 120 },
                 { title: '操作', dataIndex: 'action', width: 100,
                   render: (a) => <Tag color={ACTION_COLOR[a]}>{actionLabels[a] || a}</Tag> },
                 { title: '对象', dataIndex: 'entity', width: 120,
                   render: (e, r) =>
                     `${entityLabels[e] || e}${r.entity_id ? ` #${r.entity_id}` : ''}` },
                 { title: '详情', dataIndex: 'detail',
                   render: (d) => (
                     <Typography.Text code style={{ fontSize: 12 }}>
                       {JSON.stringify(d)}
                     </Typography.Text>) },
               ]} />
      </Card>
    </div>
  )
}
