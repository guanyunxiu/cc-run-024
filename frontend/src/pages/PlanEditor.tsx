import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  Alert, Button, Card, Col, Drawer, Dropdown, Empty, Input, Modal, Progress,
  Row, Segmented, Space, Statistic, Table, Tag, Tooltip, Typography, App,
} from 'antd'
import {
  LockOutlined, UnlockOutlined, ReloadOutlined, CloudUploadOutlined,
  HistoryOutlined, FilePdfOutlined, FileExcelOutlined, InboxOutlined,
  WarningOutlined, StopOutlined, RollbackOutlined,
} from '@ant-design/icons'
import { DndContext, DragEndEvent, DragOverlay,
         PointerSensor, useDroppable, useSensor, useSensors } from '@dnd-kit/core'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import dayjs from 'dayjs'
import { api, apiError } from '../api/client'
import { CATEGORY_LABELS, Dish, MenuItem, SLOT_LABELS, SLOT_ORDER } from '../lib/types'
import { useAuthStore, canWrite as roleCanWrite } from '../store/auth'
import { DraggableDish, DragData } from '../components/DraggableDish'

// 与后端 solver.SLOT_LINES 对齐的类别允许表
const LINE_CATS: Record<string, string[]> = {
  staple: ['staple'],
  protein: ['egg', 'soy', 'dairy', 'entree'],
  entree: ['entree', 'egg', 'soy'],
  vegetable: ['vegetable'],
  soup: ['soup'],
  snack: ['snack', 'fruit', 'dairy', 'soy'],
}
const LINES_BY_SLOT: Record<string, string[]> = {
  breakfast: ['staple', 'protein', 'vegetable'],
  morning_snack: ['snack'],
  lunch: ['staple', 'entree', 'vegetable', 'soup'],
  afternoon_snack: ['snack'],
  dinner: ['staple', 'entree', 'vegetable', 'soup'],
}
const LINE_LABELS: Record<string, string> = {
  staple: '主食', protein: '蛋白', entree: '主菜', vegetable: '蔬菜',
  soup: '汤', snack: '加餐',
}

interface CheckResult {
  hard: any[]
  soft: any[]
  cost_over: any[]
  feasible: boolean
}

function DroppableCell({ day, slot, line, over, children }: {
  day: number; slot: string; line: string; over: boolean
  children: React.ReactNode
}) {
  const { setNodeRef, isOver } = useDroppable({ id: `cell-${day}-${slot}-${line}` })
  return (
    <div ref={setNodeRef} className={`meal-cell ${isOver || over ? 'over' : ''}`}
         data-cell={`${day}-${slot}-${line}`}>
      {children}
    </div>
  )
}

