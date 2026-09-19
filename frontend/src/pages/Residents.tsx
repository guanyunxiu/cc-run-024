import { useRef, useState } from 'react'
import {
  Button, Card, Input, Modal, Form, Select, InputNumber, App, Tag, Space,
  Table, Typography,
} from 'antd'
import { PlusOutlined } from '@ant-design/icons'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate } from 'react-router-dom'
import { api, apiError } from '../api/client'
import { useAuthStore } from '../store/auth'

const CHRONIC_LABELS: Record<string, string> = {
  hypertension: '高血压', diabetes: '糖尿病', ckd: '慢性肾病',
  hyperlipidemia: '高脂血症', gout: '痛风',
}

export default function Residents() {
  const [kw, setKw] = useState('')
  const nav = useNavigate()
  const qc = useQueryClient()
  const { message } = App.useApp()
  const role = useAuthStore((s) => s.user?.role)
  const canWrite = role === 'admin' || role === 'nutritionist'

  const { data: options } = useQuery({
    queryKey: ['resident-options'],
    queryFn: async () => (await api.get('/api/residents/options')).data,
  })
  const { data, isLoading } = useQuery({
    queryKey: ['residents', kw],
    queryFn: async () => (await api.get('/api/residents', { params: { kw } })).data,
  })

  const [open, setOpen] = useState(false)
  const [form] = Form.useForm()

  const createMu = useMutation({
    mutationFn: async (v: any) => (await api.post('/api/residents', v)).data,
    onSuccess: (d) => {
      message.success('档案已创建，营养目标已自动计算')
      setOpen(false)
      qc.invalidateQueries({ queryKey: ['residents'] })
      nav(`/residents/${d.id}`)
    },
    onError: (e) => message.error(apiError(e)),
  })

  const onSearch = (v: string) => setKw(v)

  return (
    <div className="page-container">
      <Card title="老人档案" extra={
        <Space>
          <Input.Search placeholder="搜索姓名" allowClear onSearch={onSearch}
                        onChange={(e) => !e.target.value && setKw('')}
                        style={{ width: 200 }} />
          {canWrite && (
            <Button type="primary" icon={<PlusOutlined />}
                    onClick={() => { form.resetFields(); setOpen(true) }}>
              新建档案
            </Button>
          )}
        </Space>
      }>
        <Table rowKey="id" loading={isLoading} dataSource={(data || []) as any[]}
               onRow={(r) => ({ onClick: () => nav(`/residents/${r.id}`),
                                style: { cursor: 'pointer' } })}
               columns={[
                 { title: '姓名', dataIndex: 'name', width: 100,
                   render: (t, r) => (
                     <Space>
                       <Typography.Text strong>{t}</Typography.Text>
                       <Typography.Text type="secondary">
                         {r.gender === 'male' ? '男' : '女'}
                       </Typography.Text>
                     </Space>) },
                 { title: '年龄', dataIndex: 'age', width: 70 },
                 { title: 'BMI', dataIndex: 'bmi', width: 80,
                   render: (v) => v?.toFixed?.(1) ?? '—' },
                 { title: 'TDEE', dataIndex: 'tdee', width: 80,
                   render: (v) => (v ? `${v} kcal` : '—') },
                 { title: '慢病', dataIndex: 'chronic_conditions',
                   render: (cs: string[]) => (
                     <Space wrap>{cs.map((c) =>
                       <Tag color="red" key={c}>{CHRONIC_LABELS[c] || c}</Tag>)}</Space>) },
                 { title: '过敏', dataIndex: 'allergies', width: 130,
                   render: (a: string[]) => a.length
                     ? <Space wrap>{a.map((x) => <Tag color="volcano" key={x}>{x}</Tag>)}</Space>
                     : <Typography.Text type="secondary">无</Typography.Text> },
                 { title: '宗教', dataIndex: 'religion', width: 90,
                   render: (v) => v === 'none'
                     ? <Typography.Text type="secondary">—</Typography.Text>
                     : <Tag color="blue">{v}</Tag> },
                 { title: '吞咽', dataIndex: 'swallowing_level', width: 90,
                   render: (v) => <Tag color={v >= 6 ? 'green' : 'orange'}>IDDSI {v}</Tag> },
                 { title: '操作', width: 90,
                   render: (_, r) => <Link to={`/residents/${r.id}`}
                                          onClick={(e) => e.stopPropagation()}>查看/编辑</Link> },
               ]} />
      </Card>

      <Modal title="新建老人档案" open={open} width={680} destroyOnClose
             okText="创建并计算目标" cancelText="取消"
             onCancel={() => setOpen(false)}
             onOk={() => form.validateFields().then((v) => createMu.mutate(v))}
             confirmLoading={createMu.isPending}>
        <ResidentForm form={form} options={options} />
      </Modal>
    </div>
  )
}

