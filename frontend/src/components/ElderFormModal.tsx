import { useEffect, useState } from 'react'
import {
  Modal, Form, Input, Select, InputNumber, DatePicker, Button,
  Alert, Divider, Collapse, Table, Tag, Space, App,
} from 'antd'
import dayjs from 'dayjs'
import { useSaveElder, usePreviewTargets } from '../api/hooks'
import type { Elder, TargetInfo } from '../lib/types'
import { DISEASE_LABELS } from '../lib/types'

const ACTIVITY = [
  ['bedridden', '卧床'], ['sedentary', '久坐少动'], ['light', '轻度活动'], ['moderate', '中度活动'],
]
const GOALS = [
  ['maintain', '维持体重'], ['gain', '增重'], ['lose', '减重'], ['malnutrition', '营养不良干预'],
]
const ALLERGENS = [
  ['peanut', '花生'], ['seafood', '甲壳类'], ['fish', '鱼类'], ['egg', '蛋类'],
  ['milk', '乳制品'], ['nuts', '树坚果'], ['soy', '大豆'], ['wheat', '小麦/麸质'],
  ['sesame', '芝麻'],
]
const RELIGION = [
  ['none', '无'], ['islam', '清真/伊斯兰'], ['vegetarian', '蛋奶素'], ['buddhist', '佛教全素'],
]
const MEDS = [
  ['warfarin', '华法林'], ['mao_i', '单胺氧化酶抑制剂'], ['levodopa', '左旋多巴'],
  ['acei', 'ACEI/保钾利尿剂'],
]
const NUTRIENT_CN: Record<string, string> = {
  energy_kcal: '能量', protein_g: '蛋白质', fat_g: '脂肪', carbs_g: '碳水',
  dietary_fiber_g: '膳食纤维', sodium_mg: '钠', potassium_mg: '钾',
  phosphorus_mg: '磷', calcium_mg: '钙', cholesterol_mg: '胆固醇',
  sugar_g: '糖', purine_mg: '嘌呤',
}