export default function PlanEditor() {
  const { id } = useParams()
  const planId = Number(id)
  const [searchParams, setSearchParams] = useSearchParams()
  const nav = useNavigate()
  const qc = useQueryClient()
  const { message, modal } = App.useApp()
  const role = useAuthStore((s) => s.user?.role)
  const writable = roleCanWrite(role)

  const [day, setDay] = useState(0)
  const [paletteOpen, setPaletteOpen] = useState(false)
  const [paletteCtx, setPaletteCtx] = useState<{ slot: string; line: string } | null>(null)
  const [dishKw, setDishKw] = useState('')
  const [conflicts, setConflicts] = useState<CheckResult | null>(null)
  const [taskProgress, setTaskProgress] = useState<any>(null)
  const [versionOpen, setVersionOpen] = useState(false)
  const [dragData, setDragData] = useState<DragData | null>(null)
  const pollRef = useRef<any>(null)

  const sensors = useSensors(useSensor(PointerSensor, {
    activationConstraint: { distance: 5 },
  }))

  // ---------- 数据 ----------
  const { data: plan, refetch } = useQuery({
    queryKey: ['plan', planId],
    queryFn: async () => (await api.get(`/api/plans/${planId}`)).data,
    refetchInterval: false,
  })
  const { data: resident } = useQuery({
    queryKey: ['resident', plan?.resident_id],
    enabled: !!plan,
    queryFn: async () => (await api.get(`/api/residents/${plan.resident_id}`)).data,
  })
  const { data: dishesRaw } = useQuery({
    queryKey: ['dishes'],
    queryFn: async () => (await api.get('/api/dishes')).data,
  })
  const dishes: Dish[] = useMemo(() => dishesRaw || [], [dishesRaw])
  const dishMap = useMemo(() =>
    Object.fromEntries(dishes.map((d) => [d.id, d])), [dishes])

  // ---------- 冲突实时校验 ----------
  const refreshConflicts = useCallback(async () => {
    if (!plan) return
    const items = plan.items.map((it: MenuItem) => ({
      day_index: it.day_index, slot: it.slot, line: it.line,
      dish_id: it.dish_id,
    }))
    try {
      const { data } = await api.post(`/api/plans/${planId}/check`, {
        resident_id: plan.resident_id, items,
      })
      setConflicts(data)
    } catch { /* ignore */ }
  }, [plan, planId])

  useEffect(() => { refreshConflicts() }, [refreshConflicts])

  // ---------- 任务轮询 ----------
  const pollTask = useCallback(async (taskId: number) => {
    const tick = async () => {
      const { data: t } = await api.get(`/api/tasks/${taskId}`)
      setTaskProgress(t)
      if (t.status === 'success') {
        clearInterval(pollRef.current)
        message.success('配餐求解完成')
        await refetch()
        setTaskProgress(null)
      } else if (t.status === 'failed') {
        clearInterval(pollRef.current)
        message.error(`求解失败：${t.error}`)
        setTaskProgress(null)
      }
    }
    await tick()
    pollRef.current = setInterval(tick, 1000)
  }, [message, refetch])

  useEffect(() => {
    const tid = searchParams.get('task')
    if (tid) {
      pollTask(Number(tid))
      searchParams.delete('task')
      setSearchParams(searchParams, { replace: true })
    }
    return () => clearInterval(pollRef.current)
  }, [])

  // ---------- 修改 ----------
  const patchMu = useMutation({
    mutationFn: async (p: { item: MenuItem; dishId: number; locked?: boolean }) => {
      const { data } = await api.patch(`/api/plans/${planId}/items`, {
        day_index: p.item.day_index, slot: p.item.slot, line: p.item.line,
        dish_id: p.dishId,
        locked: p.locked ?? p.item.locked, version: plan.version,
      })
      return data
    },
    onSuccess: async (data) => {
      qc.setQueryData(['plan', planId], (old: any) =>
        old ? { ...old, version: data.version } : old)
      await refetch()
    },
    onError: (e) => message.error(apiError(e)),
  })

  const lockMu = useMutation({
    mutationFn: async (item: MenuItem) => {
      const { data } = await api.post(`/api/plans/${planId}/lock`, {
        item_id: item.id, locked: !item.locked, version: plan.version,
      })
      return data
    },
    onSuccess: async () => { await refetch() },
    onError: (e) => message.error(apiError(e)),
  })

  const resolveMu = useMutation({
    mutationFn: async (dayIndex: number | null) => {
      const { data } = await api.post(`/api/plans/${planId}/resolve`, {
        version: plan.version, day_index: dayIndex, time_limit_sec: 20,
      })
      return data
    },
    onSuccess: (d) => {
      message.success('已提交重求解，保持锁定菜品不变')
      pollTask(d.task_id)
    },
    onError: (e) => message.error(apiError(e)),
  })

  const publishMu = useMutation({
    mutationFn: async () =>
      (await api.post(`/api/plans/${planId}/publish`, {
        version: plan.version, note: '',
      })).data,
    onSuccess: async (d) => {
      message.success(`已发布 v${d.version_no}`)
      await refetch()
      qc.invalidateQueries({ queryKey: ['plans'] })
    },
    onError: (e) => message.error(apiError(e)),
  })

  const archiveMu = useMutation({
    mutationFn: async () => (await api.post(`/api/plans/${planId}/archive`)).data,
    onSuccess: async () => {
      message.success('已归档')
      await refetch()
      qc.invalidateQueries({ queryKey: ['plans'] })
    },
    onError: (e) => message.error(apiError(e)),
  })

  // ---------- 拖拽 ----------
  const onDragEnd = async (e: DragEndEvent) => {
    setDragData(null)
    if (!e.over || !e.active.data.current || !plan || !writable) return
    const overId = String(e.over.id)
    if (!overId.startsWith('cell-')) return
    const [, dStr, slot, line] = overId.split('-')
    const targetDay = Number(dStr)
    const drag = e.active.data.current as DragData
    if (drag.kind !== 'dish') return

    // 类别兼容检查
    const cat = dishMap[drag.dishId]?.category
    if (cat && !LINE_CATS[line]?.includes(cat)) {
      message.warning(`「${dishMap[drag.dishId].name}」类别为${CATEGORY_LABELS[cat]}，不能放到${LINE_LABELS[line]}位`)
      return
    }

    const target = plan.items.find((it: MenuItem) =>
      it.day_index === targetDay && it.slot === slot && it.line === line)
    if (!target) return
    if (target.locked) {
      message.warning('该菜品已锁定，请先解锁')
      return
    }
    if (target.dish_id === drag.dishId) return
    await patchMu.mutateAsync({ item: target, dishId: drag.dishId })
  }

  // ---------- 调色板候选 ----------
  const paletteCandidates = useMemo(() => {
    if (!paletteCtx) return []
    const allow = LINE_CATS[paletteCtx.line] || []
    return dishes
      .filter((d) => allow.includes(d.category))
      .filter((d) => d.name.includes(dishKw))
  }, [dishes, paletteCtx, dishKw])

  // 当前天的冲突索引
  const conflictKey = (dayIndex: number, slot: string, line?: string) => (x: any) =>
    x.day_index === dayIndex && x.slot === slot &&
    (line === undefined || x.line === line)

  const dayCost = useMemo(() => {
    const dt = plan?.totals?.day_totals?.[String(day)]
    return dt?.cost
  }, [plan, day])

  if (!plan) return <div className="page-container"><Card loading /></div>

  const score = plan.score || {}
  const published = plan.status === 'published'

  const renderDish = (it: MenuItem) => {
    const d = dishMap[it.dish_id]
    const hard = conflicts?.hard.filter(conflictKey(it.day_index, it.slot, it.line)) || []
    const soft = conflicts?.soft.filter(conflictKey(it.day_index, it.slot, it.line)) || []
    const cls = it.locked ? 'locked' : hard.length ? 'has-hard' : soft.length ? 'has-soft' : ''
    const dragPayload: DragData = {
      kind: 'dish', dishId: it.dish_id, dishName: it.dish_name,
      source: { day: it.day_index, slot: it.slot, line: it.line },
    }
    const tip = [...hard, ...soft].map((c) => `[${c.rule_name}] ${c.message}`).join('\n')
    return (
      <DraggableDish key={`${it.day_index}-${it.slot}-${it.line}`}
                     data={dragPayload} disabled={it.locked || !writable}
                     className={cls}
                     onLockToggle={() => lockMu.mutate(it)}>
        <div onPointerDown={(e) => e.stopPropagation()}>
          <Space style={{ width: '100%', justifyContent: 'space-between' }}>
            <Space size={4}>
              <b style={{ fontSize: 12 }}>{it.dish_name}</b>
              <Tag style={{ marginInlineEnd: 0, fontSize: 10 }}>L{d?.iddsi_level}</Tag>
            </Space>
            <Space size={2}>
              {writable && (
                <Tooltip title={it.locked ? `已锁定（${it.locked_by || ''}）` : '锁定'}>
                  <Button size="small" type="text"
                          icon={it.locked
                            ? <LockOutlined style={{ color: '#52c41a' }} />
                            : <UnlockOutlined />}
                          onClick={() => lockMu.mutate(it)} />
                </Tooltip>
              )}
            </Space>
          </Space>
          <Space size={6} style={{ fontSize: 11, color: '#888', marginTop: 2 }}>
            <span>¥{d?.cost?.toFixed(2)}</span>
            <span>{d?.energy_kcal?.toFixed(0)}kcal</span>
            {hard.length > 0 && (
              <Tooltip title={<pre style={{ whiteSpace: 'pre-wrap' }}>{tip}</pre>}>
                <Tag color="red" style={{ fontSize: 10 }}>
                  <WarningOutlined /> {hard.length}</Tag>
              </Tooltip>)}
            {soft.length > 0 && (
              <Tooltip title={<pre style={{ whiteSpace: 'pre-wrap' }}>{tip}</pre>}>
                <Tag color="orange" style={{ fontSize: 10 }}>{soft.length}</Tag>
              </Tooltip>)}
          </Space>
        </div>
      </DraggableDish>
    )
  }

  const renderCell = (slot: string, line: string) => {
    const it = plan.items.find((x: MenuItem) =>
      x.day_index === day && x.slot === slot && x.line === line)
    return (
      <DroppableCell key={`${slot}-${line}`} day={day} slot={slot} line={line} over={false}>
        {it ? renderDish(it) : (
          <Space direction="vertical" align="center" style={{ width: '100%', padding: 8 }}
                  onClick={() => { setPaletteCtx({ slot, line }); setPaletteOpen(true) }}>
            <InboxOutlined style={{ color: '#bbb' }} />
            <Typography.Text type="secondary" style={{ fontSize: 11 }}>
              拖入或选择菜品</Typography.Text>
          </Space>
        )}
      </DroppableCell>
    )
  }

  const downloadFile = async (suffix: string, mime: string, filename: string) => {
    const resp = await api.get(`/api/reports/plan/${planId}/${suffix}`,
                               { responseType: 'blob' })
    const url = URL.createObjectURL(new Blob([resp.data], { type: mime }))
    const a = document.createElement('a')
    a.href = url; a.download = filename; a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="page-container">
      {/* 头部 */}
      <Card size="small" style={{ marginBottom: 12 }}>
        <Row align="middle" justify="space-between">
          <Col>
            <Space wrap>
              <Typography.Title level={5} style={{ margin: 0 }}>{plan.name}</Typography.Title>
              <Tag color={published ? 'green' : 'default'}>
                {published ? '已发布' : '草稿'}
              </Tag>
              <Typography.Text type="secondary">
                {plan.start_date} 起 · {plan.days} 天 · 日预算 ¥{plan.budget_per_day}
              </Typography.Text>
              <Tag>v{plan.version}</Tag>
            </Space>
          </Col>
          <Col>
            <Space wrap>
              <Button icon={<ReloadOutlined />}
                      disabled={!writable || !!taskProgress}
                      onClick={() => modal.confirm({
                        title: '全部重新求解？',
                        content: '已锁定的菜品保持不变，其余槽位重新优化。',
                        onOk: () => resolveMu.mutate(null),
                      })}>全部重算</Button>
              <Button icon={<HistoryOutlined />} onClick={() => setVersionOpen(true)}>
                版本</Button>
              <Dropdown menu={{ items: [
                { key: 'pdf', icon: <FilePdfOutlined />, label: '导出 PDF 报告',
                  onClick: () => downloadFile('pdf', 'application/pdf', `mealplan_${planId}.pdf`) },
                { key: 'xlsx', icon: <FileExcelOutlined />, label: '导出 Excel',
                  onClick: () => downloadFile('excel',
                    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                    `mealplan_${planId}.xlsx`) },
                { key: 'report', label: '查看分析报告页',
                  onClick: () => nav(`/plans/${planId}/report`) },
              ] }}>
                <Button>报告/导出</Button>
              </Dropdown>
              {published
                ? <Button icon={<StopOutlined />} danger
                          disabled={!writable}
                          onClick={() => archiveMu.mutate()}>归档</Button>
                : <Button type="primary" icon={<CloudUploadOutlined />}
                          disabled={!writable}
                          onClick={() => {
                            if (conflicts && !conflicts.feasible) {
                              modal.confirm({
                                title: '存在硬约束冲突，无法发布',
                                content: `当前有 ${conflicts.hard.length} 项硬冲突，` +
                                  `请先调整（或局部重算）后再发布。`,
                                okText: '知道了', cancelButtonProps: { style: { display: 'none' } },
                              })
                              return
                            }
                            publishMu.mutate()
                          }}>发布</Button>}
            </Space>
          </Col>
        </Row>
      </Card>

      {/* 求解进度 */}
      {taskProgress && (
        <Alert type="info" showIcon style={{ marginBottom: 12 }}
               message={<Space>
                 <Progress type="circle" percent={taskProgress.progress} size={28} />
                 <b>{taskProgress.message || '求解中…'}</b>
                 <Typography.Text type="secondary">
                   CP-SAT 正在优化硬约束与多目标，请稍候</Typography.Text>
               </Space>} />
      )}

      {/* 冲突总览 */}
      {conflicts && (conflicts.hard.length > 0 || conflicts.cost_over?.length > 0) && (
        <Alert type="error" showIcon style={{ marginBottom: 12 }}
               message={`存在 ${conflicts.hard.length} 项硬约束冲突` +
                 (conflicts.cost_over.length
                   ? `，${conflicts.cost_over.length} 天超出预算` : '')}
               description={
                 <Space direction="vertical" size={2}>
                   {conflicts.hard.slice(0, 5).map((h, i) => (
                     <span key={i} style={{ fontSize: 12 }}>
                       第{h.day_index + 1}天 {SLOT_LABELS[h.slot]} 《{h.dish_name}》：
                       <b>{h.message}</b>
                     </span>
                   ))}
                   {conflicts.hard.length > 5 &&
                     <span style={{ fontSize: 12 }}>…其余 {conflicts.hard.length - 5} 项见单元格红标</span>}
                 </Space>} />
      )}
      {(plan.totals?.warnings?.length || 0) > 0 && (
        <Alert type="warning" showIcon style={{ marginBottom: 12 }}
               message={(plan.totals?.warnings || []).join('；')} />
      )}

      {/* KPI */}
      <Row gutter={12} style={{ marginBottom: 12 }}>
        {[
          ['营养达标率', `${score.avg_attainment_pct?.toFixed(1) ?? '—'}%`],
          ['日均成本', `¥${score.avg_cost_per_day ?? '—'}`],
          ['平均满意度', score.avg_satisfaction ?? '—'],
          ['菜品丰富度', score.distinct_dishes ?? '—'],
          ['软约束提示', score.soft_violation_count ?? 0],
          ['预计浪费成本', `¥${score.estimated_waste_cost ?? '—'}`],
        ].map(([t, v]) => (
          <Col span={4} key={t as string}>
            <Card size="small"><Statistic title={t as string} value={v as any} /></Card>
          </Col>
        ))}
      </Row>

      {/* 天切换 + 当日重算 */}
      <Card size="small" style={{ marginBottom: 12 }}>
        <Space style={{ width: '100%', justifyContent: 'space-between' }}>
          <Segmented value={day} onChange={(v) => setDay(v as number)}
                     options={Array.from({ length: plan.days }, (_, i) => ({
                       value: i,
                       label: `第${i + 1}天 ${dayjs(plan.start_date).add(i, 'day').format('MM-DD')}`,
                     }))} />
          <Space>
            <Typography.Text type="secondary">
              当日成本 <b style={{ color: dayCost > plan.budget_per_day ? '#cf1322' : undefined }}>
                ¥{dayCost?.toFixed?.(2) ?? '—'}</b> / ¥{plan.budget_per_day}
            </Typography.Text>
            <Button size="small" icon={<ReloadOutlined />} disabled={!writable || !!taskProgress}
                    onClick={() => resolveMu.mutate(day)}>
              仅重算第{day + 1}天
            </Button>
          </Space>
        </Space>
      </Card>

      {/* 餐次网格 */}
      <DndContext sensors={sensors} onDragEnd={onDragEnd}
                 onDragStart={(e) => setDragData(e.active.data.current as DragData)}
                 onDragCancel={() => setDragData(null)}>
        <Row gutter={12}>
          {SLOT_ORDER.map((slot) => (
            <Col span={slot.includes('snack') ? 24 : 24} key={slot}
                 style={{ marginBottom: 8 }}>
              <Card size="small"
                    title={<Space>
                      <b style={{ fontSize: 13 }}>{SLOT_LABELS[slot]}</b>
                      <Typography.Text type="secondary" style={{ fontSize: 11 }}>
                        {LINES_BY_SLOT[slot].map((l) => LINE_LABELS[l]).join(' / ')}
                      </Typography.Text>
                    </Space>}
                    styles={{ body: { padding: 8 } }}>
                <Row gutter={8}>
                  {LINES_BY_SLOT[slot].map((line) => (
                    <Col key={line} span={slot.includes('snack') ? 24 : 6}>
                      <Typography.Text type="secondary"
                        style={{ fontSize: 11, display: 'block', marginBottom: 4 }}>
                        {LINE_LABELS[line]}
                        <span style={{ color: '#bbb' }}>
                          （{LINE_CATS[line].map((c) => CATEGORY_LABELS[c]).join('/')}）
                        </span>
                      </Typography.Text>
                      {renderCell(slot, line)}
                    </Col>
                  ))}
                </Row>
              </Card>
            </Col>
          ))}
        </Row>

        <DragOverlay>
          {dragData ? (
            <div className="dish-card" style={{ background: '#2f5496', color: '#fff' }}>
              {dragData.dishName}
            </div>
          ) : null}
        </DragOverlay>
      </DndContext>

      {/* 菜品选择抽屉 */}
      <Drawer title={paletteCtx
        ? `选择菜品（${LINE_LABELS[paletteCtx.line]}位 · 第${day + 1}天）`
        : '选择菜品'}
              open={paletteOpen} width={520} onClose={() => setPaletteOpen(false)}>
        <Input.Search placeholder="搜索菜名" style={{ marginBottom: 10 }}
                      allowClear value={dishKw} onChange={(e) => setDishKw(e.target.value)} />
        <Space wrap style={{ marginBottom: 8 }}>
          <Typography.Text type="secondary" style={{ fontSize: 12 }}>
            拖拽或点击菜品放入当前槽位；列表已按类别过滤
          </Typography.Text>
        </Space>
        {paletteCandidates.length === 0 && <Empty description="该类别暂无菜品" />}
        {paletteCandidates.map((d) => {
          const check = (d as any).check
          return (
            <DraggableDish key={`pal-${d.id}`}
                           data={{ kind: 'dish', dishId: d.id, dishName: d.name }}
                           className="" >
              <Space style={{ width: '100%', justifyContent: 'space-between' }}
                     onClick={async () => {
                       if (!paletteCtx) return
                       const target = plan.items.find((it: MenuItem) =>
                         it.day_index === day && it.slot === paletteCtx.slot
                         && it.line === paletteCtx.line)
                       if (target) {
                         await patchMu.mutateAsync({ item: target, dishId: d.id })
                         setPaletteOpen(false)
                       }
                     }}>
                <Space direction="vertical" size={0}>
                  <b style={{ fontSize: 12 }}>{d.name}</b>
                  <span style={{ fontSize: 11, color: '#888' }}>
                    {CATEGORY_LABELS[d.category]} · L{d.iddsi_level} ·
                    ¥{d.cost.toFixed(2)} · {d.energy_kcal.toFixed(0)}kcal ·
                    钠{d.sodium_mg.toFixed(0)}
                  </span>
                </Space>
                <Tag color="blue">选用</Tag>
              </Space>
            </DraggableDish>
          )
        })}
      </Drawer>

      {/* 版本管理 */}
      <VersionDrawer open={versionOpen} onClose={() => setVersionOpen(false)}
                     planId={planId} currentVersion={plan.version}
                     onChanged={refetch} resident={resident} />
    </div>
  )
}

