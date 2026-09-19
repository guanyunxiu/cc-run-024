import { useEffect, useMemo, useState } from 'react'
import {
  Button, Card, DatePicker, Form, InputNumber, Modal, Select, Space, Table,
  Tag, Typography, App, Tabs, Progress, Alert,
} from 'antd'
import { PlusOutlined } from '@ant-design/icons'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import dayjs from 'dayjs'
import FullCalendar from '@fullcalendar/react'
import dayGridPlugin from '@fullcalendar/daygrid'
import interactionPlugin from '@fullcalendar/interaction'
import '@fullcalendar/core/locales/zh-cn'
import { api, apiError } from '../api/client'
import { useAuthStore } from '../store/auth'

const STATUS: Record<string, { color: string; text: string; fc: string }> = {
  draft: { color: 'default', text: '草稿', fc: '#8c8c8c' },
  published: { color: 'green', text: '已发布', fc: '#52c41a' },
  archived: { color: 'orange', text: '已归档', fc: '#fa8c16' },
}

export default function Plans() {
  const [searchParams] = useSearchParams()
  const [open, setOpen] = useState(false)
  const [form] = Form.useForm()
  const nav = useNavigate()
  const qc = useQueryClient()
  const { message } = App.useApp()
  const role = useAuthStore((s) => s.user?.role)
  const canWrite = role === 'admin' || role === 'nutritionist'

  const { data: residents } = useQuery({
    queryKey: ['residents'],
    queryFn: async () => (await api.get('/api/residents')).data,
  })
  const { data: plans, isLoading } = useQuery({
    queryKey: ['plans'],
    queryFn: async () => (await api.get('/api/plans')).data,
  })

  useEffect(() => {
    if (searchParams.get('new') && residents) {
      form.setFieldsValue({
        resident_id: Number(searchParams.get('resident')) || residents[0]?.id,
        days: 7, budget_per_day: 40, start_date: dayjs(),
      })
      setOpen(true)
    }
  }, [searchParams, residents])

  const createMu = useMutation({
    mutationFn: async (v: any) => (await api.post('/api/plans', {
      ...v, start_date: v.start_date.format('YYYY-MM-DD'),
    })).data,
    onSuccess: (d) => {
      message.success('方案已创建，求解任务已提交，正在自动配餐…')
      setOpen(false)
      qc.invalidateQueries({ queryKey: ['plans'] })
      // 进入编辑器并轮询任务
      nav(`/plans/${d.plan_id}?task=${d.task_id}`)
    },
    onError: (e) => message.error(apiError(e)),
  })

  const events = useMemo(() => (plans || []).flatMap((p: any) => {
    const resName = residents?.find((r: any) => r.id === p.resident_id)?.name
    return Array.from({ length: p.days }, (_, i) => ({
      title: `${resName} · ${p.days}天${p.status === 'published' ? '✅' : ''}`,
      date: dayjs(p.start_date).add(i, 'day').format('YYYY-MM-DD'),
      backgroundColor: STATUS[p.status]?.fc || '#1677ff',
      extendedProps: { planId: p.id },
    }))
  }), [plans, residents])

  return (
    <div className="page-container">
      <Card title="排餐方案" extra={canWrite && (
        <Button type="primary" icon={<PlusOutlined />}
                onClick={() => {
                  form.setFieldsValue({
                    resident_id: residents?.[0]?.id, days: 7,
                    budget_per_day: 40, start_date: dayjs(),
                  })
                  setOpen(true)
                }}>
          新建配餐（自动求解）
        </Button>
      )}>
        <Tabs items={[
          {
            key: 'table', label: '方案列表',
            children: (
              <Table rowKey="id" loading={isLoading} dataSource={(plans || []) as any[]}
                     onRow={(r) => ({
                       onClick: () => nav(`/plans/${r.id}`),
                       style: { cursor: 'pointer' },
                     })}
                     columns={[
                       { title: 'ID', dataIndex: 'id', width: 60 },
                       { title: '方案名称', dataIndex: 'name' },
                       { title: '老人', dataIndex: 'resident_name', width: 100 },
                       { title: '开始日期', dataIndex: 'start_date', width: 110 },
                       { title: '天数', dataIndex: 'days', width: 60 },
                       { title: '日预算', dataIndex: 'budget_per_day', width: 80,
                         render: (v) => `¥${v}` },
                       { title: '日均成本', width: 90,
                         render: (_, r) => r.score
                           ? `¥${r.score.avg_cost_per_day}` : '—' },
                       { title: '营养达标', width: 100,
                         render: (_, r) => r.score
                           ? <Progress percent={Math.round(r.score.avg_attainment_pct)}
                                       size="small" /> : '—' },
                       { title: '满意度', width: 80,
                         render: (_, r) => r.score?.avg_satisfaction ?? '—' },
                       { title: '版本', dataIndex: 'version', width: 60 },
                       { title: '状态', dataIndex: 'status', width: 90,
                         render: (s) => <Tag color={STATUS[s]?.color}>
                           {STATUS[s]?.text}</Tag> },
                       { title: '操作', width: 120,
                         render: (_, r) => (
                           <Space onClick={(e) => e.stopPropagation()}>
                             <Link to={`/plans/${r.id}`}>排餐</Link>
                             <Link to={`/plans/${r.id}/report`}>报告</Link>
                           </Space>) },
                     ]} />
            ),
          },
          {
            key: 'calendar', label: '排餐日历',
            children: (
              <FullCalendar
                plugins={[dayGridPlugin, interactionPlugin]}
                initialView="dayGridMonth"
                height="auto"
                locale="zh-cn"
                events={events}
                eventClick={(info) => nav(`/plans/${info.event.extendedProps.planId}`)}
                eventDisplay="block"
              />
            ),
          },
        ]} />
      </Card>

      <Modal title="新建配餐方案" open={open} onCancel={() => setOpen(false)}
             okText="提交并自动求解"
             confirmLoading={createMu.isPending}
             onOk={() => form.validateFields().then((v) => createMu.mutate(v))}>
        <Alert type="info" showIcon style={{ marginBottom: 12 }}
               message="提交后 CP-SAT 求解器在后台运行（通常 10–30 秒），可在排餐页查看进度。" />
        <Form form={form} layout="vertical">
          <Form.Item name="resident_id" label="选择老人" rules={[{ required: true }]}>
            <Select showSearch optionFilterProp="label"
                    options={(residents || []).map((r: any) => ({
                      value: r.id,
                      label: `${r.name}（${r.age}岁 · IDDSI ${r.swallowing_level}）`,
                    }))} />
          </Form.Item>
          <Space>
            <Form.Item name="start_date" label="开始日期" rules={[{ required: true }]}>
              <DatePicker />
            </Form.Item>
            <Form.Item name="days" label="天数" rules={[{ required: true }]}>
              <Select style={{ width: 110 }} options={[
                { value: 1, label: '单日食谱' },
                { value: 7, label: '一周食谱' }]} />
            </Form.Item>
            <Form.Item name="budget_per_day" label="每日成本上限(元)"
                       rules={[{ required: true }]}>
              <InputNumber min={5} max={500} step={5} />
            </Form.Item>
          </Space>
        </Form>
      </Modal>
    </div>
  )
}
