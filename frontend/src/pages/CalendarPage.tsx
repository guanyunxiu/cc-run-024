import { useMemo, useState } from 'react'
import { Card, Select, Space, Tag, Typography, Empty, Badge } from 'antd'
import { useNavigate } from 'react-router-dom'
import FullCalendar from '@fullcalendar/react'
import dayGridPlugin from '@fullcalendar/daygrid'
import interactionPlugin from '@fullcalendar/interaction'
import zhCnLocale from '@fullcalendar/core/locales/zh-cn'
import { usePlans, useElders } from '../api/hooks'
import { SLOT_LABELS } from '../lib/types'

export default function CalendarPage() {
  const nav = useNavigate()
  const { data: plans } = usePlans()
  const { data: elders } = useElders()
  const [elderId, setElderId] = useState<number | undefined>(undefined)

  const events = useMemo(() => {
    const list = (plans || []).filter((p) => !elderId || p.elder_id === elderId)
    const out: { id: string; title: string; start: string; end?: string;
      planId: number; color: string; detail: string }[] = []
    list.forEach((p) => {
      const colors: Record<string, string> = {
        published: '#52c41a', draft: '#faad14', archived: '#bfbfbf',
      }
      const dayCount = p.period_type === 'week' ? 7 : 1
      const itemSummary: Record<string, number> = {}
      p.items.forEach((i) => { itemSummary[i.slot] = (itemSummary[i.slot] || 0) + 1 })
      const detail = Object.entries(itemSummary)
        .map(([s, n]) => `${SLOT_LABELS[s]} ${n}菜`).join(' / ')
      for (let d = 0; d < dayCount; d++) {
        const date = new Date(p.start_date)
        date.setDate(date.getDate() + d)
        out.push({
          id: `${p.id}-${d}`,
          title: `🍱 ${p.elder_name || ''}${p.period_type === 'week' && d === 0 ? ' 周配餐' : ''}`,
          start: date.toISOString().slice(0, 10),
          planId: p.id, color: colors[p.status] || '#2f6fb0',
          detail: d === 0 ? detail : '',
        })
      }
    })
    return out
  }, [plans, elderId])

  return (
    <Card
      title="排餐日历"
      extra={
        <Space>
          <span>老人筛选：</span>
          <Select
            allowClear style={{ width: 200 }} placeholder="全部老人"
            value={elderId} onChange={setElderId}
            options={(elders || []).map((e) => ({ value: e.id, label: e.name }))}
          />
          <Space>
            <Badge color="#52c41a" text="已发布" />
            <Badge color="#faad14" text="草稿" />
            <Badge color="#bfbfbf" text="已归档" />
          </Space>
        </Space>
      }
    >
      {plans?.length === 0
        ? <Empty description="暂无方案，先去「配餐方案」发起求解" />
        : (
          <FullCalendar
            plugins={[dayGridPlugin, interactionPlugin]}
            initialView="dayGridMonth"
            initialDate="2026-09-21"
            locale={zhCnLocale}
            height="auto"
            events={events.map((e) => ({
              id: e.id, title: e.title, start: e.start,
              backgroundColor: e.color, borderColor: e.color,
              extendedProps: { planId: e.planId, detail: e.detail },
            }))}
            eventClick={(info) => nav(`/plans/${info.event.extendedProps.planId}`)}
            eventDidMount={(info) => {
              if (info.event.extendedProps.detail) {
                info.el.title = info.event.extendedProps.detail
              }
            }}
            headerToolbar={{
              left: 'prev,next today', center: 'title', right: 'dayGridMonth',
            }}
          />
        )}
      <Typography.Paragraph type="secondary" style={{ marginTop: 12 }}>
        点击日历事件可跳转到方案详情；周方案在整周每日显示；颜色代表发布状态。
      </Typography.Paragraph>
    </Card>
  )
}