export function ResidentForm({ form, options }: { form: any; options: any }) {
  return (
    <Form form={form} layout="vertical"
          initialValues={{
            gender: 'female', age: 80, height_cm: 158, weight_kg: 55,
            activity_level: 'light', swallowing_level: 7,
            religion: 'none', nutrition_goal_type: 'maintain',
            chronic_conditions: [], allergies: [], dislikes: [], medications: [],
          }}>
      <Space wrap size={16}>
        <Form.Item name="name" label="姓名" rules={[{ required: true }]}>
          <Input style={{ width: 140 }} />
        </Form.Item>
        <Form.Item name="gender" label="性别">
          <Select style={{ width: 90 }} options={[
            { value: 'female', label: '女' }, { value: 'male', label: '男' }]} />
        </Form.Item>
        <Form.Item name="age" label="年龄"><InputNumber min={60} max={120} /></Form.Item>
        <Form.Item name="height_cm" label="身高cm"><InputNumber min={130} max={210} /></Form.Item>
        <Form.Item name="weight_kg" label="体重kg"><InputNumber min={30} max={150} step={0.5} /></Form.Item>
      </Space>
      <Space wrap size={16} align="start">
        <Form.Item name="activity_level" label="活动量">
          <Select style={{ width: 130 }}
                  options={(options?.activity || []).map(([v, l]: any) =>
                    ({ value: v, label: l }))} />
        </Form.Item>
        <Form.Item name="swallowing_level" label="吞咽等级 IDDSI">
          <Select style={{ width: 120 }}
                  options={(options?.iddsi || [0, 1, 2, 3, 4, 5, 6, 7])
                    .map((n: number) => ({ value: n, label: `IDDSI ${n}` }))} />
        </Form.Item>
        <Form.Item name="nutrition_goal_type" label="营养目标">
          <Select style={{ width: 110 }} options={[
            { value: 'maintain', label: '维持' },
            { value: 'lose', label: '减重' },
            { value: 'gain', label: '增重' }]} />
        </Form.Item>
        <Form.Item name="religion" label="宗教禁忌">
          <Select style={{ width: 130 }}
                  options={(options?.religion || []).map(([v, l]: any) =>
                    ({ value: v, label: l }))} />
        </Form.Item>
      </Space>
      <Form.Item name="chronic_conditions" label="慢病（可多选）">
        <Select mode="multiple" allowClear style={{ width: '100%' }}
                options={(options?.chronic || []).map(([v, l]: any) =>
                  ({ value: v, label: l }))} />
      </Form.Item>
      <Form.Item name="allergies" label="过敏原">
        <Select mode="multiple" allowClear style={{ width: '100%' }}
                options={(options?.allergens || []).map(([v, l]: any) =>
                  ({ value: v, label: l }))} />
      </Form.Item>
      <Form.Item name="medications" label="长期用药（食物交互）">
        <Select mode="multiple" allowClear style={{ width: '100%' }}
                options={(options?.medications || []).map(([v, l]: any) =>
                  ({ value: v, label: l }))} />
      </Form.Item>
      <Form.Item name="dislikes" label="忌口（输入标签后回车，如 bitter、fish）">
        <Select mode="tags" style={{ width: '100%' }} placeholder="软约束，不强制" />
      </Form.Item>
      <Form.Item name="note" label="备注">
        <Input.TextArea rows={2} />
      </Form.Item>
    </Form>
  )
}
