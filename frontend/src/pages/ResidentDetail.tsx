import { useEffect, useRef } from 'react'
import {
  Button, Card, Col, Descriptions, Row, Space, Tag, Typography, Modal, Form,
  App, Alert, Table, Progress, Statistic, Divider,
} from 'antd'
import { EditOutlined, ArrowLeftOutlined, PlusOutlined } from '@ant-design/icons'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate, useParams, Link } from 'react-router-dom'
import { api, apiError } from '../api/client'
import { NUTRIENTS, NUT_LABELS } from '../lib/types'
import { RadarChart } from '../components/RadarChart'
import { useAuthStore } from '../store/auth'
import { ResidentForm } from './Residents'

const CHRONIC: Record<string, string> = {
  hypertension: '高血压', diabetes: '糖尿病', ckd: '慢性肾病',
  hyperlipidemia: '高脂血症', gout: '痛风',
}
const SEV: Record<string, any> = { hard: { c: 'red', t: '硬约束' }, soft: { c: 'orange', t: '软约束' } }

export default function ResidentDetail() {
  const { id } = useParams()
  const nav = useNavigate()
  const qc = useQueryClient()
  const { message } = App.useApp()
  const role = useAuthStore((s) => s.user?.role)
  const canWrite = role === 'admin' || role === 'nutritionist'
  const [modal, ctxHolder] = Modal.useModal()
  const editInst = useRef<any>(null)
  const [form] = Form.useForm()

  const { data: r, isLoading } = useQuery({
    queryKey: ['resident', id],
    queryFn: async () => (await api.get(`/api/residents/${id}`)).data,
  })
  const { data: options } = useQuery({
    queryKey: ['resident-options'],
    queryFn: async () => (await api.get('/api/residents/options')).data,
  })

  useEffect(() => {
    if (r) {
      const { applicable_rules, targets, ...rest } = r
      form.setFieldsValue(rest)
    }
  }, [r])

  const updateMu = useMutation({
    mutationFn: async (v: any) =>
      (await api.put(`/api/residents/${id}`, { ...v, version: r.version })).data,
    onSuccess: () => {
      message.success('档案已更新，营养目标已重算')
      editInst.current?.destroy()
      qc.invalidateQueries({ queryKey: ['resident', id] })
    },
    onError: (e) => message.error(apiError(e)),
  })

  if (isLoading || !r) return null
  const t = r.targets?.targets || {}
  const conflicts = r.targets?.conflicts || []
  const assumptions = r.targets?.assumptions || []

  const targetRows = NUTRIENTS.map((n) => {
    const sp = t[n] || {}
    return {
      key: n, nutrient: NUT_LABELS[n],
      min: sp.min ?? '—', target: sp.target ?? '—', max: sp.max ?? '—',
    }
  })

  return (
    <div className="page-container">
      {ctxHolder}
      <Space style={{ marginBottom: 12 }}>
        <Button icon={<ArrowLeftOutlined />} onClick={() => nav('/residents')}>返回</Button>
        <Typography.Title level={4} style={{ margin: 0 }}>{r.name} 的营养档案</Typography.Title>
        {canWrite && (
          <Button type="primary" icon={<EditOutlined />}
                  onClick={() => { editInst.current = modal.info({
                    title: `编辑 ${r.name} 的档案（当前版本 v${r.version}）`,
                    width: 720,
                    content: <ResidentFormWrap form={form} options={options} />,
                    okText: '保存并重算目标',
                    onOk: () => form.validateFields().then((v) => updateMu.mutate(v)),
                    closable: true,
                  }) }}>编辑档案</Button>
        )}
      </Space>

      <Row gutter={16}>
        <Col span={9}>
          <Card title="基本信息">
            <Descriptions column={2} size="small">
              <Descriptions.Item label="性别">{r.gender === 'male' ? '男' : '女'}</Descriptions.Item>
              <Descriptions.Item label="年龄">{r.age} 岁</Descriptions.Item>
              <Descriptions.Item label="身高">{r.height_cm} cm</Descriptions.Item>
              <Descriptions.Item label="体重">{r.weight_kg} kg</Descriptions.Item>
              <Descriptions.Item label="BMI"><Tag color={r.targets?.bmi >= 24 ? 'orange' : 'green'}>{r.targets?.bmi}</Tag></Descriptions.Item>
              <Descriptions.Item label="TDEE">{r.targets?.tdee} kcal</Descriptions.Item>
              <Descriptions.Item label="BMR">{r.targets?.bmr} kcal</Descriptions.Item>
              <Descriptions.Item label="吞咽"><Tag color="orange">IDDSI {r.swallowing_level}</Tag></Descriptions.Item>
              <Descriptions.Item label="活动量" span={2}>{r.activity_level}</Descriptions.Item>
              <Descriptions.Item label="营养目标" span={2}>
                {{ maintain: '维持体重', lose: '减重', gain: '增重' }
                  [r.nutrition_goal_type as 'maintain' | 'lose' | 'gain']}
              </Descriptions.Item>
              <Descriptions.Item label="慢病" span={2}>
                {r.chronic_conditions.length
                  ? <Space wrap>{r.chronic_conditions.map((c: string) =>
                      <Tag color="red" key={c}>{CHRONIC[c] || c}</Tag>)}</Space>
                  : '无'}
              </Descriptions.Item>
              <Descriptions.Item label="过敏" span={2}>
                {r.allergies.length
                  ? <Space wrap>{r.allergies.map((a: string) => <Tag color="volcano" key={a}>{a}</Tag>)}</Space>
                  : '无'}
              </Descriptions.Item>
              <Descriptions.Item label="宗教" span={2}>
                {r.religion === 'none' ? '无' : <Tag color="blue">{r.religion}</Tag>}
              </Descriptions.Item>
              <Descriptions.Item label="用药" span={2}>
                {r.medications.length ? r.medications.join('、') : '无'}
              </Descriptions.Item>
              {r.note && <Descriptions.Item label="备注" span={2}>{r.note}</Descriptions.Item>}
            </Descriptions>
            <Divider />
            <Button type="primary" icon={<PlusOutlined />}
                    onClick={() => nav(`/plans?resident=${r.id}&new=1`)}>
              为 TA 生成配餐方案
            </Button>
          </Card>
        </Col>

        <Col span={15}>
          <Card title="营养目标雷达（目标区间）" extra={
            <Typography.Text type="secondary">多指标个体化计算</Typography.Text>}>
            <RadarChart
              attainment={Object.fromEntries(NUTRIENTS.map((n) => [n, 100]))}
              labels={NUT_LABELS} height={280} />
          </Card>
        </Col>
      </Row>

      <Row gutter={16} style={{ marginTop: 16 }}>
        <Col span={14}>
          <Card title="每日营养目标（区间）">
            <Table size="small" pagination={false} dataSource={targetRows}
                   columns={[
                     { title: '营养素', dataIndex: 'nutrient' },
                     { title: '下限', dataIndex: 'min', align: 'right' },
                     { title: '目标值', dataIndex: 'target', align: 'right',
                       render: (v) => <Typography.Text strong>{v}</Typography.Text> },
                     { title: '上限', dataIndex: 'max', align: 'right' },
                   ]} />
          </Card>
        </Col>
        <Col span={10}>
          <Card title="计算依据" size="small">
            {assumptions.map((a: string, i: number) => (
              <Typography.Paragraph key={i} style={{ marginBottom: 4, fontSize: 12 }}>• {a}</Typography.Paragraph>
            ))}
          </Card>
        </Col>
      </Row>

      {conflicts.length > 0 && (
        <Card title="多病共存冲突与折衷" size="small" style={{ marginTop: 16 }}>
          {conflicts.map((c: any, i: number) => (
            <Alert key={i} type="warning" showIcon style={{ marginBottom: 8 }}
                   message={<span><b>{c.topic}</b>（指标：{c.nutrient}）</span>}
                   description={c.resolution} />
          ))}
        </Card>
      )}

      <Card title="适用禁忌规则（可解释校验）" size="small" style={{ marginTop: 16 }}>
        <Table size="small" pagination={false} rowKey="code"
               dataSource={(r.applicable_rules || []) as any[]}
               columns={[
                 { title: '优先级', dataIndex: 'priority', width: 70 },
                 { title: '规则', render: (_, x) => (
                     <Space direction="vertical" size={0}>
                       <b>{x.name}</b>
                       <span className="rationale-text">{x.rationale}</span>
                     </Space>) },
                 { title: '类型', dataIndex: 'type', width: 90 },
                 { title: '级别', dataIndex: 'severity', width: 90,
                   render: (s) => <Tag color={SEV[s]?.c}>{SEV[s]?.t || s}</Tag> },
                 { title: '版本', dataIndex: 'version', width: 70 },
               ]} />
      </Card>
    </div>
  )
}

// 弹窗内嵌表单（保证 form 上下文可用）
function ResidentFormWrap({ form, options }: { form: any; options: any }) {
  return <div style={{ marginTop: 16, maxHeight: '60vh', overflow: 'auto' }}>
    <ResidentForm form={form} options={options} />
  </div>
}
