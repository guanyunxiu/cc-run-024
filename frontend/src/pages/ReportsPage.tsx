import { useState } from 'react'
import { Card, Select, Button, Space, Empty, Table, Tag, App } from 'antd'
import { FileExcelOutlined } from '@ant-design/icons'
import { usePlans } from '../api/hooks'
import { downloadFile } from '../api/client'
import { PlansCompareChart } from '../components/Charts'
import type { Plan } from '../lib/types'

export default function ReportsPage() {
  const { data: plans } = usePlans()
  const [selected, setSelected] = useState<number[]>([])
  const { message } = App.useApp()
  const chosen: Plan[] = (plans || []).filter((p) => selected.includes(p.id))

  const exportCompare = () => {
    if (selected.length < 2) { message.warning('请选择至少 2 个方案'); return }
    downloadFile(`/api/reports/compare/excel?plan_ids=${selected.join(',')}`,
      '方案对比.xlsx')
  }

  return (
    <Space direction="vertical" size={16} style={{ width: '100%' }}>
      <Card title="方案对比报告">
        <Space wrap>
          <span>选择 2~6 个方案：</span>
          <Select
            mode="multiple" allowClear style={{ minWidth: 480 }} maxCount={6}
            value={selected} onChange={setSelected}
            placeholder="按方案标题选择"
            options={(plans || []).map((p) => ({
              value: p.id,
              label: `${p.title}（${p.status} ${p.start_date}）`,
            }))}
          />
          <Button type="primary" icon={<FileExcelOutlined />} onClick={exportCompare}>
            导出对比 Excel
          </Button>
        </Space>
      </Card>

      {chosen.length < 2
        ? <Card><Empty description="选择方案后显示多维对比图" /></Card>
        : (
          <>
            <Card title="关键指标对比">
              <PlansCompareChart plans={chosen.map((p) =>
                ({ title: p.title, metrics: p.metrics || {} }))} />
            </Card>
            <Card title="指标明细表">
              <Table
                size="small" pagination={false} rowKey="id"
                dataSource={chosen.map((p) => ({
                  id: p.id,
                  title: p.title,
                  status: p.status,
                  total: p.metrics?.total_cost,
                  avgDay: p.metrics?.score_breakdown?.avg_day_cost,
                  dev: p.metrics?.score_breakdown?.avg_nutrient_deviation_pct,
                  sat: p.metrics?.score_breakdown?.avg_satisfaction,
                  waste: p.metrics?.score_breakdown?.waste_g_est,
                  distinct: p.metrics?.score_breakdown?.distinct_dishes,
                  risk: p.metrics?.score_breakdown?.risk_tag_hits,
                  seconds: p.metrics?.solve_seconds,
                }))}
                columns={[
                  { title: '方案', dataIndex: 'title' },
                  { title: '状态', dataIndex: 'status', width: 90,
                    render: (v: string) => <Tag>{v}</Tag> },
                  { title: '总成本', dataIndex: 'total', width: 90 },
                  { title: '日均成本', dataIndex: 'avgDay', width: 90 },
                  { title: '营养偏差%', dataIndex: 'dev', width: 100 },
                  { title: '满意度', dataIndex: 'sat', width: 80 },
                  { title: '浪费g', dataIndex: 'waste', width: 80 },
                  { title: '菜品数', dataIndex: 'distinct', width: 80 },
                  { title: '风险命中', dataIndex: 'risk', width: 90 },
                  { title: '求解秒', dataIndex: 'seconds', width: 90 },
                ]}
              />
            </Card>
          </>
        )}

      <Card title="单方案报告导出">
        <Space wrap>
          {(plans || []).slice(0, 12).map((p) => (
            <Space key={p.id} style={{ border: '1px solid #e4e9f0', borderRadius: 8,
              padding: '6px 10px', marginBottom: 6 }}>
              <span>{p.title}</span>
              <Button size="small" onClick={() =>
                downloadFile(`/api/reports/plans/${p.id}/pdf`, `方案${p.id}.pdf`)}>PDF</Button>
              <Button size="small" onClick={() =>
                downloadFile(`/api/reports/plans/${p.id}/excel`, `方案${p.id}.xlsx`)}>
                Excel</Button>
            </Space>
          ))}
        </Space>
      </Card>
    </Space>
  )
}
