import { useParams, useNavigate } from 'react-router-dom'
import {
  Card, Descriptions, Tag, Space, Button, Alert, Collapse, Table, Typography, Spin,
} from 'antd'
import { ArrowLeftOutlined } from '@ant-design/icons'
import { useElder } from '../api/hooks'
import {
  DISEASE_LABELS, IDDSI_LABELS, NUTRIENT_LABELS,
} from '../lib/types'
import { NutrientRadar } from '../components/Charts'

export default function ElderDetailPage() {
  const { id } = useParams()
  const nav = useNavigate()
  const { data: e, isLoading } = useElder(Number(id))
  if (isLoading || !e) return <Spin />
  const t = e.target
  const avgActual: Record<string, number> = {}
  Object.entries(t?.targets || {}).forEach(([k, [lo, hi]]) => {
    avgActual[k] = (lo + hi) / 2  // 雷达展示目标中值自身（目标页无实际摄入）
  })

  return (
    <Space direction="vertical" style={{ width: '100%' }}>
      <Space>
        <Button icon={<ArrowLeftOutlined />} onClick={() => nav('/elders')}>返回</Button>
        <Typography.Title level={4} style={{ margin: 0 }}>{e.name} · 营养目标档案</Typography.Title>
        <Button type="primary" onClick={() => nav(`/plans?elder=${e.id}`)}>发起配餐</Button>
      </Space>

      <Card>
        <Descriptions column={3} bordered size="small">
          <Descriptions.Item label="性别">{e.gender === 'male' ? '男' : '女'}</Descriptions.Item>
          <Descriptions.Item label="出生日期">{e.birth_date}</Descriptions.Item>
          <Descriptions.Item label="身高/体重">{e.height_cm}cm / {e.weight_kg}kg</Descriptions.Item>
          <Descriptions.Item label="活动量">{e.activity_level}</Descriptions.Item>
          <Descriptions.Item label="吞咽等级">{IDDSI_LABELS[e.iddsi_level]}</Descriptions.Item>
          <Descriptions.Item label="日餐费上限">¥{e.cost_limit_day}</Descriptions.Item>
          <Descriptions.Item label="慢病" span={3}>
            {(e.chronic_diseases ? e.chronic_diseases.split(',').filter(Boolean) : [])
              .map((d) => <Tag key={d} color="orange">{DISEASE_LABELS[d] || d}</Tag>)
              || <span style={{ color: '#aaa' }}>无</span>}
          </Descriptions.Item>
          <Descriptions.Item label="过敏原">
            {e.allergies.split(',').filter(Boolean).map((a) =>
              <Tag key={a} color="red">{a}</Tag>) || <span style={{ color: '#aaa' }}>无</span>}
          </Descriptions.Item>
          <Descriptions.Item label="宗教禁忌">{e.religion}</Descriptions.Item>
          <Descriptions.Item label="药物">{e.medications || '无'}</Descriptions.Item>
          <Descriptions.Item label="个人忌口" span={3}>{e.dislikes || '无'}</Descriptions.Item>
        </Descriptions>
      </Card>

      {!!t?.conflict_notes && t.conflict_notes.length > 0 && (
        <Alert type="warning" showIcon message="多病共存冲突调解记录"
          description={<ul style={{ margin: 0, paddingLeft: 18 }}>
            {t.conflict_notes.map((n, i) => <li key={i}>{n}</li>)}
          </ul>} />
      )}

      <Space direction="horizontal" size={16} style={{ width: '100%', alignItems: 'stretch' }}>
        <Card title="核心营养目标雷达（目标中值）" style={{ flex: 1 }}>
          <NutrientRadar actual={avgActual} targets={t?.targets || {}} height={320} />
        </Card>
        <Card title="每日营养目标区间" style={{ flex: 1.2 }}>
          <Table
            size="small" pagination={false} rowKey="0"
            dataSource={Object.entries(t?.targets || {})}
            columns={[
              { title: '营养素', dataIndex: '0',
                render: (v: string) => NUTRIENT_LABELS[v] || v },
              { title: '下限', render: (_: unknown, r: [string, [number, number]]) => r[1][0] },
              { title: '上限', render: (_: unknown, r: [string, [number, number]]) => r[1][1] },
            ]}
          />
        </Card>
      </Space>

      <Card title="目标计算依据（完整可解释链）">
        <Collapse
          defaultActiveKey={['1']}
          items={[{
            key: '1', label: `共 ${t?.explanation?.length || 0} 条计算步骤`,
            children: (
              <ol style={{ paddingLeft: 20 }}>
                {t?.explanation?.map((x, i) => <li key={i} style={{ marginBottom: 4 }}>{x}</li>)}
              </ol>
            ),
          }]}
        />
      </Card>
    </Space>
  )
}
