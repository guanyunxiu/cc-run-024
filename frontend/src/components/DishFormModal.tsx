import { useEffect, useState } from 'react'
import {
  Modal, Form, Input, Select, InputNumber, Button, Table, Space, App,
  Divider, Tag, Alert,
} from 'antd'
import { DeleteOutlined, PlusOutlined } from '@ant-design/icons'
import { useIngredients, useSaveDish } from '../api/hooks'
import type { Dish, RecipeRow } from '../lib/types'

const DISH_TYPES = [
  ['staple', '主食'], ['liquid_staple', '流质主食'], ['meat', '荤菜'],
  ['egg', '蛋类'], ['soy', '豆制品'], ['vegetable', '蔬菜'],
  ['soup', '汤羹'], ['milk', '奶类'], ['fruit', '水果'],
]

export default function DishFormModal({ dish, onClose }:
  { dish: Dish | null; onClose: () => void }) {
  const [form] = Form.useForm()
  const { data: ings } = useIngredients()
  const save = useSaveDish()
  const { message } = App.useApp()
  const [recipe, setRecipe] = useState<RecipeRow[]>([])

  useEffect(() => {
    if (dish) {
      form.setFieldsValue({
        ...dish,
        meal_slot_list: dish.meal_slots.split(',').filter(Boolean),
      })
      setRecipe((dish.recipe || []).map((r) => ({ ...r })))
    } else {
      form.setFieldsValue({
        meal_slot_list: ['breakfast', 'lunch', 'dinner'],
        portion_g: 200, preference_score: 3.5, waste_rate: 0.08,
        iddsi_level: 6, portion_cost: 0, is_active: true,
      })
    }
  }, [dish, form])

  const onOk = async () => {
    const v = await form.validateFields()
    const body = {
      ...(dish || {}),
      ...v,
      meal_slots: (v.meal_slot_list || []).join(','),
      recipe: recipe
        .filter((r) => r.ingredient_id && r.gross_weight_g > 0)
        .map((r) => ({
          ingredient_id: r.ingredient_id,
          gross_weight_g: r.gross_weight_g,
          cooking_loss_rate: r.cooking_loss_rate || 0,
        })),
    }
    save.mutate(body as Dish, {
      onSuccess: () => { message.success('菜品已保存，营养/成本已重算'); onClose() },
      onError: (e: unknown) => message.error(
        (e as { response?: { data?: { detail?: string } } }).response?.data?.detail || '保存失败'),
    })
  }

  const ingName = (id: number) => ings?.find((x) => x.id === id)?.name || `#${id}`

  return (
    <Modal open title={dish ? `编辑菜品：${dish.name}` : '新建菜品'}
      onCancel={onClose} width={900} onOk={onOk} okText="保存并核算"
      confirmLoading={save.isPending} destroyOnClose>
      <Form form={form} layout="vertical">
        <Space wrap>
          <Form.Item name="code" label="编码" rules={[{ required: true }]}>
            <Input style={{ width: 130 }} />
          </Form.Item>
          <Form.Item name="name" label="菜名" rules={[{ required: true }]}>
            <Input style={{ width: 180 }} />
          </Form.Item>
          <Form.Item name="dish_type" label="类型" rules={[{ required: true }]}>
            <Select style={{ width: 120 }}
              options={DISH_TYPES.map(([v, l]) => ({ value: v, label: l }))} />
          </Form.Item>
          <Form.Item name="iddsi_level" label="IDDSI 质地等级">
            <Select style={{ width: 110 }} options={[0, 1, 2, 3, 4, 5, 6, 7]
              .map((i) => ({ value: i, label: `${i}级` }))} />
          </Form.Item>
          <Form.Item name="meal_slot_list" label="适用餐次">
            <Select mode="multiple" style={{ width: 230 }}
              options={[
                { value: 'breakfast', label: '早餐' },
                { value: 'lunch', label: '午餐' },
                { value: 'dinner', label: '晚餐' },
              ]} />
          </Form.Item>
        </Space>
        <Space wrap>
          <Form.Item name="portion_g" label="一份成品重(g)"><InputNumber min={30} max={1000} /></Form.Item>
          <Form.Item name="portion_cost" label="单价(元,0=按配方核算)">
            <InputNumber min={0} step={0.5} />
          </Form.Item>
          <Form.Item name="preference_score" label="满意度(1-5)">
            <InputNumber min={1} max={5} step={0.1} />
          </Form.Item>
          <Form.Item name="waste_rate" label="浪费率(0-0.8)">
            <InputNumber min={0} max={0.8} step={0.01} />
          </Form.Item>
          <Form.Item name="tags" label="人工标签">
            <Input style={{ width: 240 }} placeholder="high_fat,soft（营养等级标签自动派生）" />
          </Form.Item>
          <Form.Item name="allergen_tags" label="人工过敏原">
            <Input style={{ width: 160 }} placeholder="一般由配方自动聚合" />
          </Form.Item>
        </Space>

        <Divider style={{ margin: '8px 0' }} orientation="left">配方（食材 → 成品营养/成本换算）</Divider>
        <Table
          size="small" pagination={false} rowKey={(r, i) => `${r.ingredient_id}-${i}`}
          dataSource={recipe}
          footer={() => (
            <Button type="dashed" block icon={<PlusOutlined />}
              onClick={() => setRecipe([...recipe,
                { ingredient_id: ings?.[0]?.id || 0, gross_weight_g: 50,
                  cooking_loss_rate: 0 }])}>
              添加食材
            </Button>
          )}
          columns={[
            { title: '食材', width: 280,
              render: (_: unknown, r: RecipeRow) => (
                <Select
                  showSearch style={{ width: 260 }} value={r.ingredient_id || undefined}
                  optionFilterProp="label"
                  options={(ings || []).map((x) => ({ value: x.id!, label: `${x.name}（${x.code}）` }))}
                  onChange={(v) => setRecipe(recipe.map((x, i) =>
                    x === r ? { ...x, ingredient_id: v } : x))}
                  filterOption={(input, opt) =>
                    (opt?.label as string).toLowerCase().includes(input.toLowerCase())}
                />) },
            { title: '投料市品重(g)', width: 150,
              render: (_: unknown, r: RecipeRow) => (
                <InputNumber value={r.gross_weight_g} min={0} step={10}
                  onChange={(v) => setRecipe(recipe.map((x) =>
                    x === r ? { ...x, gross_weight_g: v ?? 0 } : x))} />) },
            { title: '烹饪损失率', width: 150,
              render: (_: unknown, r: RecipeRow) => (
                <InputNumber value={r.cooking_loss_rate} min={-0.8} max={0.95}
                  step={0.05}
                  onChange={(v) => setRecipe(recipe.map((x) =>
                    x === r ? { ...x, cooking_loss_rate: v ?? 0 } : x))} />) },
            { title: '可食部', width: 80,
              render: (_: unknown, r: RecipeRow) =>
                ings?.find((x) => x.id === r.ingredient_id)?.edible_rate ?? '—' },
            { title: '操作', width: 70,
              render: (_: unknown, _r: RecipeRow, i: number) => (
                <Button danger size="small" icon={<DeleteOutlined />}
                  onClick={() => setRecipe(recipe.filter((_, j) => j !== i))} />) },
          ]}
        />
        <Alert style={{ marginTop: 10 }} type="info" showIcon
          message="保存时按「可食重量×(1-损失率)」聚合熟重与营养（吸水菜损失率填负值）；过敏原与身份标签沿配方传播，高钠/高脂等营养等级标签按成品营养阈值自动判定。" />
        {dish && (
          <div style={{ marginTop: 10 }}>
            <Tag color="blue">成品每100g：{dish.energy_kcal}kcal</Tag>
            <Tag>蛋白 {dish.protein_g}g</Tag>
            <Tag>钠 {dish.sodium_mg}mg</Tag>
            <Tag>钾 {dish.potassium_mg}mg</Tag>
            <Tag>磷 {dish.phosphorus_mg}mg</Tag>
            <Tag>成本 ¥{dish.portion_cost}</Tag>
          </div>
        )}
      </Form>
    </Modal>
  )
}