export default function ElderFormModal({ elder, onClose }:
  { elder: Elder | null; onClose: () => void }) {
  const [form] = Form.useForm()
  const save = useSaveElder()
  const preview = usePreviewTargets()
  const { message } = App.useApp()
  const [target, setTarget] = useState<TargetInfo | null>(null)

  useEffect(() => {
    if (elder) {
      let overrides: Record<string, number> = {}
      try { overrides = JSON.parse(elder.target_overrides || '{}') } catch { /* noop */ }
      form.setFieldsValue({
        ...elder,
        birth_date: dayjs(elder.birth_date),
        chronic_list: elder.chronic_diseases.split(',').filter(Boolean),
        allergy_list: elder.allergies.split(',').filter(Boolean),
        med_list: elder.medications.split(',').filter(Boolean),
        overrides,
      })
      try { setTarget(JSON.parse(elder.target_explanation)) } catch { /* noop */ }
    }
  }, [elder, form])

  const collect = async () => {
    const v = await form.validateFields()
    const overridesArr: { key: string; value: number }[] = v.overrides || []
    const target_overrides: Record<string, number> = {}
    overridesArr.forEach((o) => {
      if (o?.key && o.value != null) target_overrides[o.key] = Number(o.value)
    })
    return {
      ...v,
      birth_date: v.birth_date.format('YYYY-MM-DD'),
      chronic_diseases: (v.chronic_list || []).join(','),
      allergies: (v.allergy_list || []).join(','),
      medications: (v.med_list || []).join(','),
      target_overrides,
    }
  }

  const doPreview = async () => {
    const b = await collect()
    preview.mutate(b, {
      onSuccess: (d) => setTarget(d),
      onError: (e: unknown) => message.error(
        (e as { response?: { data?: { detail?: string } } }).response?.data?.detail || '试算失败'),
    })
  }

  const onOk = async () => {
    const b = await collect()
    save.mutate({ ...(elder || {}), ...b } as Elder, {
      onSuccess: () => { message.success(elder ? '已保存' : '档案已创建'); onClose() },
      onError: (e: unknown) => message.error(
        (e as { response?: { data?: { detail?: string } } }).response?.data?.detail || '保存失败'),
    })
  }

  return (
    <Modal
      open title={elder ? `编辑档案：${elder.name}` : '新建老人档案'}
      onCancel={onClose} width={820}
      onOk={onOk} confirmLoading={save.isPending} okText="保存"
      destroyOnClose
    >
      <Form form={form} layout="vertical" initialValues={{
        gender: 'male', activity_level: 'sedentary', nutrition_goal: 'maintain',
        religion: 'none', iddsi_level: 7, cost_limit_day: 35, height_cm: 165,
        weight_kg: 60, birth_date: dayjs('1945-01-01'), overrides: {},
      }}>
        <Space size={16} wrap>
          <Form.Item name="name" label="姓名" rules={[{ required: true }]}>
            <Input style={{ width: 140 }} />
          </Form.Item>
          <Form.Item name="gender" label="性别">
            <Select style={{ width: 90 }} options={[
              { value: 'male', label: '男' }, { value: 'female', label: '女' }]} />
          </Form.Item>
          <Form.Item name="birth_date" label="出生日期" rules={[{ required: true }]}>
            <DatePicker style={{ width: 150 }} />
          </Form.Item>
          <Form.Item name="height_cm" label="身高(cm)"><InputNumber min={100} max={230} /></Form.Item>
          <Form.Item name="weight_kg" label="体重(kg)"><InputNumber min={25} max={200} step={0.5} /></Form.Item>
          <Form.Item name="activity_level" label="活动量">
            <Select style={{ width: 120 }} options={ACTIVITY.map(([v, l]) =>
              ({ value: v, label: l }))} />
          </Form.Item>
        </Space>
        <Form.Item name="chronic_list" label="慢病（可多选，系统自动调解多病共存冲突）">
          <Select mode="multiple" allowClear style={{ width: '100%' }}
            options={Object.entries(DISEASE_LABELS).map(([v, l]) => ({ value: v, label: l }))} />
        </Form.Item>
        <Space size={16} wrap style={{ width: '100%' }}>
          <Form.Item name="allergy_list" label="过敏原">
            <Select mode="multiple" allowClear style={{ width: 300 }}
              options={ALLERGENS.map(([v, l]) => ({ value: v, label: l }))} />
          </Form.Item>
          <Form.Item name="iddsi_level" label="吞咽 IDDSI 等级">
            <Select style={{ width: 170 }} options={[0, 1, 2, 3, 4, 5, 6, 7].map((i) =>
              ({ value: i, label: `${i} 级` }))} />
          </Form.Item>
          <Form.Item name="religion" label="宗教/饮食">
            <Select style={{ width: 140 }}
              options={RELIGION.map(([v, l]) => ({ value: v, label: l }))} />
          </Form.Item>
        </Space>
        <Space size={16} wrap style={{ width: '100%' }}>
          <Form.Item name="med_list" label="在用药物（药食交互）">
            <Select mode="multiple" allowClear style={{ width: 360 }}
              options={MEDS.map(([v, l]) => ({ value: v, label: l }))} />
          </Form.Item>
          <Form.Item name="nutrition_goal" label="营养目标">
            <Select style={{ width: 160 }}
              options={GOALS.map(([v, l]) => ({ value: v, label: l }))} />
          </Form.Item>
          <Form.Item name="cost_limit_day" label="日餐费上限(元)">
            <InputNumber min={5} max={200} step={1} />
          </Form.Item>
        </Space>
        <Form.Item name="dislikes" label="忌口（分号分隔，如：香菜；动物内脏）">
          <Input placeholder="香菜;动物内脏" />
        </Form.Item>

        <Space>
          <Button loading={preview.isPending} onClick={doPreview}>
            实时试算营养目标
          </Button>
          <span style={{ color: '#999' }}>根据多病共存自动计算，保存前可试算查看依据</span>
        </Space>

        {target && (
          <div style={{ marginTop: 12 }}>
            {target.conflict_notes.length > 0 && (
              <Alert
                style={{ marginBottom: 8 }} type="warning" showIcon
                message="检测到多病共存目标冲突，已按临床优先级调解"
                description={
                  <ul style={{ margin: 0, paddingLeft: 18 }}>
                    {target.conflict_notes.map((n, i) => <li key={i}>{n}</li>)}
                  </ul>}
              />
            )}
            <Collapse
              defaultActiveKey={['t']}
              items={[{
                key: 't', label: `个体化营养目标（${Object.keys(target.targets).length} 项）`,
                children: (
                  <Table
                    size="small" pagination={false}
                    rowKey={(r) => r[0]}
                    dataSource={Object.entries(target.targets)}
                    columns={[
                      { title: '营养素', dataIndex: '0', width: 130,
                        render: (v: string) => NUTRIENT_CN[v] || v },
                      { title: '目标下限', render: (_: unknown, r: [string, [number, number]]) =>
                        r[1][0] },
                      { title: '目标上限', render: (_: unknown, r: [string, [number, number]]) =>
                        r[1][1] },
                    ]}
                  />),
              }, {
                key: 'e', label: '目标计算依据（可解释链）',
                children: (
                  <ul style={{ margin: 0, paddingLeft: 18, fontSize: 13 }}>
                    {target.explanation.map((x, i) => <li key={i}>{x}</li>)}
                  </ul>),
              }]}
            />
          </div>
        )}
        <Divider style={{ margin: '10px 0' }} />
        <Collapse
          items={[{
            key: 'o', label: '手工目标覆盖（营养师权威，可选）',
            children: (
              <Form.List name="overrides">
                {(fields, { add, remove }) => (
                  <>
                    {fields.map((f) => (
                      <Space key={f.key} align="baseline">
                        <Form.Item {...f} name={[f.name, 'key']}
                          rules={[{ required: true }]}>
                          <Select style={{ width: 150 }} placeholder="营养素"
                            options={Object.entries(NUTRIENT_CN).map(([v, l]) =>
                              ({ value: v, label: l }))} />
                        </Form.Item>
                        <Form.Item {...f} name={[f.name, 'value']}
                          rules={[{ required: true }]}>
                          <InputNumber placeholder="目标值" />
                        </Form.Item>
                        <Button danger size="small" onClick={() => remove(f.name)}>删除</Button>
                      </Space>
                    ))}
                    <Button type="dashed" onClick={() => add({ key: 'energy_kcal', value: 1800 })}
                      icon={<span>＋</span>}>添加覆盖项</Button>
                  </>
                )}
              </Form.List>
            ),
          }]}
        />
        {elder && <Tag>id={elder.id}</Tag>}
      </Form>
    </Modal>
  )
}
