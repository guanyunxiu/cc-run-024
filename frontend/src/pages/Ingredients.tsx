import { useState } from 'react'
import {
  Button, Card, Form, Input, InputNumber, Modal, Select, Space, Table, App,
} from 'antd'
import { PlusOutlined } from '@ant-design/icons'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, apiError } from '../api/client'
import { useAuthStore } from '../store/auth'

const CATS = ['主食', '蔬菜', '蛋奶', '肉类', '鱼类', '鱼虾', '豆制品',
  '水果', '调味', '油脂', '坚果', '其他']

export default function Ingredients() {
  const [kw, setKw] = useState('')
  const [category, setCategory] = useState('')
  const [open, setOpen] = useState(false)
  const [editing, setEditing] = useState<any>(null)
  const [form] = Form.useForm()
  const qc = useQueryClient()
  const { message } = App.useApp()
  const role = useAuthStore((s) => s.user?.role)
  const canWrite = role === 'admin' || role === 'nutritionist'

  const { data, isLoading } = useQuery({
    queryKey: ['ingredients', kw, category],
    queryFn: async () => (await api.get('/api/ingredients', {
      params: { kw, category },
    })).data,
  })

  const saveMu = useMutation({
    mutationFn: async (v: any) =>
      editing ? api.put(`/api/ingredients/${editing.id}`, v)
              : api.post('/api/ingredients', v),
    onSuccess: () => {
      message.success(editing ? '食材已更新' : '食材已创建')
      setOpen(false)
      qc.invalidateQueries({ queryKey: ['ingredients'] })
      qc.invalidateQueries({ queryKey: ['ingredients-all'] })
    },
    onError: (e) => message.error(apiError(e)),
  })

  return (
    <div className="page-container">
      <Card title="食材营养库（每100g可食部）" extra={
        <Space>
          <Input.Search placeholder="搜索食材" allowClear style={{ width: 150 }}
                        onSearch={setKw}
                        onChange={(e) => !e.target.value && setKw('')} />
          <Select allowClear placeholder="分类" style={{ width: 110 }}
                  value={category || undefined}
                  onChange={(v) => setCategory(v || '')}
                  options={CATS.map((c) => ({ value: c, label: c }))} />
          {canWrite && (
            <Button type="primary" icon={<PlusOutlined />} onClick={() => {
              setEditing(null); form.resetFields(); setOpen(true)
            }}>新建食材</Button>
          )}
        </Space>
      }>
        <Table rowKey="id" loading={isLoading} dataSource={(data || []) as any[]}
               scroll={{ x: 1100 }} size="middle"
               onRow={(r) => ({
                 onClick: () => {
                   if (!canWrite) return
                   setEditing(r)
                   form.setFieldsValue(r)
                   setOpen(true)
                 },
                 style: { cursor: canWrite ? 'pointer' : 'default' },
               })}
               columns={[
                 { title: '食材', dataIndex: 'name', width: 130,
                   render: (t, r) => <Space direction="vertical" size={0}>
                     <b>{t}</b>
                     <span style={{ fontSize: 11, color: '#999' }}>
                       可食部 {r.edible_pct}% · ¥{r.unit_cost}/kg
                     </span>
                   </Space> },
                 { title: '分类', dataIndex: 'category', width: 80 },
                 { title: '能量', dataIndex: 'energy_kcal', align: 'right' },
                 { title: '蛋白g', dataIndex: 'protein_g', align: 'right',
                   render: (v) => v?.toFixed(1) },
                 { title: '脂肪g', dataIndex: 'fat_g', align: 'right',
                   render: (v) => v?.toFixed(1) },
                 { title: '碳水g', dataIndex: 'carb_g', align: 'right',
                   render: (v) => v?.toFixed(1) },
                 { title: '钠mg', dataIndex: 'sodium_mg', align: 'right' },
                 { title: '钾mg', dataIndex: 'potassium_mg', align: 'right' },
                 { title: '磷mg', dataIndex: 'phosphorus_mg', align: 'right' },
                 { title: '钙mg', dataIndex: 'calcium_mg', align: 'right' },
                 { title: '维Kμg', dataIndex: 'vitamin_k_ug', align: 'right' },
                 { title: '标签', dataIndex: 'tags',
                   render: (t: string[], r) => (
                     <Space wrap size={2}>
                       {(t || []).map((x) => <span key={x}
                         style={{ fontSize: 11 }}>#{x}</span>)}
                       {(r.allergens || []).map((a: string) =>
                         <span key={a} style={{ fontSize: 11, color: '#cf1322' }}>⚡{a}</span>)}
                     </Space>) },
               ]} />
      </Card>

      <Modal title={editing ? `编辑食材：${editing.name}` : '新建食材'}
             open={open} width={760} destroyOnClose
             onCancel={() => setOpen(false)}
             onOk={() => form.validateFields().then((v) => saveMu.mutate(v))}
             confirmLoading={saveMu.isPending}>
        <Form form={form} layout="vertical"
              initialValues={{ edible_pct: 100, category: '其他',
                allergens: [], tags: [] }}>
          <Space wrap size={12}>
            <Form.Item name="name" label="名称" rules={[{ required: true }]}>
              <Input style={{ width: 160 }} />
            </Form.Item>
            <Form.Item name="category" label="分类">
              <Select style={{ width: 110 }} options={CATS.map((c) => ({ value: c, label: c }))} />
            </Form.Item>
            <Form.Item name="edible_pct" label="可食部%">
              <InputNumber min={1} max={100} />
            </Form.Item>
            <Form.Item name="unit_cost" label="单价(元/kg)">
              <InputNumber min={0} step={0.5} />
            </Form.Item>
          </Space>
          <Space wrap size={12}>
            {[['energy_kcal', '能量kcal'], ['protein_g', '蛋白质g'],
              ['fat_g', '脂肪g'], ['carb_g', '碳水g'], ['sodium_mg', '钠mg'],
              ['potassium_mg', '钾mg'], ['phosphorus_mg', '磷mg'],
              ['fiber_g', '纤维g'], ['calcium_mg', '钙mg'],
              ['vitamin_k_ug', '维Kμg'], ['purine_mg', '嘌呤mg'],
              ['glycemic_index', 'GI']].map(([k, label]) => (
              <Form.Item key={k} name={k} label={label}>
                <InputNumber min={0} step={0.1} style={{ width: 100 }} />
              </Form.Item>
            ))}
          </Space>
          <Form.Item name="allergens" label="过敏原">
            <Select mode="tags" style={{ width: '100%' }} placeholder="egg/milk/fish/..." />
          </Form.Item>
          <Form.Item name="tags" label="标签">
            <Select mode="tags" style={{ width: '100%' }}
                    placeholder="pork/high_potassium/high_purine/..." />
          </Form.Item>
          <Form.Item name="note" label="备注">
            <Input.TextArea rows={2} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
