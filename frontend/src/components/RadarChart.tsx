import ReactECharts from 'echarts-for-react'

export function RadarChart({ attainment, labels, height = 300 }: {
  attainment: Record<string, number>
  labels: Record<string, string>
  height?: number
}) {
  const indicator = Object.keys(labels).map((k) => ({
    name: labels[k], max: 100,
  }))
  const values = Object.keys(labels).map((k) => attainment?.[k] ?? 0)
  const option = {
    tooltip: {},
    radar: {
      indicator, radius: '65%',
      axisName: { color: '#555', fontSize: 11 },
      splitArea: { areaStyle: { color: ['#fafcff', '#eef3fb'] } },
    },
    series: [{
      type: 'radar',
      data: [{
        value: values, name: '营养达标率(%)',
        areaStyle: { color: 'rgba(47,84,150,.30)' },
        lineStyle: { color: '#2f5496', width: 2 },
        itemStyle: { color: '#2f5496' },
        label: { show: true, fontSize: 10, color: '#333',
                 formatter: (p: any) => `${Math.round(p.value)}` },
      }],
    }],
  }
  return <ReactECharts option={option} style={{ height }} />
}
