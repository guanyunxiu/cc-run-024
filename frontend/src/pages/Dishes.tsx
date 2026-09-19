import { useState } from 'react'
import {
  Button, Card, Input, Select, Space, Table, Tag, Typography, App, Tooltip,
} from 'antd'
import { PlusOutlined, DeleteOutlined } from '@ant-design/icons'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate } from 'react-router-dom'
import { api, apiError } from '../api/client'
import { CATEGORY_LABELS } from '../lib/types'
import { useAuthStore } from '../store/auth'

export default function Dishes() {
  const [kw, setKw] = useState('')
  const [category, setCategory] = useState('')
  const [residentId, setResidentId] = useState<number | undefined>()
  const nav = useNavigate()
  const qc = useQueryClient()
  const { message, modal } = App.useApp()
  const role = useAuthStore((s) => s.user?.role)
  const canWrite = role === 'admin' || role === 'nutritionist'

  const { data: residents } = useQuery({
    queryKey: ['residents'],
    queryFn: async () => (await api.get('/api/residents')).data,
  })
  const { data, isLoading } = useQuery({
    queryKey: ['dishes', kw, category, residentId],
    queryFn: async () => (await api.get('/api/dishes', {
      params: { kw, category, resident_id: residentId },
    })).data,
  })

  const delMu = useMutation({
    mutationFn: async (id: number) => (await api.delete(`/api/dishes/${id}`)).data,
    onSuccess: () => {
      message.success('菜品已停用')
      qc.invalidateQueries({ queryKey: ['dishes'] })
    },
    onError: (e) => message.error(apiError(e)),
  })

  return (
    <div className="page-container">
      <Card title="菜品营养库" extra={
        <Space>
          <Input.Search placeholder="搜索菜名" allowClear style={{ width: 160 }}
                        onSearch={setKw}
                        onChange={(e) => !e.target.value && setKw('')} />
          <Select allowClear placeholder="类别" style={{ width: 120 }}
                  value={category || undefined} onChange={(v) => setCategory(v || '')}
                  options={Object.entries(CATEGORY_LABELS).map(([v, l]) =>
                    ({ value: v, label: l }))} />
          <Select allowClear placeholder="按老人校验禁忌" style={{ width: 170 }}
                  value={residentId} onChange={setResidentId}
                  options={(residents || []).map((r: any) =>
                    ({ value: r.id, label: `${r.name} (IDDSI ${r.swallowing_level})` }))} />
          {canWrite && (
            <Button type="primary" icon={<PlusOutlined />}
                    onClick={() => nav('/dishes/new')}>新建菜品</Button>
          )}
        </Space>
      }>
        <Table rowKey="id" loading={isLoading} dataSource={(data || []) as any[]}
               scroll={{ x: 1200 }}
               columns={[
                 { title: '菜名', dataIndex: 'name', width: 150,
                   render: (t, r) => (
                     <Space direction="vertical" size={0}>
                       <Link to={`/dishes/${r.id}/edit`}><b>{t}</b></Link>
                       {residentId && r.check && !r.check.eligible && (
                         <Tooltip title={r.check.hard.map((h: any) => h.message).join('；')}>
                           <Tag color="red">{r.check.hard.length} 项硬冲突</Tag>
                         </Tooltip>
                       )}
                       {residentId && r.check?.soft?.length > 0 && (
                         <Tooltip title={r.check.soft.map((h: any) => h.message).join('；')}>
                           <Tag color="orange">{r.check.soft.length} 项软提示</Tag>
                         </Tooltip>
                       )}
                     </Space>) },
                 { title: '类别', dataIndex: 'category', width: 80,
                   render: (c) => CATEGORY_LABELS[c] || c },
                 { title: 'IDDSI', dataIndex: 'iddsi_level', width: 70,
                   render: (v) => <Tag color={v >= 6 ? 'green' : 'orange'}>{v}</Tag> },
                 { title: '能量', dataIndex: 'energy_kcal', width: 80, align: 'right',
                   render: (v) => `${v?.toFixed(0)}` },
                 { title: '蛋白g', dataIndex: 'protein_g', width: 70, align: 'right',
                   render: (v) => v?.toFixed(1) },
                 { title: '钠mg', dataIndex: 'sodium_mg', width: 80, align: 'right',
                   render: (v) => v?.toFixed(0) },
                 { title: '钾mg', dataIndex: 'potassium_mg', width: 80, align: 'right',
                   render: (v) => v?.toFixed(0) },
                 { title: '磷mg', dataIndex: 'phosphorus_mg', width: 80, align: 'right',
                   render: (v) => v?.toFixed(0) },
                 { title: '成本', dataIndex: 'cost', width: 70, align: 'right',
                   render: (v) => `¥${v?.toFixed(2)}` },
                 { title: '喜好', dataIndex: 'satisfaction', width: 70, align: 'right',
                   render: (v) => v?.toFixed(1) },
                 { title: '标签', dataIndex: 'tags',
                   render: (tags: string[], r) => (
                     <Space wrap size={2}>
                       {tags.map((t) => <Tag key={t}>{t}</Tag>)}
                       {(r.allergens || []).map((a: string) =>
                         <Tag key={a} color="volcano">{a}</Tag>)}
                     </Space>) },
                 { title: '状态', dataIndex: 'active', width: 70,
                   render: (a) => a ? <Tag color="green">启用</Tag>
                                    : <Tag>停用</Tag> },
                 { title: '操作', width: 90,
                   render: (_, r) => (
                     <Space>
                       <Link to={`/dishes/${r.id}/edit`}>编辑</Link>
                       {role === 'admin' && r.active && (
                         <Typography.Link type="danger"
                           onClick={() => modal.confirm({
                             title: `停用菜品「${r.name}」？`,
                             content: '停用后历史方案保留，求解器不再选用。',
                             onOk: () => delMu.mutate(r.id),
                           })}><DeleteOutlined /></Typography.Link>
                       )}
                     </Space>) },
               ]} />
      </Card>
    </div>
  )
}
