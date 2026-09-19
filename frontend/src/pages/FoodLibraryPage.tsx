import { useState } from 'react'
import {
  Card, Tabs, Table, Button, Space, Tag, Input, Select, App, Modal, InputNumber,
} from 'antd'
import { PlusOutlined } from '@ant-design/icons'
import {
  useIngredients, useDishes, useSaveIngredient, useSaveDish,
} from '../api/hooks'
import type { Ingredient, Dish } from '../lib/types'
import { DISH_TYPE_LABELS, IDDSI_LABELS } from '../lib/types'
import DishFormModal from '../components/DishFormModal'

export default function FoodLibraryPage() {
  const [tab, setTab] = useState('dishes')
  return (
    <Card>
      <Tabs
        activeKey={tab}
        onChange={setTab}
        items={[
          { key: 'dishes', label: '菜品库', children: <DishesTab /> },
          { key: 'ingredients', label: '食材营养库', children: <IngredientsTab /> },
        ]}
      />
    </Card>
  )
}

function DishesTab() {
  const { data, isLoading } = useDishes()
  const [q, setQ] = useState('')
  const [editing, setEditing] = useState<Dish | null>(null)
  const [creating, setCreating] = useState(false)
  const rows = (data || []).filter((d) =>
    !q || d.name.includes(q) || d.code.toLowerCase().includes(q.toLowerCase()))

  return (
    <>
      <Space style={{ marginBottom: 12 }}>
        <Input.Search placeholder="菜名/编码" allowClear onChange={(e) => setQ(e.target.value)}
          style={{ width: 240 }} />
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setCreating(true)}>
          新建菜品
        </Button>
        <span style={{ color: '#999' }}>成品营养与成本由配方（可食部×烹饪损失）自动聚合</span>
      </Space>
      <Table
        rowKey="id" loading={isLoading} dataSource={rows}
        scroll={{ x: 1200 }} pagination={{ pageSize: 15 }}
        columns={[
          { title: '菜名', dataIndex: 'name', width: 180, fixed: 'left' },
          { title: '类型', dataIndex: 'dish_type', width: 90,
            render: (v: string) => DISH_TYPE_LABELS[v] || v },
          { title: '质地', dataIndex: 'iddsi_level', width: 100,
            render: (v: number) => <Tag color={v <= 5 ? 'blue' : 'default'}>{v}级</Tag> },
          { title: '份量/成本', width: 110,
            render: (_: unknown, r: Dish) => `${r.portion_g}g / ¥${r.portion_cost}` },
          { title: '能量', dataIndex: 'energy_kcal', width: 80,
            render: (v: number) => v.toFixed(0) },
          { title: '蛋白', dataIndex: 'protein_g', width: 70,
            render: (v: number) => v.toFixed(1) },
          { title: '钠', dataIndex: 'sodium_mg', width: 80,
            render: (v: number) => v.toFixed(0) },
          { title: '钾', dataIndex: 'potassium_mg', width: 80,
            render: (v: number) => v.toFixed(0) },
          { title: '磷', dataIndex: 'phosphorus_mg', width: 80,
            render: (v: number) => v.toFixed(0) },
          { title: '标签', dataIndex: 'tags',
            render: (v: string) => <Space size={2} wrap>
              {v.split(',').filter(Boolean).slice(0, 5).map((t) => <Tag key={t}>{t}</Tag>)}
            </Space> },
          { title: '操作', width: 90, fixed: 'right',
            render: (_: unknown, r: Dish) =>
              <Button size="small" onClick={() => setEditing(r)}>编辑</Button> },
        ]}
      />
      {(creating || editing) && (
        <DishFormModal dish={editing} onClose={() => { setCreating(false); setEditing(null) }} />
      )}
    </>
  )
}

const EDITABLE: { key: keyof Ingredient; label: string; step?: number }[] = [
  { key: 'edible_rate', label: '可食部', step: 0.05 },
  { key: 'energy_kcal', label: '能量kcal' },
  { key: 'protein_g', label: '蛋白g', step: 0.1 },
  { key: 'fat_g', label: '脂肪g', step: 0.1 },
  { key: 'carbs_g', label: '碳水g', step: 0.1 },
  { key: 'dietary_fiber_g', label: '纤维g', step: 0.1 },
  { key: 'sodium_mg', label: '钠mg' },
  { key: 'potassium_mg', label: '钾mg' },
  { key: 'phosphorus_mg', label: '磷mg' },
  { key: 'calcium_mg', label: '钙mg' },
  { key: 'cholesterol_mg', label: '胆固醇mg' },
  { key: 'sugar_g', label: '糖g', step: 0.1 },
  { key: 'purine_mg', label: '嘌呤mg' },
  { key: 'gi', label: 'GI' },
  { key: 'unit_cost', label: '元/100g', step: 0.1 },
]

