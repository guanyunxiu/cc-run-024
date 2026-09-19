import { useEffect, useMemo, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  Card, Space, Button, Tag, App, Spin, Alert, Statistic, Row, Col, Collapse,
  Table, Modal, List, Tabs, Input, Select, Tooltip, Typography, Divider,
} from 'antd'
import {
  ArrowLeftOutlined, SaveOutlined, CloudUploadOutlined, HistoryOutlined,
  RollbackOutlined, FilePdfOutlined, FileExcelOutlined, ThunderboltOutlined,
  ShoppingCartOutlined, LockOutlined,
} from '@ant-design/icons'
import dayjs from 'dayjs'
import {
  usePlan, useElder, useDishes, useUpdatePlan, usePlanAction, usePlanVersions,
  useRollback, useResolve, useTask, useCheckDishes, usePurchase,
} from '../api/hooks'
import { downloadFile, api } from '../api/client'
import type { Dish, MealItem, Violation } from '../lib/types'
import {
  SLOT_LABELS, DISH_TYPE_LABELS, IDDSI_LABELS, NUTRIENT_LABELS,
} from '../lib/types'
import PlanEditor, { PaletteItem } from '../components/PlanEditor'
import { NutrientRadar, NutrientBars } from '../components/Charts'

const SLOTS = ['breakfast', 'lunch', 'dinner']

