import { Card, Table, Button, Tag, Space, Popconfirm, App } from 'antd'
import { PlusOutlined, ReloadOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import { useState } from 'react'
import { useElders } from '../api/hooks'
import type { Elder } from '../lib/types'
import { DISEASE_LABELS, IDDSI_LABELS } from '../lib/types'
import ElderFormModal from '../components/ElderFormModal'

export default function EldersPage() {
  const nav = useNavigate()
  const { data, isLoading, refetch } = useElders()
  const [editing, setEditing] = useState<Elder | null>(null)
  const [creating, setCreating] = useState(false)

  const columns = [
    { title: '姓名', dataIndex: 'name', width: 100,
      render: (v: string, r: Elder) => <a onClick={() => nav(`/elders/${r.id}`)}>{v}</a> },
    { title: '性别', dataIndex: 'gender', width: 70,
      render: (v: string) => (v === 'male' ? '男' : '女') },
    { title: '出生', dataIndex: 'birth_date', width: 110 },
    { title: '身高/体重', width: 110,
      render: (_: unknown, r: Elder) => `${r.height_cm}cm / ${r.weight_kg}kg` },
    { title: '吞咽等级', dataIndex: 'iddsi_level', width: 120,
      render: (v: number) => <Tag>{IDDSI_LABELS[v]}</Tag> },
    { title: '慢病', dataIndex: 'chronic_diseases',
      render: (v: string) => (
        <Space size={2} wrap>
          {v.split(',').filter(Boolean).map((d) =>
            <Tag color="orange" key={d}>{DISEASE_LABELS[d] || d}</Tag>)}
        </Space>) },
    { title: '过敏/禁忌', width: 160,
      render: (_: unknown, r: Elder) => (
        <Space size={2} wrap>
          {r.allergies.split(',').filter(Boolean).map((a) =>
            <Tag color="red" key={a}>{a}</Tag>)}
          {r.religion !== 'none' && <Tag color="geekblue">{r.religion}</Tag>}
          {!r.allergies && r.religion === 'none' && <span style={{ color: '#aaa' }}>—</span>}
        </Space>) },
    { title: '日餐费', dataIndex: 'cost_limit_day', width: 90,
      render: (v: number) => `¥${v}` },
    { title: '操作', width: 150, fixed: 'right' as const,
      render: (_: unknown, r: Elder) => (
        <Space>
          <Button size="small" onClick={() => nav(`/elders/${r.id}`)}>目标</Button>
          <Button size="small" onClick={() => setEditing(r)}>编辑</Button>
          <Button size="small" type="primary" ghost
            onClick={() => nav(`/plans?elder=${r.id}`)}>配餐</Button>
        </Space>) },
  ]

  return (
    <Card
      title="老人档案"
      extra={<Space>
        <Button icon={<ReloadOutlined />} onClick={() => refetch()}>刷新</Button>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setCreating(true)}>
          新建档案
        </Button>
      </Space>}
    >
      <Table
        rowKey="id" loading={isLoading} columns={columns}
        dataSource={data || []} scroll={{ x: 1100 }} pagination={{ pageSize: 12 }}
      />
      {(creating || editing) && (
        <ElderFormModal
          elder={editing}
          onClose={() => { setCreating(false); setEditing(null) }}
        />
      )}
    </Card>
  )
}
