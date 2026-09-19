import { useMemo, useState } from 'react'
import {
  DndContext, DragOverlay, PointerSensor, useSensor, useSensors,
  useDroppable, useDraggable, type DragStartEvent, type DragEndEvent,
} from '@dnd-kit/core'
import { Tag, Tooltip, Space, Typography, Badge } from 'antd'
import { LockOutlined, DeleteOutlined, WarningFilled, StopFilled } from '@ant-design/icons'
import type { Dish, MealItem, Violation } from '../lib/types'
import { SLOT_LABELS, DISH_TYPE_LABELS } from '../lib/types'

export function PaletteItem({ dish }: { dish: Dish }) {
  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({
    id: `palette-${dish.id}`,
  })
  return (
    <div
      ref={setNodeRef} {...listeners} {...attributes}
      style={{
        border: '1px solid #d6e0ec', borderRadius: 6, padding: '4px 8px',
        marginBottom: 6, background: isDragging ? '#e8f2ff' : '#fff',
        cursor: 'grab', fontSize: 12,
      }}
    >
      <Space size={4}>
        <Tag style={{ marginInlineEnd: 0 }}>{dish.iddsi_level}级</Tag>
        <span>{dish.name}</span>
      </Space>
      <div style={{ color: '#999' }}>
        {DISH_TYPE_LABELS[dish.dish_type] || dish.dish_type} · ¥{dish.portion_cost}
      </div>
    </div>
  )
}

function DropCell({ day, slot, selected, children, onClick }:
  { day: number; slot: string; selected: boolean
    children: React.ReactNode; onClick: () => void }) {
  const { setNodeRef, isOver } = useDroppable({ id: `${day}-${slot}` })
  return (
    <div
      ref={setNodeRef} onClick={onClick}
      style={{
        minHeight: 96, background: isOver ? '#e8f2ff' : selected ? '#f0f8ff' : '#fafcff',
        border: selected ? '1px solid #2f6fb0' : '1px dashed #c4d4e6',
        borderRadius: 6, padding: 6,
      }}
    >
      {children}
    </div>
  )
}

function PortionEditor({ value, disabled, onChange }:
  { value: number; disabled: boolean; onChange: (g: number) => void }) {
  const [editing, setEditing] = useState(false)
  if (editing && !disabled) {
    return (
      <input
        autoFocus type="number" defaultValue={value}
        style={{ width: 56, fontSize: 11 }}
        onBlur={(e) => {
          const raw = Number(e.target.value)
          if (!Number.isNaN(raw)) {
            const g = Math.max(30, Math.min(300, Math.round(raw / 30) * 30))
            onChange(g)
          }
          setEditing(false)
        }}
      />
    )
  }
  return (
    <span onDoubleClick={() => !disabled && setEditing(true)}
      style={{ borderBottom: '1px dotted #bbb', cursor: disabled ? 'default' : 'text' }}>
      {value}g{disabled ? '' : ' ·双击改'}
    </span>
  )
}

function CardRow({ itemKey, item, dish, violations, onRemove, onLock, onPortion }:
  { itemKey: string; item: MealItem; dish?: Dish; violations: Violation[]
    onRemove: () => void; onLock: () => void; onPortion: (g: number) => void }) {
  const { attributes, listeners, setNodeRef, transform, isDragging } = useDraggable({
    id: itemKey, disabled: item.locked,
  })
  const style = transform ? {
    transform: `translate(${transform.x}px, ${transform.y}px)`, zIndex: 1000,
  } : undefined
  const forbid = violations.some((v) => v.level === 'forbid')
  const warn = violations.some((v) => v.level === 'warn')
  const tip = violations.length
    ? violations.map((v) =>
        `[${v.level === 'forbid' ? '禁止' : '警告'}] ${v.rule_name}：${v.message}`
        + (v.suggestion ? `（建议：${v.suggestion}）` : '')).join('\n')
    : (dish ? `${DISH_TYPE_LABELS[dish.dish_type] || dish.dish_type} · ${dish.iddsi_level}级 · ¥${dish.portion_cost}` : '')
  return (
    <Tooltip title={tip} placement="left" color={forbid ? '#e5575e' : undefined}>
      <div
        ref={setNodeRef} {...listeners} {...attributes}
        style={{
          border: `1px solid ${forbid ? '#e5575e' : warn ? '#e6a23c' : '#d6e0ec'}`,
          background: forbid ? '#fff1f0' : warn ? '#fffbe6' : '#fff',
          borderRadius: 6, padding: '3px 8px', marginBottom: 6,
          cursor: item.locked ? 'default' : 'grab',
          opacity: isDragging ? 0.5 : 1, fontSize: 12,
          boxShadow: '0 1px 2px rgba(0,0,0,0.05)', ...style,
        }}
      >
        <Space size={4} style={{ width: '100%', justifyContent: 'space-between' }}>
          <Space size={3}>
            {item.locked && <LockOutlined style={{ color: '#2f6fb0' }} />}
            {forbid ? <StopFilled style={{ color: '#e5575e' }} />
              : warn ? <WarningFilled style={{ color: '#e6a23c' }} /> : null}
            <span>{item.dish_name}</span>
          </Space>
          <Space size={4}>
            <a onPointerDown={(e) => e.stopPropagation()}
              onClick={(e) => { e.stopPropagation(); onLock() }}
              style={{ fontSize: 11 }}>{item.locked ? '解锁' : '锁定'}</a>
            <a onPointerDown={(e) => e.stopPropagation()}
              onClick={(e) => { e.stopPropagation(); onRemove() }}>
              <DeleteOutlined />
            </a>
          </Space>
        </Space>
        <div style={{ color: '#888' }} onPointerDown={(e) => e.stopPropagation()}>
          <PortionEditor value={item.portion_g} disabled={item.locked} onChange={onPortion} />
        </div>
      </div>
    </Tooltip>
  )
}