// ---------- 版本抽屉 ----------
function VersionDrawer({ open, onClose, planId, currentVersion, onChanged, resident }: {
  open: boolean
  onClose: () => void
  planId: number
  currentVersion: number
  onChanged: () => void
  resident?: any
}) {
  const { message, modal } = App.useApp()
  const nav = useNavigate()
  const { data: versions } = useQuery({
    queryKey: ['plan-versions', planId],
    enabled: open,
    queryFn: async () => (await api.get(`/api/plans/${planId}/versions`)).data,
  })
  const [compare, setCompare] = useState<[number | null, number | null] | null>(null)
  const [diff, setDiff] = useState<any>(null)

  const doCompare = async (a: number, b: number) => {
    setCompare([a, b])
    const { data } = await api.get(`/api/plans/${planId}/compare/${a}/${b}`)
    setDiff(data)
  }
  const rollback = (vno: number) => {
    modal.confirm({
      title: `回滚到 v${vno}？`,
      content: '当前排餐内容将被该版本快照覆盖，并生成新的当前版本。',
      onOk: async () => {
        try {
          await api.post(`/api/plans/${planId}/rollback/${vno}`)
          message.success(`已回滚到 v${vno}`)
          onChanged()
          onClose()
        } catch (e) { message.error(apiError(e)) }
      },
    })
  }

  return (
    <Drawer title="版本历史 / 对比 / 回滚" open={open} width={640} onClose={onClose}>
      <Table size="small" pagination={false} rowKey="version_no"
             dataSource={(versions || []) as any[]}
             columns={[
               { title: '版本', dataIndex: 'version_no', width: 70,
                 render: (v) => <Tag color="blue">v{v}</Tag> },
               { title: '备注', dataIndex: 'note' },
               { title: '发布人', dataIndex: 'created_by', width: 100 },
               { title: '时间', dataIndex: 'created_at', width: 160,
                 render: (t) => dayjs(t).format('MM-DD HH:mm') },
               { title: '操作', width: 130,
                 render: (_, r) => (
                   <Space size={4}>
                     <Typography.Link onClick={() => rollback(r.version_no)}>
                       <RollbackOutlined /> 回滚
                     </Typography.Link>
                   </Space>) },
             ]} />
      <Space style={{ marginTop: 12 }} wrap>
        <Typography.Text>版本对比：</Typography.Text>
        {(versions || []).map((v: any, i: number) => (
          <Button key={v.version_no} size="small"
                  type={compare?.includes(v.version_no) ? 'primary' : 'default'}
                  onClick={() => {
                    const cur: [number | null, number | null] =
                      compare && compare[0] !== null && compare[1] === null
                        ? compare
                        : [null, null]
                    let next: [number | null, number | null]
                    if (cur[0] === null) {
                      next = [v.version_no, null]
                      setCompare(next)
                    } else {
                      next = [cur[0], v.version_no]
                      doCompare(cur[0], v.version_no)
                    }
                  }}>
            v{v.version_no}
          </Button>
        ))}
      </Space>
      {diff && (
        <Card size="small" style={{ marginTop: 12 }}
              title={`v${diff.v_a} → v${diff.v_b}：${diff.item_diff.length} 处菜品差异`}>
          <Space style={{ marginBottom: 8 }} wrap>
            <Tag color="green">达标率 {diff.score_a?.avg_attainment_pct?.toFixed(1)}%
              → {diff.score_b?.avg_attainment_pct?.toFixed(1)}%</Tag>
            <Tag>日均成本 ¥{diff.score_a?.avg_cost_per_day}
              → ¥{diff.score_b?.avg_cost_per_day}</Tag>
          </Space>
          <Table size="small" pagination={{ pageSize: 8 }}
                 dataSource={(diff.item_diff || []) as any[]} rowKey={(_r: any, i?: number) => `${i}`}
                 columns={[
                   { title: '天', dataIndex: 'day_index', width: 50,
                     render: (d) => `第${d + 1}天` },
                   { title: '餐次', dataIndex: 'slot', width: 90,
                     render: (s) => SLOT_LABELS[s] },
                   { title: `v${diff.v_a}`, render: (_: any, r: any) => r[`v${diff.v_a}`] || '—' },
                   { title: `v${diff.v_b}`, render: (_: any, r: any) => r[`v${diff.v_b}`] || '—' },
                 ]} />
        </Card>
      )}
      {!diff && (versions?.length < 2) && (
        <Alert style={{ marginTop: 12 }} type="info"
               message="至少发布两个版本后可进行版本对比" />
      )}
    </Drawer>
  )
}
