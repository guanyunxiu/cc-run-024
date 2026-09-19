import { Button, Card, Col, Row, Space, Statistic, Table, Tag, Typography, App } from 'antd'
import {
  ArrowLeftOutlined, FilePdfOutlined, FileExcelOutlined, ShoppingOutlined,
} from '@ant-design/icons'
import ReactECharts from 'echarts-for-react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate, useParams } from 'react-router-dom'
import { api } from '../api/client'
import { RadarChart } from '../components/RadarChart'
import { NUT_LABELS, SLOT_LABELS } from '../lib/types'

export default function Report() {
  const { id } = useParams()
  const planId = Number(id)
  const nav = useNavigate()
  const { message } = App.useApp()

  const { data } = useQuery({
    queryKey: ['report', planId],
    queryFn: async () => (await api.get(`/api/reports/plan/${planId}`)).data,
  })
  const { data: proc } = useQuery({
    queryKey: ['procurement', planId],
    queryFn: async () => (await api.get(`/api/reports/plan/${planId}/procurement`)).data,
  })

  const download = async (suffix: string, mime: string, filename: string) => {
    try {
      const resp = await api.get(`/api/reports/plan/${planId}/${suffix}`,
                                 { responseType: 'blob' })
      const url = URL.createObjectURL(new Blob([resp.data], { type: mime }))
      const a = document.createElement('a')
      a.href = url; a.download = filename; a.click()
      URL.revokeObjectURL(url)
    } catch { message.error('导出失败') }
  }

  if (!data) return <div className="page-container"><Card loading /></div>

  const meta = data.report_meta
  const score = meta.score || {}
  const trend = data.trend || []

  const trendOption = {
    tooltip: { trigger: 'axis' },
    legend: { data: ['能量(kcal)', '蛋白质(g)', '钠(mg)', '成本(元)'], top: 0 },
    grid: { left: 50, right: 60, top: 40, bottom: 30 },
    xAxis: { type: 'category', data: trend.map((t: any) => t.date.slice(5)) },
    yAxis: [
      { type: 'value', name: '营养' },
      { type: 'value', name: '成本', position: 'right' },
    ],
    series: [
      { name: '能量(kcal)', type: 'line', smooth: true,
        data: trend.map((t: any) => t.energy_kcal),
        itemStyle: { color: '#2f5496' } },
      { name: '蛋白质(g)', type: 'line', smooth: true,
        data: trend.map((t: any) => t.protein_g),
        itemStyle: { color: '#52c41a' } },
      { name: '钠(mg)', type: 'bar',
        data: trend.map((t: any) => t.sodium_mg),
        itemStyle: { color: '#ffccc7' } },
      { name: '成本(元)', type: 'line', yAxisIndex: 1, smooth: true,
        data: trend.map((t: any) => t.cost), lineStyle: { type: 'dashed' },
        itemStyle: { color: '#fa8c16' } },
    ],
  }

  // 达标率柱状
  const barOption = {
    tooltip: {},
    grid: { left: 90, right: 30, top: 20, bottom: 30 },
    xAxis: { type: 'value', max: 100 },
    yAxis: { type: 'category',
      data: Object.keys(data.nut_labels).map((k) => data.nut_labels[k]) },
    series: [{
      type: 'bar',
      data: Object.keys(data.nut_labels).map((k) => ({
        value: score.attainment?.[k]?.toFixed(1) ?? 0,
        itemStyle: { color: (score.attainment?.[k] ?? 0) >= 85 ? '#52c41a'
          : (score.attainment?.[k] ?? 0) >= 60 ? '#faad14' : '#f5222d' },
      })),
      label: { show: true, position: 'right', formatter: '{c}%' },
    }],
  }

  return (
    <div className="page-container">
      <Space style={{ marginBottom: 12 }}>
        <Button icon={<ArrowLeftOutlined />} onClick={() => nav(`/plans/${planId}`)}>
          返回排餐</Button>
        <Typography.Title level={4} style={{ margin: 0 }}>
          营养分析报告 — {meta.resident}</Typography.Title>
        <Button icon={<FilePdfOutlined />} type="primary"
                onClick={() => download('pdf', 'application/pdf', `mealplan_${planId}.pdf`)}>
          导出 PDF</Button>
        <Button icon={<FileExcelOutlined />}
                onClick={() => download('excel',
          'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
          `mealplan_${planId}.xlsx`)}>导出 Excel</Button>
      </Space>

      <Row gutter={16}>
        {[
          ['平均营养达标率', `${score.avg_attainment_pct ?? '—'}%`],
          ['日均成本', `¥${score.avg_cost_per_day ?? '—'}`],
          ['平均满意度', score.avg_satisfaction ?? '—'],
          ['菜品丰富度', score.distinct_dishes ?? '—'],
          ['软约束提示', score.soft_violation_count ?? 0],
          ['预计浪费金额', `¥${score.estimated_waste_cost ?? '—'}`],
        ].map(([t, v]) => (
          <Col span={4} key={t as string}>
            <Card size="small" style={{ marginBottom: 16 }}>
              <Statistic title={t as string} value={v as any} />
            </Card>
          </Col>
        ))}
      </Row>

      <Row gutter={16}>
        <Col span={10}>
          <Card title="营养达标雷达（%）">
            <RadarChart attainment={score.attainment} labels={data.nut_labels}
                        height={340} />
          </Card>
        </Col>
        <Col span={14}>
          <Card title="各营养素达标率">
            <ReactECharts option={barOption} style={{ height: 340 }} />
          </Card>
        </Col>
      </Row>

      <Card title="每日营养与成本趋势" style={{ marginTop: 16 }}>
        <ReactECharts option={trendOption} style={{ height: 320 }} />
      </Card>

      <Row gutter={16} style={{ marginTop: 16 }}>
        <Col span={12}>
          <Card title="目标计算依据" size="small">
            {meta.assumptions?.map((a: string, i: number) => (
              <Typography.Paragraph key={i} style={{ marginBottom: 4, fontSize: 12 }}>
                • {a}</Typography.Paragraph>
            ))}
            {meta.conflicts_calc?.length > 0 && (
              <>
                <Typography.Text strong type="warning">多病共存冲突与折衷：</Typography.Text>
                {meta.conflicts_calc.map((c: any, i: number) => (
                  <div key={i} style={{ fontSize: 12, marginTop: 4 }}>
                    <Tag color="orange">{c.nutrient}</Tag>
                    <b>{c.topic}</b>
                    <div style={{ color: '#666' }}>折衷：{c.resolution}</div>
                  </div>
                ))}
              </>
            )}
          </Card>
        </Col>
        <Col span={12}>
          <Card title="软约束提示与求解器告警" size="small">
            {meta.soft_violations?.slice(0, 12).map((v: any, i: number) => (
              <div key={i} style={{ fontSize: 12, marginBottom: 4 }}>
                <Tag color="orange">软</Tag>
                第{v.day_index + 1}天{SLOT_LABELS[v.slot]}《{v.dish_name}》：{v.message}
                <div style={{ color: '#999' }}>依据：{v.rationale}</div>
              </div>
            ))}
            {(!meta.soft_violations || meta.soft_violations.length === 0) &&
              <Typography.Text type="secondary">无软约束提示</Typography.Text>}
            {meta.warnings?.length > 0 && (
              <Alert warnings={meta.warnings} />
            )}
            <Typography.Paragraph type="secondary" style={{ fontSize: 11, marginTop: 8 }}>
              规则版本：{meta.rule_version} ｜ 求解器参数：
              {JSON.stringify(meta.solver_params)} ｜ 状态：{score.status}
              ｜ 用时 {score.solve_time_sec}s
            </Typography.Paragraph>
          </Card>
        </Col>
      </Row>

      <Card title={<Space><ShoppingOutlined />采购需求汇总清单</Space>}
            size="small" style={{ marginTop: 16 }}
            extra={<Typography.Text type="secondary">
              仅汇总整个周期的食材需求，不涉及仓库库存扣减
            </Typography.Text>}>
        <Table size="small" pagination={false} rowKey="ingredient_id"
               dataSource={proc?.rows || []}
               summary={() => (
                 <Table.Summary.Row>
                   <Table.Summary.Cell index={0}>
                     <b>合计（{proc?.days} 天）</b>
                   </Table.Summary.Cell>
                   {Array.from({ length: 5 }).map((_, i) =>
                     <Table.Summary.Cell index={i + 1} key={i} />)}
                   <Table.Summary.Cell index={6}>
                     <b>¥{proc?.total_cost}</b>
                   </Table.Summary.Cell>
                 </Table.Summary.Row>
               )}
               columns={[
                 { title: '分类', dataIndex: 'category', width: 90 },
                 { title: '食材', dataIndex: 'name' },
                 { title: '需求毛重(kg)', dataIndex: 'gross_kg', align: 'right' },
                 { title: '可食部%', dataIndex: 'edible_pct', align: 'right' },
                 { title: '可食量(kg)', dataIndex: 'edible_weight_kg', align: 'right' },
                 { title: '单价(元/kg)', dataIndex: 'unit_cost', align: 'right' },
                 { title: '预估金额(元)', dataIndex: 'cost', align: 'right' },
               ]} />
      </Card>
    </div>
  )
}

function Alert({ warnings }: { warnings: string[] }) {
  return <div style={{ marginTop: 8 }}>
    {warnings.map((w, i) => (
      <Tag key={i} color="red" style={{ marginBottom: 4 }}>求解告警：{w}</Tag>
    ))}
  </div>
}
