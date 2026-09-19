import { useEffect, useMemo, useState } from 'react'
import {
  Button, Card, Col, Form, Input, InputNumber, Row, Select, Space, Table,
  Typography, App, Divider, Tag,
} from 'antd'
import { ArrowLeftOutlined, DeleteOutlined, PlusOutlined } from '@ant-design/icons'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate, useParams } from 'react-router-dom'
import { api, apiError } from '../api/client'
import { CATEGORY_LABELS, NUT_LABELS } from '../lib/types'
import { useAuthStore } from '../store/auth'

interface RecipeRow { ingredient_id?: number; gross_g: number; cooking_loss_pct: number }

export default function DishEdit() {
  const { id } = useParams()
  const isNew = !id
  const nav = useNavigate()
  const qc = useQueryClient()
  const { message } = App.useApp()
  const role = useAuthStore((s) => s.user?.role)
  const canWrite = role === 'admin' || role === 'nutritionist'

  const [form] = Form.useForm()
  const [recipe, setRecipe] = useState<RecipeRow[]>([])
  const [allergens, setAllergens] = useState<string[]>([])
  const [tags, setTags] = useState<string[]>([])

  const { data: ingredients } = useQuery({
    queryKey: ['ingredients-all'],
    queryFn: async () => (await api.get('/api/ingredients')).data,
  })

  useEffect(() => {
    if (id) {
      api.get(`/api/dishes/${id}`).then(({ data }) => {
        form.setFieldsValue({
          name: data.name, category: data.category,
          iddsi_level: data.iddsi_level, serving_desc: data.serving_desc,
          satisfaction: data.satisfaction, waste_index: data.waste_index,
          active: data.active, note: data.note,
        })
        setAllergens(data.allergens || [])
        setTags(data.tags || [])
        setRecipe((data.recipe || []).map((r: any) => ({
          ingredient_id: r.ingredient_id, gross_g: r.gross_g,
          cooking_loss_pct: r.cooking_loss_pct,
        })))
      })
    }
  }, [id])

  // 实时配方换算
  const { data: preview } = useQuery({
    queryKey: ['recipe-preview', recipe],
    queryFn: async () =>
      (await api.post('/api/dishes/recipe-preview', { recipe })).data,
    enabled: recipe.length > 0,
  })

  const saveMu = useMutation({
    mutationFn: async (payload: any) =>
      isNew ? await api.post('/api/dishes', payload)
            : await api.put(`/api/dishes/${id}`, payload),
    onSuccess: () => {
      message.success(isNew ? '菜品已创建，营养由配方自动换算' : '菜品已更新')
      qc.invalidateQueries({ queryKey: ['dishes'] })
      nav('/dishes')
    },
    onError: (e) => message.error(apiError(e)),
  })

  const ingMap = useMemo(() =>
    Object.fromEntries((ingredients || []).map((i: any) => [i.id, i])),
    [ingredients])

  const onSave = async () => {
    const v = await form.validateFields()
    if (recipe.length === 0) {
      message.warning('请至少添加一条食材配方（营养/成本由配方换算）')
      return
    }
    saveMu.mutate({
      ...v, allergens, tags,
      recipe: recipe.filter((r) => r.ingredient_id),
    })
  }

  const nutrition = preview?.nutrition || {}
  const autoTags = preview?.tags || []
  const autoAllergens = preview?.allergens || []

  return (
    <div className="page-container">
      <Space style={{ marginBottom: 12 }}>
        <Button icon={<ArrowLeftOutlined />} onClick={() => nav('/dishes')}>返回</Button>
        <Typography.Title level={4} style={{ margin: 0 }}>
          {isNew ? '新建菜品' : `编辑菜品`}
        </Typography.Title>
      </Space>

      <Row gutter={16}>
        <Col span={14}>
          <Card title="基础信息" size="small">
            <Form form={form} layout="vertical"
                  initialValues={{
                    category: 'entree', iddsi_level: 7, satisfaction: 3.5,
                    waste_index: 0.1, serving_desc: '每份', active: true,
                  }}
                  disabled={!canWrite}>
              <Row gutter={12}>
                <Col span={10}>
                  <Form.Item name="name" label="菜品名称" rules={[{ required: true }]}>
                    <Input />
                  </Form.Item>
                </Col>
                <Col span={7}>
                  <Form.Item name="category" label="类别">
                    <Select options={Object.entries(CATEGORY_LABELS)
                      .map(([v, l]) => ({ value: v, label: l }))} />
                  </Form.Item>
                </Col>
                <Col span={7}>
                  <Form.Item name="iddsi_level" label="IDDSI 等级">
                    <Select options={[0, 1, 2, 3, 4, 5, 6, 7]
                      .map((n) => ({ value: n, label: `IDDSI ${n}` }))} />
                  </Form.Item>
                </Col>
                <Col span={8}>
                  <Form.Item name="satisfaction" label="喜好度(1-5)">
                    <InputNumber min={1} max={5} step={0.1} style={{ width: '100%' }} />
                  </Form.Item>
                </Col>
                <Col span={8}>
                  <Form.Item name="waste_index" label="预计浪费比例(0-1)">
                    <InputNumber min={0} max={1} step={0.05} style={{ width: '100%' }} />
                  </Form.Item>
                </Col>
                <Col span={8}>
                  <Form.Item name="active" label="状态">
                    <Select options={[{ value: true, label: '启用' },
                                      { value: false, label: '停用' }]} />
                  </Form.Item>
                </Col>
                <Col span={24}>
                  <Form.Item name="note" label="备注">
                    <Input.TextArea rows={2} />
                  </Form.Item>
                </Col>
              </Row>
            </Form>
          </Card>

          <Card title="食材配方（每份投料毛重）" size="small" style={{ marginTop: 16 }}
                extra={<Typography.Text type="secondary" style={{ fontSize: 12 }}>
                  烹饪损失：正数=失重%，负数=吸水增重%</Typography.Text>}>
            <Table size="small" pagination={false} rowKey={(r, i) => `${i}`}
                   dataSource={recipe as any[]}
                   footer={() => canWrite && (
                     <Button block type="dashed" icon={<PlusOutlined />}
                             onClick={() => setRecipe([...recipe,
                               { gross_g: 50, cooking_loss_pct: 0 }])}>
                       添加食材</Button>)}
                   columns={[
                     { title: '食材',
                       render: (_, __, i) => (
                         <Select showSearch style={{ width: '100%' }}
                                 value={recipe[i].ingredient_id}
                                 optionFilterProp="label"
                                 onChange={(v) => {
                                   const nr = [...recipe]; nr[i] = { ...nr[i], ingredient_id: v }
                                   setRecipe(nr) }}
                                 options={(ingredients || []).map((x: any) =>
                                   ({ value: x.id, label: `${x.name}（${x.category}）` }))} />) },
                     { title: '毛重g', dataIndex: 'gross_g', width: 110,
                       render: (v, _, i) => (
                         <InputNumber min={0} value={v} style={{ width: 100 }}
                                      onChange={(x) => {
                                        const nr = [...recipe]
                                        nr[i] = { ...nr[i], gross_g: x || 0 }
                                        setRecipe(nr) }} />) },
                     { title: '损失%', dataIndex: 'cooking_loss_pct', width: 110,
                       render: (v, _, i) => (
                         <InputNumber min={-400} max={100} value={v} style={{ width: 100 }}
                                      onChange={(x) => {
                                        const nr = [...recipe]
                                        nr[i] = { ...nr[i], cooking_loss_pct: x || 0 }
                                        setRecipe(nr) }} />) },
                     { title: '可食量g', width: 90,
                       render: (_, r) => {
                         const ing = ingMap[r.ingredient_id]
                         return ing ? (r.gross_g * ing.edible_pct / 100
                           * (1 - r.cooking_loss_pct / 100)).toFixed(0) : '—' } },
                     { title: '', width: 40,
                       render: (_, __, i) => canWrite && (
                         <Button type="text" danger icon={<DeleteOutlined />}
                                 onClick={() => setRecipe(recipe.filter((_, j) => j !== i))} />) },
                   ]} />
          </Card>
        </Col>

        <Col span={10}>
          <Card title="配方自动换算结果（每份）" size="small">
            <Row gutter={[8, 8]}>
              {Object.entries(NUT_LABELS).map(([k, label]: [string, string]) => (
                <Col span={12} key={k}>
                  <Card size="small" styles={{ body: { padding: 8 } }}>
                    <Typography.Text type="secondary" style={{ fontSize: 11 }}>{label}</Typography.Text>
                    <div className="kpi-num" style={{ fontSize: 18 }}>
                      {(nutrition[k] ?? 0).toFixed(1)}
                    </div>
                  </Card>
                </Col>
              ))}
              <Col span={12}>
                <Card size="small" styles={{ body: { padding: 8 } }}>
                  <Typography.Text type="secondary" style={{ fontSize: 11 }}>成本</Typography.Text>
                  <div className="kpi-num" style={{ fontSize: 18 }}>
                    ¥{preview?.cost?.toFixed?.(2) ?? '0.00'}
                  </div>
                </Card>
              </Col>
              <Col span={12}>
                <Card size="small" styles={{ body: { padding: 8 } }}>
                  <Typography.Text type="secondary" style={{ fontSize: 11 }}>成品重量g</Typography.Text>
                  <div className="kpi-num" style={{ fontSize: 18 }}>
                    {preview?.cooked_weight_g?.toFixed?.(0) ?? '—'}
                  </div>
                </Card>
              </Col>
            </Row>
            <Divider style={{ margin: '10px 0' }} />
            <Typography.Text strong>配方自动识别标签：</Typography.Text>
            <div style={{ marginTop: 6 }}>
              {autoTags.map((t: string) => <Tag key={t} color="blue">{t}</Tag>)}
              {autoAllergens.map((a: string) => <Tag key={a} color="volcano">{a}</Tag>)}
              {!autoTags.length && !autoAllergens.length &&
                <Typography.Text type="secondary">无</Typography.Text>}
            </div>
          </Card>

          <Card title="手工标签与过敏原" size="small" style={{ marginTop: 16 }}>
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              在此补充烹饪类标签（如 fried / pickle / high_sugar 等）
            </Typography.Text>
            <Select mode="tags" style={{ width: '100%', marginTop: 8 }}
                    value={tags} onChange={setTags}
                    placeholder="输入标签后回车，如 fried / pickle / high_sugar / high_purine"
                    options={['fried', 'pickle', 'high_sugar', 'high_sodium',
                      'high_potassium', 'high_phosphorus', 'high_purine',
                      'organ_meat', 'fatty_meat', 'high_vitamin_k', 'strong_broth']
                      .map((t) => ({ value: t, label: t }))} />
            <Typography.Text type="secondary" style={{ fontSize: 12, marginTop: 8, display: 'block' }}>
              额外过敏原（配方未覆盖时手工声明）
            </Typography.Text>
            <Select mode="tags" style={{ width: '100%', marginTop: 8 }}
                    value={allergens} onChange={setAllergens}
                    placeholder="egg / milk / fish / shrimp / peanut / soy / gluten ..." />
          </Card>

          {canWrite && (
            <Button type="primary" block size="large" style={{ marginTop: 16 }}
                    loading={saveMu.isPending} onClick={onSave}>
              {isNew ? '创建菜品' : '保存修改'}
            </Button>
          )}
        </Col>
      </Row>
    </div>
  )
}
