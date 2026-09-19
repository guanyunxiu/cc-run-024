import { useState } from 'react'
import {
  Card, Table, Tag, Button, Space, Modal, Form, Select, DatePicker, InputNumber,
  Input, App, Progress, Alert,
} from 'antd'
import { PlusOutlined } from '@ant-design/icons'
import { useNavigate, useSearchParams } from 'react-router-dom'
import dayjs from 'dayjs'
import {
  usePlans, useElders, useSolve, useTask,
} from '../api/hooks'
import type { Plan } from '../lib/types'

function SolveModal({ onClose, presetElder }:
  { onClose: () => void; presetElder?: number }) {
  const [form] = Form.useForm()
  const solve = useSolve()
  const { data: elders } = useElders()
  const { message } = App.useApp()
  const nav = useNavigate()
  const [taskId, setTaskId] = useState<number | null>(null)
  const { data: task } = useTask(taskId, {
    refetchInterval: taskId ? 1000 : false,
  })

  const onOk = async () => {
    const v = await form.validateFields()
    solve.mutate({
      elder_id: v.elder_id,
      period_type: v.days > 1 ? 'week' : 'day',
      start_date: v.start_date.format('YYYY-MM-DD'),
      days: v.days,
      title: v.title || '',
      cost_limit_day: v.cost_limit_day ?? undefined,
      time_limit_seconds: v.time_limit_seconds,
      weights: v.custom_weights
        ? { nutrition: v.w_nutrition, cost: v.w_cost, satisfaction: v.w_sat,
            waste: v.w_waste, repeat: v.w_repeat, risk_tag: v.w_risk }
        : undefined,
    }, {
      onSuccess: (d) => setTaskId(d.task_id),
      onError: (e: unknown) => message.error(
        (e as { response?: { data?: { detail?: string } } }).response?.data?.detail || '提交失败'),
    })
  }

  return (
    <Modal open title="发起自动配餐求解" onCancel={onClose}
      width={620}
      footer={taskId ? [
        <Button key="c" onClick={onClose}>关闭</Button>,
        <Button key="o" type="primary" disabled={task?.status !== 'success'}
          onClick={() => nav(`/plans/${task?.result.plan_id}`)}>
          打开方案
        </Button>,
      ] : undefined}
      onOk={taskId ? undefined : onOk}
      confirmLoading={solve.isPending} okText="开始求解">
      <Form form={form} layout="vertical" initialValues={{
        elder_id: presetElder, days: 1,
        start_date: dayjs('2026-09-21'), time_limit_seconds: 20,
        custom_weights: false, w_nutrition: 1000, w_cost: 25, w_sat: 40,
        w_waste: 60, w_repeat: 90, w_risk: 150,
      }}>
        <Form.Item name="elder_id" label="选择老人" rules={[{ required: true }]}>
          <Select
            showSearch optionFilterProp="label"
            placeholder="选择老人"
            options={(elders || []).map((e) => ({
              value: e.id,
              label: `${e.name}（${e.chronic_diseases || '无慢病'} / IDDSI ${e.iddsi_level} / 上限¥${e.cost_limit_day}）`,
            }))}
          />
        </Form.Item>
        <Space>
          <Form.Item name="start_date" label="开始日期" rules={[{ required: true }]}>
            <DatePicker />
          </Form.Item>
          <Form.Item name="days" label="天数（1=日方案，7=周方案）">
            <InputNumber min={1} max={7} />
          </Form.Item>
          <Form.Item name="cost_limit_day" label="临时日成本上限（空=档案值）">
            <InputNumber min={5} max={300} addonAfter="元" />
          </Form.Item>
          <Form.Item name="time_limit_seconds" label="求解时限">
            <InputNumber min={5} max={60} addonAfter="秒" />
          </Form.Item>
        </Space>
        <Form.Item name="title" label="方案标题（可选）">
          <Input placeholder="留空自动生成" />
        </Form.Item>
        <Form.Item name="custom_weights" label="自定义多目标权重">
          <Select style={{ width: 200 }} options={[
            { value: false, label: '使用默认权重' }, { value: true, label: '自定义权重' }]} />
        </Form.Item>
        <Form.Item noStyle shouldUpdate={(a, b) => a.custom_weights !== b.custom_weights}>
          {() => (form.getFieldValue('custom_weights') ? (
            <Space wrap>
              <Form.Item name="w_nutrition" label="营养偏差"><InputNumber /></Form.Item>
              <Form.Item name="w_cost" label="成本"><InputNumber /></Form.Item>
              <Form.Item name="w_sat" label="满意度"><InputNumber /></Form.Item>
              <Form.Item name="w_waste" label="浪费"><InputNumber /></Form.Item>
              <Form.Item name="w_repeat" label="重复"><InputNumber /></Form.Item>
              <Form.Item name="w_risk" label="慢病风险"><InputNumber /></Form.Item>
            </Space>
          ) : null)}
        </Form.Item>
      </Form>
      {taskId && task && (
        <div style={{ marginTop: 8 }}>
          <Progress percent={task.progress} status={
            task.status === 'failed' ? 'exception'
              : task.status === 'success' ? 'success' : 'active'} />
          <Tag color={task.status === 'success' ? 'green'
            : task.status === 'failed' ? 'red' : 'blue'}>{task.status}</Tag>
          <span>{task.message || '求解中，请稍候…'}</span>
          {task.status === 'failed' && (
            <Alert style={{ marginTop: 8 }} type="error" showIcon
              message="未求得可行方案"
              description={<div>
                <div>{task.message}</div>
                {task.result?.warnings?.map((w, i) => <div key={i}>• {w}</div>)}
                {task.result?.relaxations?.map((w, i) => <div key={`r${i}`}>• {w}</div>)}
              </div>} />
          )}
        </div>
      )}
    </Modal>
  )
}

