import ReactECharts from 'echarts-for-react'

const RADAR_KEYS = [
  ['energy_kcal', '能量'],
  ['protein_g', '蛋白质'],
  ['dietary_fiber_g', '纤维'],
  ['calcium_mg', '钙'],
  ['potassium_mg', '钾'],
  ['phosphorus_mg', '磷'],
] as const

/** 营养雷达：实际均值 / 目标中值（100% 即正好达标）。 */
export function NutrientRadar({
  actual,
  targets,
  height = 300,
}: {
  actual: Record<string, number>
  targets: Record<string, [number, number]>
  height?: number
}) {
  const indicator = RADAR_KEYS.map(([k, name]) => {
    const t = targets[k]
    const max = t ? t[1] * 1.4 : Math.max(actual[k] ?? 0, 1) * 1.4
    return { name, max: Number(max.toFixed(0)) }
  })
  const value = RADAR_KEYS.map(([k]) => Number((actual[k] ?? 0).toFixed(1)))
  const targetMid = RADAR_KEYS.map(([k]) =>
    targets[k] ? (targets[k][0] + targets[k][1]) / 2 : 0)
  const option = {
    tooltip: {},
    legend: { bottom: 0, data: ['实际摄入', '目标中值'] },
    radar: {
      indicator, radius: '62%',
      axisName: { color: '#444', fontSize: 12 },
      splitArea: { areaStyle: { color: ['#fafcff', '#f0f6fc'] } },
    },
    series: [
      {
        type: 'radar',
        data: [
          {
            value, name: '实际摄入', areaStyle: { color: 'rgba(47,111,176,0.28)' },
            lineStyle: { color: '#2f6fb0' }, itemStyle: { color: '#2f6fb0' },
          },
          {
            value: targetMid, name: '目标中值', areaStyle: { color: 'rgba(230,162,60,0.12)' },
            lineStyle: { color: '#e6a23c', type: 'dashed' }, itemStyle: { color: '#e6a23c' },
          },
        ],
      },
    ],
  }
  return <ReactECharts option={option} style={{ height }} />
}

/** 多营养素 实际 vs 目标区间 柱状。 */
export function NutrientBars({
  actual,
  targets,
  height = 280,
}: {
  actual: Record<string, number>
  targets: Record<string, [number, number]>
  height?: number
}) {
  const keys = ['energy_kcal', 'protein_g', 'fat_g', 'carbs_g', 'dietary_fiber_g',
    'sodium_mg', 'potassium_mg', 'phosphorus_mg', 'calcium_mg']
  const names: Record<string, string> = {
    energy_kcal: '能量', protein_g: '蛋白', fat_g: '脂肪', carbs_g: '碳水',
    dietary_fiber_g: '纤维', sodium_mg: '钠', potassium_mg: '钾',
    phosphorus_mg: '磷', calcium_mg: '钙',
  }
  // 归一化为目标中值百分比
  const pct = keys.map((k) => {
    const t = targets[k]
    const mid = t ? (t[0] + t[1]) / 2 : (actual[k] || 1)
    return Math.round(((actual[k] ?? 0) / mid) * 100)
  })
  const loPct = keys.map((k) => {
    const t = targets[k]
    const mid = t ? (t[0] + t[1]) / 2 : 1
    return t ? Math.round((t[0] / mid) * 100) : 0
  })
  const hiPct = keys.map((k) => {
    const t = targets[k]
    const mid = t ? (t[0] + t[1]) / 2 : 1
    return t ? Math.round((t[1] / mid) * 100) : 200
  })
  const option = {
    tooltip: { trigger: 'axis', formatter: (ps: unknown[]) => {
      const arr = ps as { name: string; value: number; seriesName: string }[]
      return `${arr[0]?.name}<br/>` + arr.map((p) => `${p.seriesName}: ${p.value}%`).join('<br/>')
    } },
    legend: { bottom: 0, data: ['实际(目标中值%)', '目标下限%', '目标上限%'] },
    grid: { left: 40, right: 20, top: 30, bottom: 50 },
    xAxis: { type: 'category', data: keys.map((k) => names[k]) },
    yAxis: { type: 'value', axisLabel: { formatter: '{value}%' } },
    series: [
      {
        name: '实际(目标中值%)', type: 'bar', data: pct, barWidth: 22,
        itemStyle: {
          color: (p: { value: number; dataIndex: number }) =>
            p.value < loPct[p.dataIndex] || p.value > hiPct[p.dataIndex]
              ? '#e5575e' : '#2f6fb0',
        },
      },
      { name: '目标下限%', type: 'line', data: loPct, symbol: 'none',
        lineStyle: { type: 'dashed', color: '#67c23a' } },
      { name: '目标上限%', type: 'line', data: hiPct, symbol: 'none',
        lineStyle: { type: 'dashed', color: '#e6a23c' } },
    ],
  }
  return <ReactECharts option={option} style={{ height }} />
}

/** 多方案关键指标对比（分组柱状）。 */
export function PlansCompareChart({
  plans,
  height = 340,
}: {
  plans: { title: string; metrics: {
    total_cost?: number
    score_breakdown?: Record<string, number>
  } }[]
  height?: number
}) {
  const metrics = [
    ['avg_day_cost', '日均成本(元)'],
    ['avg_nutrient_deviation_pct', '营养偏差(%)'],
    ['avg_satisfaction', '满意度×10'],
    ['waste_g_est', '浪费(g)/10'],
    ['distinct_dishes', '菜品数'],
  ] as const
  const option = {
    tooltip: { trigger: 'axis' },
    legend: { bottom: 0, data: plans.map((p) => p.title) },
    grid: { left: 50, right: 20, top: 30, bottom: 60 },
    xAxis: { type: 'category', data: metrics.map((m) => m[1]) },
    yAxis: { type: 'value' },
    series: plans.map((p, i) => {
      const bd = p.metrics.score_breakdown || {}
      const colors = ['#2f6fb0', '#5aa0d8', '#67c23a', '#e6a23c', '#9b59b6']
      return {
        name: p.title, type: 'bar',
        data: metrics.map(([k]) => {
          const v = Number(bd[k] ?? 0)
          if (k === 'avg_satisfaction') return +(v * 10).toFixed(1)
          if (k === 'waste_g_est') return +(v / 10).toFixed(1)
          return v
        }),
        itemStyle: { color: colors[i % colors.length] },
      }
    }),
  }
  return <ReactECharts option={option} style={{ height }} />
}