function IngredientsTab() {
  const { data, isLoading } = useIngredients()
  const save = useSaveIngredient()
  const { message } = App.useApp()
  const [q, setQ] = useState('')
  const [cat, setCat] = useState('')
  const [creating, setCreating] = useState(false)
  const cats = [...new Set((data || []).map((x) => x.category))]
  const rows = (data || []).filter((x) =>
    (!q || x.name.includes(q)) && (!cat || x.category === cat))

  const blank: Ingredient = {
    code: '', name: '', category: '谷薯', edible_rate: 1,
    energy_kcal: 0, protein_g: 0, fat_g: 0, carbs_g: 0, dietary_fiber_g: 0,
    sodium_mg: 0, potassium_mg: 0, phosphorus_mg: 0, calcium_mg: 0,
    cholesterol_mg: 0, sugar_g: 0, purine_mg: 0, gi: null,
    allergen_tags: '', tags: '', unit_cost: 0, is_active: true,
  }
  const [form, setForm] = useState<Ingredient>(blank)

  const editableCell = (key: keyof Ingredient, step = 1) => ({
    children: (
      <InputNumber
        size="small" value={form[key] as number} step={step}
        style={{ width: 76 }}
        onChange={(v) => setForm({ ...form, [key]: v ?? 0 })} />
    ),
  })

  return (
    <>
      <Space style={{ marginBottom: 12 }}>
        <Input.Search placeholder="食材名" allowClear onChange={(e) => setQ(e.target.value)}
          style={{ width: 180 }} />
        <Select allowClear placeholder="分类" style={{ width: 130 }} value={cat || undefined}
          onChange={setCat}
          options={cats.map((c) => ({ value: c, label: c }))} />
        <Button type="primary" icon={<PlusOutlined />} onClick={() => { setForm(blank); setCreating(true) }}>
          新建食材
        </Button>
      </Space>
      <Table
        rowKey="id" loading={isLoading} dataSource={rows}
        scroll={{ x: 1200 }} pagination={{ pageSize: 20 }}
        columns={[
          { title: '名称', dataIndex: 'name', width: 140, fixed: 'left' },
          { title: '分类', dataIndex: 'category', width: 80 },
          { title: '能量', dataIndex: 'energy_kcal', width: 70 },
          { title: '蛋白', dataIndex: 'protein_g', width: 70,
            render: (v: number) => v.toFixed(1) },
          { title: '脂肪', dataIndex: 'fat_g', width: 70 },
          { title: '碳水', dataIndex: 'carbs_g', width: 70 },
          { title: '纤维', dataIndex: 'dietary_fiber_g', width: 70 },
          { title: '钠', dataIndex: 'sodium_mg', width: 80 },
          { title: '钾', dataIndex: 'potassium_mg', width: 80 },
          { title: '磷', dataIndex: 'phosphorus_mg', width: 80 },
          { title: '钙', dataIndex: 'calcium_mg', width: 80 },
          { title: '标签', dataIndex: 'tags', width: 140,
            render: (v: string) => <Space size={2} wrap>
              {v.split(',').filter(Boolean).map((t) => <Tag key={t}>{t}</Tag>)}
            </Space> },
          { title: '操作', width: 80, fixed: 'right',
            render: (_: unknown, r: Ingredient) =>
              <Button size="small" onClick={() => setForm(r)}>编辑</Button> },
        ]}
      />
      <Modal
        open={creating}
        title={form.id ? `编辑食材：${form.name}` : '新建食材（每100g可食部）'}
        onCancel={() => setCreating(false)} width={760}
        onOk={() => save.mutate(form, {
          onSuccess: () => { message.success('已保存'); setCreating(false) },
          onError: (e: unknown) => message.error(
            (e as { response?: { data?: { detail?: string } } }).response?.data?.detail || '保存失败'),
        })}
        confirmLoading={save.isPending}
      >
        <Space wrap style={{ marginBottom: 8 }}>
          <Input addonBefore="编码" value={form.code} style={{ width: 180 }}
            onChange={(e) => setForm({ ...form, code: e.target.value })} />
          <Input addonBefore="名称" value={form.name} style={{ width: 180 }}
            onChange={(e) => setForm({ ...form, name: e.target.value })} />
          <Select value={form.category} style={{ width: 120 }}
            onChange={(v) => setForm({ ...form, category: v })}
            options={['谷薯', '蔬菜', '水果', '肉蛋', '水产', '奶豆', '坚果', '油脂', '调味', '汤羹']
              .map((c) => ({ value: c, label: c }))} />
          <Input addonBefore="过敏原标签" value={form.allergen_tags} style={{ width: 220 }}
            placeholder="egg,milk"
            onChange={(e) => setForm({ ...form, allergen_tags: e.target.value })} />
          <Input addonBefore="标签" value={form.tags} style={{ width: 240 }}
            placeholder="pork,high_sodium"
            onChange={(e) => setForm({ ...form, tags: e.target.value })} />
        </Space>
        <Table
          size="small" pagination={false} rowKey="label"
          showHeader={false}
          dataSource={EDITABLE}
          columns={[
            { dataIndex: 'label', width: 110, render: (v: string) => v },
            { render: (_: unknown, r: { key: keyof Ingredient; step?: number }) =>
              editableCell(r.key, r.step || 1).children },
          ]}
        />
      </Modal>
    </>
  )
}