export default function PlanEditor({
  days, slots, items, dishes, violationsByDish, selectedCellKey,
  onSelectCell, onChange,
}: {
  days: number
  slots: string[]
  items: MealItem[]
  dishes: Record<number, Dish>
  violationsByDish: Record<number, Violation[]>
  selectedCellKey: string | null
  onSelectCell: (key: string | null) => void
  onChange: (items: MealItem[]) => void
}) {
  const [activeId, setActiveId] = useState<string | null>(null)
  const sensors = useSensors(useSensor(PointerSensor, {
    activationConstraint: { distance: 4 },
  }))

  // 稳定 key：优先数据库 id，新增项用 index 兜底
  const keyOf = (it: MealItem, idx: number) => it.id ? `item-${it.id}` : `tmp-${idx}`
  const byCell = useMemo(() => {
    const m: Record<string, { key: string; item: MealItem }[]> = {}
    items.forEach((it, idx) => {
      const k = `${it.day_index}-${it.slot}`
      ;(m[k] ||= []).push({ key: keyOf(it, idx), item: it })
    })
    return m
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [items])

  const activeContext = useMemo(() => {
    if (!activeId) return null
    if (activeId.startsWith('palette-')) {
      const did = Number(activeId.replace('palette-', ''))
      return dishes[did] ? { kind: 'palette' as const, dish: dishes[did] } : null
    }
    const idx = items.findIndex((it, i) => keyOf(it, i) === activeId)
    return idx >= 0 ? { kind: 'item' as const, item: items[idx] } : null
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeId, items, dishes])

  const onDragStart = (e: DragStartEvent) => setActiveId(String(e.active.id))

  const onDragEnd = (e: DragEndEvent) => {
    setActiveId(null)
    const over = e.over?.id ? String(e.over.id) : null
    if (!over || !activeContext) return
    const [dayStr, slot] = over.split('-')
    const day = Number(dayStr)
    if (activeContext.kind === 'item') {
      const src = activeContext.item
      if (src.locked) return
      if (src.day_index === day && src.slot === slot) return
      onChange(items.map((it) =>
        it === src ? { ...it, day_index: day, slot, locked: false } : it))
    }
  }

  const removeItem = (target: MealItem) => onChange(items.filter((it) => it !== target))
  const toggleLock = (target: MealItem) =>
    onChange(items.map((it) => (it === target ? { ...it, locked: !it.locked } : it)))
  const setPortion = (target: MealItem, g: number) =>
    onChange(items.map((it) => (it === target ? { ...it, portion_g: g } : it)))

  return (
    <DndContext sensors={sensors} onDragStart={onDragStart} onDragEnd={onDragEnd}>
      <div style={{ display: 'grid',
        gridTemplateColumns: `64px repeat(${slots.length}, 1fr)`, gap: 8 }}>
        <div />
        {slots.map((s) => (
          <div key={s} style={{ fontWeight: 600, textAlign: 'center' }}>{SLOT_LABELS[s]}</div>
        ))}
        {Array.from({ length: days }).flatMap((_, d) => [
          <div key={`h${d}`} style={{ fontWeight: 600, display: 'flex',
            alignItems: 'center', justifyContent: 'center',
            background: '#eef4fb', borderRadius: 6 }}>
            <div>第{d + 1}天</div>
          </div>,
          ...slots.map((slot) => {
            const cellKey = `${d}-${slot}`
            const cellItems = byCell[cellKey] || []
            const forbidCount = cellItems.filter((c) =>
              violationsByDish[c.item.dish_id]?.some((v) => v.level === 'forbid')).length
            return (
              <div key={cellKey} style={{ position: 'relative' }}>
                {forbidCount > 0 && (
                  <Tag color="red" style={{ position: 'absolute', top: -8, right: 4, zIndex: 2 }}>
                    {forbidCount} 项硬冲突
                  </Tag>
                )}
                <DropCell day={d} slot={slot}
                  selected={selectedCellKey === cellKey}
                  onClick={() => onSelectCell(
                    selectedCellKey === cellKey ? null : cellKey)}>
                  {cellItems.map(({ key, item }) => (
                    <CardRow
                      key={key} itemKey={key} item={item} dish={dishes[item.dish_id]}
                      violations={violationsByDish[item.dish_id] || []}
                      onRemove={() => removeItem(item)}
                      onLock={() => toggleLock(item)}
                      onPortion={(g) => setPortion(item, g)}
                    />
                  ))}
                  <div style={{ color: '#9ab', fontSize: 11, textAlign: 'center', marginTop: 2 }}>
                    拖拽 / 点击加菜
                  </div>
                </DropCell>
              </div>
            )
          }),
        ])}
      </div>
      <DragOverlay dropAnimation={null}>
        {activeContext?.kind === 'palette'
          ? <div style={{ background: '#fff', border: '1px solid #2f6fb0',
              borderRadius: 6, padding: '2px 8px', fontSize: 12 }}>
              {activeContext.dish?.name}
            </div>
          : activeContext?.kind === 'item'
            ? <div style={{ background: '#fff', border: '1px solid #2f6fb0',
                borderRadius: 6, padding: '2px 8px', fontSize: 12 }}>
                {activeContext.item.dish_name}
              </div>
            : null}
      </DragOverlay>
    </DndContext>
  )
}