export default function PlansPage() {
  const nav = useNavigate()
  const [params] = useSearchParams()
  const presetElder = params.get('elder') ? Number(params.get('elder')) : undefined
  const { data, isLoading } = usePlans(presetElder)
  const [open, setOpen] = useState(false)

  const columns = [
    { title: '方案', dataIndex: 'title',
      render: (v: string, r: Plan) => <a onClick={() => nav(`/plans/${r.id}`)}>{v}</a> },
    { title: '老人', dataIndex: 'elder_name', width: 100 },
    { title: '周期', width: 180,
      render: (_: unknown, r: Plan) =>
        `${r.period_type === 'week' ? '周' : '日'} ${r.start_date} ~ ${r.end_date || r.start_date}` },
    { title: '状态', dataIndex: 'status', width: 90,
      render: (v: string) => <Tag color={v === 'published' ? 'green'
        : v === 'archived' ? 'default' : 'gold'}>
        {v === 'published' ? '已发布' : v === 'archived' ? '已归档' : '草稿'}</Tag> },
    { title: '规则版本', dataIndex: 'rule_version', width: 110 },
    { title: '总成本', width: 90,
      render: (_: unknown, r: Plan) => `¥${r.metrics?.total_cost ?? '-'}` },
    { title: '日均成本', width: 90,
      render: (_: unknown, r: Plan) => r.metrics?.score_breakdown?.avg_day_cost
        ? `¥${r.metrics.score_breakdown.avg_day_cost}` : '-' },
    { title: '营养偏差', width: 90,
      render: (_: unknown, r: Plan) =>
        r.metrics?.score_breakdown?.avg_nutrient_deviation_pct != null
          ? `${r.metrics.score_breakdown.avg_nutrient_deviation_pct}%` : '-' },
    { title: '满意度', width: 80,
      render: (_: unknown, r: Plan) =>
        r.metrics?.score_breakdown?.avg_satisfaction ?? '-' },
    { title: '创建人', dataIndex: 'created_by', width: 100 },
    { title: '创建时间', dataIndex: 'created_at', width: 170,
      render: (v: string) => dayjs(v).format('YYYY-MM-DD HH:mm') },
  ]

  return (
    <Card title={presetElder ? '该老人的配餐方案' : '全部配餐方案'}
      extra={<Button type="primary" icon={<PlusOutlined />}
        onClick={() => setOpen(true)}>发起求解</Button>}>
      <Table rowKey="id" loading={isLoading} dataSource={data || []}
        columns={columns} pagination={{ pageSize: 15 }} />
      {open && <SolveModal presetElder={presetElder} onClose={() => setOpen(false)} />}
    </Card>
  )
}