export default function PlanDetailPage() {
  const { id } = useParams()
  const planId = Number(id)
  const nav = useNavigate()
  const { message, modal } = App.useApp()
  const { data: plan, isLoading, refetch } = usePlan(planId)
  const { data: elder } = useElder(plan?.elder_id)
  const { data: allDishes } = useDishes()
  const update = useUpdatePlan()
  const action = usePlanAction()
  const resolve = useResolve()
  const rollback = useRollback()
  const { data: versions } = usePlanVersions(plan ? planId : null)
  const check = useCheckDishes()
  const purchase = usePurchase(planId)
  const [resolveTask, setResolveTask] = useState<number | null>(null)
  const { data: rtask } = useTask(resolveTask, {
    refetchInterval: resolveTask ? 1200 : false,
  })

  const [draft, setDraft] = useState<MealItem[] | null>(null)
  const [selectedCell, setSelectedCell] = useState<string | null>(null)
  const [violations, setViolations] = useState<Record<number, Violation[]>>({})
  const [paletteQ, setPaletteQ] = useState('')

  useEffect(() => { if (plan) setDraft(plan.items.map((x) => ({ ...x }))) },
    [plan?.id]) // eslint-disable-line

  const dishes: Record<number, Dish> = useMemo(() =>
    Object.fromEntries((allDishes || []).map((d) => [d.id!, d])), [allDishes])

  const days = plan?.period_type === 'week'
    ? dayjs(plan.end_date).diff(dayjs(plan.start_date), 'day') + 1 : 1

  // 冲突实时校验（草稿菜品集合变化时）
  const draftDishIds = useMemo(() =>
    [...new Set((draft || []).map((i) => i.dish_id))], [draft])

  useEffect(() => {
    if (!plan || draftDishIds.length === 0) { setViolations({}); return }
    check.mutate({ elder_id: plan.elder_id, dish_ids: draftDishIds }, {
      onSuccess: (d) => {
        const out: Record<number, Violation[]> = {}
        Object.entries(d.results).forEach(([did, r]) => {
          out[Number(did)] = (r as { violations: Violation[] }).violations || []
        })
        setViolations(out)
      },
    })
    // eslint-disable-next-line
  }, [draftDishIds.join(','), plan?.elder_id])

  useEffect(() => {
    if (rtask?.status === 'success') {
      message.success('局部重求解完成，已锁定菜品保持不变')
      refetch(); setResolveTask(null)
    } else if (rtask?.status === 'failed') {
      message.error(`局部重求解失败：${rtask.message}`)
      setResolveTask(null)
    }
  }, [rtask?.status]) // eslint-disable-line

  if (isLoading || !plan || !elder || !draft) return <Spin size="large" />

  const targets = (() => {
    try { return JSON.parse(elder.target_explanation)?.targets || {} } catch { return {} }
  })()
  const conflictCount = draft.filter((i) =>
    violations[i.dish_id]?.some((v) => v.level === 'forbid')).length
  const warnCount = draft.filter((i) =>
    violations[i.dish_id]?.some((v) => v.level === 'warn')).length

  const addDishToCell = (dishId: number) => {
    if (!selectedCell) { message.info('请先点击一个餐次格子'); return }
    const [dStr, slot] = selectedCell.split('-')
    const d = Number(dStr)
    const dish = dishes[dishId]
    const date = dayjs(plan.start_date).add(d, 'day').format('YYYY-MM-DD')
    setDraft([...draft, {
      day_index: d, meal_date: date, slot, dish_id: dishId,
      dish_name: dish.name, portion_g: Math.round(dish.portion_g / 30) * 30,
      locked: false,
    }])
  }

  const save = () => {
    update.mutate({
      id: planId,
      body: { lock_version: plan.lock_version, items: draft },
    }, {
      onSuccess: (p) => {
        message.success(`已保存（版本 v${p.lock_version}，冲突已在指标中标记）`)
        refetch()
      },
      onError: (e: unknown) => {
        const det = (e as { response?: { data?: { detail?: string } } }).response?.data?.detail
        message.error(det || '保存失败')
        refetch()
      },
    })
  }

  const onResolve = () => {
    const lockedN = draft.filter((x) => x.locked).length
    if (lockedN === 0) { message.warning('请先锁定至少一道菜，再做局部重求解'); return }
    // 先保存（含锁状态），再发起重求解
    update.mutate({ id: planId, body: { lock_version: plan.lock_version, items: draft } }, {
      onSuccess: () => {
        resolve.mutate(planId, {
          onSuccess: (d) => { setResolveTask(d.task_id); message.loading('局部重求解中…') },
          onError: (e: unknown) => message.error(
            (e as { response?: { data?: { detail?: string } } }).response?.data?.detail || '失败'),
        })
      },
      onError: (e: unknown) => message.error(
        (e as { response?: { data?: { detail?: string } } }).response?.data?.detail || '保存失败'),
    })
  }

  const publish = () => {
    if (conflictCount > 0) {
      modal.confirm({
        title: '存在硬约束冲突，仍要发布吗？',
        content: `当前有 ${conflictCount} 道菜违反过敏/禁忌/吞咽等硬约束，建议替换后再发布。`,
        okText: '仍要发布', okButtonProps: { danger: true },
        onOk: () => doPublish(),
      })
      return
    }
    doPublish()
  }
  const doPublish = () => update.mutate(
    { id: planId, body: { lock_version: plan.lock_version, items: draft } },
    {
      onSuccess: (saved) => action.mutate(
        { id: planId, action: 'publish', lockVersion: saved.lock_version },
        { onSuccess: () => { message.success('方案已发布'); refetch() } }),
      onError: () => refetch(),
    })

  const palette = (allDishes || []).filter((d) => {
    if (paletteQ && !d.name.includes(paletteQ)) return false
    if (d.iddsi_level > elder.iddsi_level) return false
    return true
  })

  const metrics = plan.metrics
  const dayAvg: Record<string, number> = {}
  const dn = metrics?.daily_nutrients || []
  if (dn.length) {
    Object.keys(dn[0]).forEach((k) => {
      dayAvg[k] = dn.reduce((s, x) => s + (x[k] || 0), 0) / dn.length
    })
  }
  const manualCheck = metrics?.nutrient_check
  let solverParamsObj: Record<string, unknown> = {}
  if (plan.solver_params) {
    if (typeof plan.solver_params === 'string') {
      try { solverParamsObj = JSON.parse(plan.solver_params) } catch { solverParamsObj = {} }
    } else {
      solverParamsObj = plan.solver_params
    }
  }

  return (
    <Space direction="vertical" size={12} style={{ width: '100%' }}>
      <Space wrap style={{ justifyContent: 'space-between', width: '100%' }}>
        <Space>
          <Button icon={<ArrowLeftOutlined />} onClick={() => nav('/plans')}>返回</Button>
          <Typography.Title level={5} style={{ margin: 0 }}>{plan.title}</Typography.Title>
          <Tag color={plan.status === 'published' ? 'green'
            : plan.status === 'archived' ? 'default' : 'gold'}>
            {plan.status === 'published' ? '已发布' : plan.status === 'archived' ? '已归档' : '草稿'}
          </Tag>
          <Tag>规则版本 {plan.rule_version}</Tag>
          <Tag>乐观锁 v{plan.lock_version}</Tag>
        </Space>
        <Space wrap>
          <Button icon={<SaveOutlined />} type="primary" ghost onClick={save}
            loading={update.isPending}>保存调整</Button>
          <Button icon={<ThunderboltOutlined />} onClick={onResolve}
            loading={!!resolveTask}>
            锁定后局部重求解
          </Button>
          <Button icon={<CloudUploadOutlined />} type="primary" onClick={publish}
            disabled={plan.status === 'archived'}>发布</Button>
          <Button icon={<FilePdfOutlined />}
            onClick={() => downloadFile(`/api/reports/plans/${planId}/pdf`, `方案${planId}.pdf`)}>
            PDF</Button>
          <Button icon={<FileExcelOutlined />}
            onClick={() => downloadFile(`/api/reports/plans/${planId}/excel`, `方案${planId}.xlsx`)}>
            Excel</Button>
        </Space>
      </Space>

      <Alert
        type={conflictCount ? 'error' : warnCount ? 'warning' : 'success'} showIcon
        message={conflictCount
          ? `存在 ${conflictCount} 项硬约束冲突（红框），保存会记录但发布前强烈建议替换`
          : warnCount
            ? `存在 ${warnCount} 项软提示（黄框，如华法林维K稳定/个人忌口）`
            : '当前配餐全部通过过敏/慢病/吞咽/宗教/药食硬约束校验'}
      />

      <Row gutter={12}>
        <Col span={4}><Card><Statistic title="总/日均成本"
          value={metrics?.total_cost ?? '-'} precision={1} prefix="¥"
          suffix={`/ ¥${metrics?.score_breakdown?.avg_day_cost ?? '-'}`} /></Card></Col>
        <Col span={4}><Card><Statistic title="平均营养偏差"
          value={metrics?.score_breakdown?.avg_nutrient_deviation_pct ?? '-'}
          suffix="%" valueStyle={{
            color: (metrics?.score_breakdown?.avg_nutrient_deviation_pct ?? 99) < 20
              ? '#389e0d' : '#cf1322' }} /></Card></Col>
        <Col span={4}><Card><Statistic title="满意度"
          value={metrics?.score_breakdown?.avg_satisfaction ?? '-'} suffix="/5" /></Card></Col>
        <Col span={4}><Card><Statistic title="浪费估算"
          value={metrics?.score_breakdown?.waste_g_est ?? '-'} suffix="g" /></Card></Col>
        <Col span={4}><Card><Statistic title="不同菜品"
          value={metrics?.score_breakdown?.distinct_dishes ?? '-'} /></Card></Col>
        <Col span={4}><Card><Statistic title="锁定菜品"
          value={draft.filter((x) => x.locked).length}
          prefix={<LockOutlined />} /></Card></Col>
      </Row>

      <Card
        title="排餐编辑（拖拽卡片换餐次；点击格子后从右侧面板加菜；锁定后可局部重求解）"
        extra={<Space>
          <Typography.Text type="secondary">
            {elder.name} · {IDDSI_LABELS[elder.iddsi_level]}
          </Typography.Text>
        </Space>}
      >
        <div style={{ display: 'flex', gap: 12 }}>
          <div style={{ flex: 1, overflowX: 'auto' }}>
            <PlanEditor
              days={days} slots={SLOTS} items={draft} dishes={dishes}
              violationsByDish={violations}
              selectedCellKey={selectedCell}
              onSelectCell={setSelectedCell}
              onChange={setDraft}
            />
          </div>
          <div style={{ width: 240, flexShrink: 0, borderLeft: '1px solid #eee',
            paddingLeft: 12 }}>
            <Input.Search placeholder="筛选可加菜（已按吞咽等级过滤）" allowClear size="small"
              onChange={(e) => setPaletteQ(e.target.value)} style={{ marginBottom: 8 }} />
            <div style={{ maxHeight: 520, overflowY: 'auto' }}>
              {palette.slice(0, 40).map((d) => {
                const v = violations[d.id!] || []
                const forbid = v.some((x) => x.level === 'forbid')
                return (
                  <Tooltip key={d.id} title={forbid
                    ? v.filter((x) => x.level === 'forbid').map((x) => x.message).join('；')
                    : '点击选中的格子即可加入'}>
                    <div onClick={() => !forbid && addDishToCell(d.id!)}
                      style={{ opacity: forbid ? 0.45 : 1, cursor: forbid ? 'not-allowed' : 'pointer' }}>
                      <PaletteItem dish={d} />
                    </div>
                  </Tooltip>
                )
              })}
            </div>
          </div>
        </div>
      </Card>

      <Card title="营养分析（多日均值 vs 个体化目标）">
        <Row gutter={16}>
          <Col span={10}><NutrientRadar actual={dayAvg} targets={targets} height={320} /></Col>
          <Col span={14}><NutrientBars actual={dayAvg} targets={targets} height={320} /></Col>
        </Row>
        {manualCheck && (
          <Alert style={{ marginTop: 8 }} type="info" showIcon
            message="手动调整后重新核算的达标情况（保存后刷新）"
            description={
              <Space wrap>
                {Object.entries(manualCheck).map(([k, c]) => (
                  <Tag key={k} color={c.in_range ? 'green' : 'red'}>
                    {NUTRIENT_LABELS[k] || k}: {c.avg}
                    （{c.target[0]}~{c.target[1]}）
                  </Tag>
                ))}
              </Space>} />
        )}
        <Collapse
          style={{ marginTop: 8 }}
          items={[{
            key: 'd', label: '每日营养与成本明细',
            children: (
              <Table
                size="small" pagination={false} scroll={{ x: 900 }}
                rowKey={(r, i) => String(i)}
                dataSource={(metrics?.daily_nutrients || []).map((n, i) => ({
                  ...n, day: i + 1, cost: metrics?.daily_costs?.[i],
                }))}
                columns={[
                  { title: '天', dataIndex: 'day', width: 50 },
                  ...['energy_kcal', 'protein_g', 'fat_g', 'carbs_g',
                    'dietary_fiber_g', 'sodium_mg', 'potassium_mg',
                    'phosphorus_mg', 'calcium_mg'].map((k) => ({
                      title: NUTRIENT_LABELS[k], dataIndex: k,
                      render: (v: number) => v?.toFixed(0),
                    })),
                  { title: '成本(元)', dataIndex: 'cost' },
                ]}
              />),
          }]}
        />
      </Card>

      <Tabs
        items={[
          {
            key: 'versions', label: <span><HistoryOutlined /> 版本与回滚</span>,
            children: (
              <Table
                size="small" pagination={false} rowKey="version_no"
                dataSource={(versions || []) as Array<Record<string, unknown>>}
                columns={[
                  { title: '版本号', dataIndex: 'version_no', width: 80 },
                  { title: '状态', dataIndex: 'status', width: 90,
                    render: (v: string) => <Tag>{v}</Tag> },
                  { title: '操作人', dataIndex: 'created_by', width: 110 },
                  { title: '时间', dataIndex: 'created_at', width: 170,
                    render: (v: string) => dayjs(v).format('YYYY-MM-DD HH:mm:ss') },
                  { title: '总成本', width: 90,
                    render: (_: unknown, r: Record<string, unknown>) =>
                      ((r.metrics as { total_cost?: number } | undefined)?.total_cost ?? '-') },
                  { title: '操作', width: 150,
                    render: (_: unknown, r: Record<string, unknown>) => (
                      <Space>
                        <Button size="small" icon={<RollbackOutlined />}
                          onClick={() => modal.confirm({
                            title: `回滚到 v${r.version_no}？`,
                            content: '当前编辑内容将被该版本快照覆盖，并生成新的草稿版本。',
                            onOk: () => rollback.mutateAsync(
                              { id: planId, v: Number(r.version_no) })
                              .then(() => { message.success('已回滚'); refetch() }),
                          })}>
                          回滚
                        </Button>
                        <Button size="small" onClick={() => {
                          Modal.info({
                            title: `版本 v${r.version_no} 快照`,
                            width: 800,
                            content: <VersionDiff planId={planId} version={Number(r.version_no)} />,
                          })
                        }}>查看</Button>
                      </Space>) },
                ]}
              />),
          },
          {
            key: 'purchase', label: <span><ShoppingCartOutlined /> 采购需求汇总</span>,
            children: (
              <>
                <Alert style={{ marginBottom: 8 }} type="info" showIcon
                  message="采购建议仅为需求汇总清单（按配方与排餐份数折算市品重量），不含仓库库存管理。" />
                <Table
                  size="small" pagination={false} rowKey="code"
                  loading={purchase.isLoading}
                  dataSource={purchase.data?.items || []}
                  columns={[
                    { title: '分类', dataIndex: 'category', width: 90 },
                    { title: '食材', dataIndex: 'ingredient' },
                    { title: '编码', dataIndex: 'code', width: 120 },
                    { title: '市品需求(g)', dataIndex: 'gross_g', width: 120 },
                    { title: '折可食熟重(g)', dataIndex: 'edible_g', width: 130 },
                    { title: '估算成本(元)', dataIndex: 'cost', width: 120 },
                  ]}
                  summary={(rows) => (
                    <Table.Summary.Row>
                      <Table.Summary.Cell index={0} colSpan={3}>合计</Table.Summary.Cell>
                      <Table.Summary.Cell index={3}>
                        {purchase.data?.total_gross_g} g
                      </Table.Summary.Cell>
                      <Table.Summary.Cell index={4} />
                      <Table.Summary.Cell index={5}>
                        ¥{purchase.data?.total_ingredient_cost}
                      </Table.Summary.Cell>
                    </Table.Summary.Row>
                  )}
                />
              </>),
          },
          {
            key: 'params', label: '求解器参数快照',
            children: (
              <pre style={{ background: '#f6f8fa', padding: 12, borderRadius: 6,
                fontSize: 12, maxHeight: 400, overflow: 'auto' }}>
                {JSON.stringify({
                  ...solverParamsObj,
                  metrics_meta: {
                    relaxations: metrics?.relaxations,
                    warnings: metrics?.warnings,
                    solve_seconds: metrics?.solve_seconds,
                    candidate_count: metrics?.candidate_count,
                    status: metrics?.status,
                  },
                }, null, 2)}
              </pre>),
          },
        ]}
      />
      {rtask && (resolveTask) && (
        <div style={{ position: 'fixed', bottom: 24, right: 24, zIndex: 1000, width: 300 }}>
          <Card size="small" title="局部重求解任务">
            <Tag color={rtask.status === 'failed' ? 'red' : 'blue'}>{rtask.status}</Tag>
            <div>{rtask.message || '求解中…'}</div>
          </Card>
        </div>
      )}
    </Space>
  )
}

function VersionDiff({ planId, version }: { planId: number; version: number }) {
  const [snap, setSnap] = useState<null | {
    plan: { title: string }; items: MealItem[] }>(null)
  useEffect(() => {
    api.get(`/api/plans/${planId}/versions/${version}`).then((r) => setSnap(r.data))
  }, [planId, version])
  if (!snap) return <Spin />
  return (
    <List
      size="small" style={{ maxHeight: 460, overflow: 'auto' }}
      header={`快照菜品 ${snap.items.length} 项`}
      dataSource={snap.items}
      renderItem={(i) => (
        <List.Item>
          <Space>
            <Tag>{i.locked ? '锁定' : ''}</Tag>
            第{i.day_index + 1}天 {SLOT_LABELS[i.slot]} {i.dish_name} {i.portion_g}g
            <span style={{ color: '#999' }}>{DISH_TYPE_LABELS[i.detail?.dish_type || '']}</span>
          </Space>
        </List.Item>
      )}
    />
  )
}
