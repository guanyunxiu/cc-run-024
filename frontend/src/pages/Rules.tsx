import { useState } from 'react'
import {
  Button, Card, Form, Input, InputNumber, Modal, Select, Space, Table, Tag,
  Typography, App, Alert, Tooltip,
} from 'antd'
import { PlusOutlined, DeleteOutlined } from '@ant-design/icons'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, apiError } from '../api/client'
import { useAuthStore } from '../store/auth'

const TYPE_LABELS: Record<string, string> = {
  allergen: '过敏原', chronic: '慢病禁忌', medication: '药物交互',
  iddsi: '吞咽 IDDSI', religion: '宗教禁忌',
}

export default function Rules() {
  const [open, setOpen] = useState(false)
  const [editing, setEditing] = useState<any>(null)
  const [paramsText, setParamsText] = useState('{}')
  const [parseErr, setParseErr] = useState('')
  const [form] = Form.useForm()
  const qc = useQueryClient()
  const { message, modal } = App.useApp()
  const role = useAuthStore((s) => s.user?.role)
  const canWrite = role === 'admin' || role === 'nutritionist'

  const { data: types } = useQuery({
    queryKey: ['rule-types'],
    queryFn: async () => (await api.get('/api/rules/types')).data,
  })
  const { data, isLoading } = useQuery({
    queryKey: ['rules'],
    queryFn: async () => (await api.get('/api/rules')).data,
  })

  const saveMu = useMutation({
    mutationFn: async (v: any) =>
      editing ? api.put(`/api/rules/${editing.id}`, v)
              : api.post('/api/rules', v),
    onSuccess: () => {
      message.success('规则已保存')
      setOpen(false)
      qc.invalidateQueries({ queryKey: ['rules'] })
    },
    onError: (e) => message.error(apiError(e)),
  })
  const delMu = useMutation({
    mutationFn: async (id: number) => (await api.delete(`/api/rules/${id}`)).data,
    onSuccess: () => {
      message.success('规则已删除')
      qc.invalidateQueries({ queryKey: ['rules'] })
    },
    onError: (e) => message.error(apiError(e)),
  })

  const openEditor = (r: any | null) => {
    setEditing(r)
    if (r) {
      form.setFieldsValue({ ...r })
      setParamsText(JSON.stringify(r.params || {}, null, 2))
    } else {
      form.resetFields()
      form.setFieldsValue({
        rule_type: 'chronic', severity: 'hard', priority: 100,
        version: '1.0.0', active: true,
      })
      setParamsText('{\n  "condition": "hypertension",\n  "match": { "tags_any": ["pickle"] }\n}')
    }
    setParseErr('')
    setOpen(true)
  }

  const onOk = async () => {
    const v = await form.validateFields()
    let params: any
    try {
      params = JSON.parse(paramsText)
    } catch {
      setParseErr('JSON 格式错误，请检查')
      return
    }
    saveMu.mutate({ ...v, params })
  }

  return (
    <div className="page-container">
      <Card title="禁忌规则表（JSON 规则 + Python 校验函数）" extra={canWrite && (
        <Button type="primary" icon={<PlusOutlined />} onClick={() => openEditor(null)}>
          新建规则
        </Button>
      )}>
        <Alert type="info" showIcon style={{ marginBottom: 12 }}
               message="规则按类型（过敏原/慢病/药物交互/IDDSI/宗教）由后端 Python 校验函数分派；"
               description="硬约束(hard)不满足则菜品从求解候选中剔除；软约束(soft)进入目标函数尽量规避并在报告中给出可解释提示。优先级数字越小越优先。" />
        <Table rowKey="id" loading={isLoading} dataSource={(data || []) as any[]}
               scroll={{ x: 900 }}
               columns={[
                 { title: '优先级', dataIndex: 'priority', width: 70 },
                 { title: '编码', dataIndex: 'code', width: 140 },
                 { title: '规则名称',
                   render: (_, r) => (
                     <Space direction="vertical" size={0}>
                       <b>{r.name}</b>
                       <Tooltip title={r.rationale}>
                         <Typography.Text type="secondary"
                           ellipsis style={{ maxWidth: 420, fontSize: 12 }}>
                           {r.rationale}
                         </Typography.Text>
                       </Tooltip>
                     </Space>) },
                 { title: '类型', dataIndex: 'rule_type', width: 100,
                   render: (t) => <Tag color="blue">{TYPE_LABELS[t] || t}</Tag> },
                 { title: '级别', dataIndex: 'severity', width: 90,
                   render: (s) => <Tag color={s === 'hard' ? 'red' : 'orange'}>
                     {s === 'hard' ? '硬约束' : '软约束'}</Tag> },
                 { title: '版本', dataIndex: 'version', width: 70 },
                 { title: '启用', dataIndex: 'active', width: 70,
                   render: (a) => a ? <Tag color="green">是</Tag> : <Tag>否</Tag> },
                 { title: '操作', width: 110,
                   render: (_, r) => (
                     <Space>
                       {canWrite && <Typography.Link onClick={() => openEditor(r)}>编辑</Typography.Link>}
                       {role === 'admin' && (
                         <Typography.Link type="danger"
                           onClick={() => modal.confirm({
                             title: `删除规则 ${r.code}？`,
                             onOk: () => delMu.mutate(r.id),
                           })}><DeleteOutlined /></Typography.Link>)}
                     </Space>) },
               ]} />
      </Card>

      <Modal title={editing ? `编辑规则 ${editing.code}` : '新建规则'}
             open={open} width={720} onCancel={() => setOpen(false)}
             onOk={onOk} confirmLoading={saveMu.isPending} okText="保存">
        <Form form={form} layout="vertical">
          <Space>
            <Form.Item name="code" label="规则编码" rules={[{ required: true }]}>
              <Input style={{ width: 180 }} placeholder="如 HTN-003" />
            </Form.Item>
            <Form.Item name="name" label="名称">
              <Input style={{ width: 220 }} />
            </Form.Item>
          </Space>
          <Space>
            <Form.Item name="rule_type" label="类型">
              <Select style={{ width: 150 }}
                      options={(types?.types || Object.entries(TYPE_LABELS))
                        .map(([v, l]: any) => ({ value: v, label: l }))} />
            </Form.Item>
            <Form.Item name="severity" label="严重级别">
              <Select style={{ width: 120 }} options={[
                { value: 'hard', label: '硬约束' },
                { value: 'soft', label: '软约束' }]} />
            </Form.Item>
            <Form.Item name="priority" label="优先级">
              <InputNumber min={1} max={9999} />
            </Form.Item>
            <Form.Item name="version" label="版本号">
              <Input style={{ width: 100 }} placeholder="1.0.0" />
            </Form.Item>
            <Form.Item name="active" label="启用">
              <Select style={{ width: 80 }} options={[
                { value: true, label: '是' }, { value: false, label: '否' }]} />
            </Form.Item>
          </Space>
          <Form.Item label="规则参数（JSON）">
            <Input.TextArea rows={8} value={paramsText} onChange={(e) => {
              setParamsText(e.target.value)
              setParseErr('')
            }} style={{ fontFamily: 'monospace', fontSize: 12 }} />
          </Form.Item>
          {parseErr && <Alert type="error" message={parseErr} style={{ marginBottom: 8 }} />}
          <Typography.Paragraph type="secondary" style={{ fontSize: 12 }}>
            参数示例：慢病标签 <code>{'{"condition":"hypertension","match":{"tags_any":["pickle"]}}'}</code>
            ；单菜营养上限 <code>{'{"condition":"ckd","nutrient_max":{"potassium_mg":600}}'}</code>；
            药物交互 <code>{'{"medication":"warfarin","match":{"tags_any":["high_vitamin_k"]}}'}</code>
          </Typography.Paragraph>
          <Form.Item name="rationale" label="临床依据（解释文本）">
            <Input.TextArea rows={2} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
