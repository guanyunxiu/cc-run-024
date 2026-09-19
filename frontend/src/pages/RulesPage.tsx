import { useState, useEffect } from 'react'
import {
  Card, Table, Tag, Button, Space, Modal, Form, Select, Input, InputNumber,
  App, Descriptions, Alert, message,
} from 'antd'
import { PlusOutlined, SendOutlined } from '@ant-design/icons'
import dayjs from 'dayjs'
import {
  useRuleVersions, useRules,
} from '../api/hooks'
import { api } from '../api/client'
import type { RuleItem, RuleVersion } from '../lib/types'
import { useAuthStore } from '../store/auth'

const RULE_TYPES = [
  ['chronic', '慢病禁忌'], ['allergen', '过敏原'], ['religion', '宗教禁忌'],
  ['drug_food', '药食交互'], ['iddsi', '吞咽IDDSI'], ['dislike', '个人忌口'],
]

function RuleModal({ versionId, rule, onClose }:
  { versionId: number; rule: RuleItem | null; onClose: () => void }) {
  const [form] = Form.useForm()
  const { message: msg } = App.useApp()
  useEffect(() => {
    if (rule) form.setFieldsValue({ ...rule,
      tags_any: (rule.condition?.tags_any as string[]) || [],
      tags_all: (rule.condition?.tags_all as string[]) || [],
      disease: rule.condition?.disease, drug: rule.condition?.drug,
      allergen: rule.condition?.allergen, religion: rule.condition?.religion,
      suggestion: rule.condition?.suggestion })
  }, [rule, form])

  const onOk = async () => {
    const v = await form.validateFields()
    const condition: Record<string, unknown> = { tags_any: v.tags_any || [] }
    if (v.tags_all?.length) condition.tags_all = v.tags_all
    if (v.disease) condition.disease = v.disease
    if (v.drug) condition.drug = v.drug
    if (v.allergen) condition.allergen = v.allergen
    if (v.religion) condition.religion = v.religion
    if (v.suggestion) condition.suggestion = v.suggestion
    const body = {
      code: v.code, name: v.name, rule_type: v.rule_type,
      subject: 'dish', action: v.action, priority: v.priority,
      condition, message: v.message, is_active: true,
    }
    const req = rule
      ? api.put(`/api/rules/rules/${rule.id}`, body)
      : api.post(`/api/rules/versions/${versionId}/rules`, body)
    req.then(() => { msg.success('已保存'); onClose() })
      .catch((e) => msg.error(e.response?.data?.detail || '保存失败（已发布版本不可修改）'))
  }

  return (
    <Modal open title={rule ? `编辑规则 ${rule.code}` : '新建规则'}
      onCancel={onClose} onOk={onOk} width={720} okText="保存">
      <Form form={form} layout="vertical" initialValues={{
        rule_type: 'chronic', action: 'forbid', priority: 500,
      }}>
        <Space>
          <Form.Item name="code" label="规则编码" rules={[{ required: true }]}>
            <Input style={{ width: 200 }} placeholder="CHR-HTN-SODIUM" />
          </Form.Item>
          <Form.Item name="name" label="名称" rules={[{ required: true }]}>
            <Input style={{ width: 240 }} />
          </Form.Item>
        </Space>
        <Space>
          <Form.Item name="rule_type" label="类型">
            <Select style={{ width: 150 }}
              options={RULE_TYPES.map(([v, l]) => ({ value: v, label: l }))} />
          </Form.Item>
          <Form.Item name="action" label="动作">
            <Select style={{ width: 120 }} options={[
              { value: 'forbid', label: '硬禁止' }, { value: 'warn', label: '软警告' }]} />
          </Form.Item>
          <Form.Item name="priority" label="优先级（越大越高）">
            <InputNumber min={0} max={2000} />
          </Form.Item>
        </Space>
        <Form.Item noStyle shouldUpdate={(a, b) => a.rule_type !== b.rule_type}>
          {() => {
            const t = form.getFieldValue('rule_type')
            if (t === 'chronic') return (
              <Form.Item name="disease" label="适用疾病代码">
                <Input placeholder="hypertension / diabetes2 / ckd ..." />
              </Form.Item>)
            if (t === 'drug_food') return (
              <Form.Item name="drug" label="药物代码">
                <Input placeholder="warfarin / mao_i / acei ..." />
              </Form.Item>)
            if (t === 'allergen') return (
              <Form.Item name="allergen" label="过敏原代码">
                <Input placeholder="peanut / egg / seafood ..." />
              </Form.Item>)
            if (t === 'religion') return (
              <Form.Item name="religion" label="宗教代码">
                <Input placeholder="islam / vegetarian / buddhist" />
              </Form.Item>)
            return null
          }}
        </Form.Item>
        <Form.Item name="tags_any" label="命中标签（任一命中即触发）">
          <Select mode="tags" style={{ width: '100%' }} placeholder="high_sodium, pork ..." />
        </Form.Item>
        <Form.Item name="message" label="提示信息">
          <Input.TextArea rows={2} />
        </Form.Item>
        <Form.Item name="suggestion" label="替换建议">
          <Input />
        </Form.Item>
      </Form>
    </Modal>
  )
}

function VersionPanel({ version }: { version: RuleVersion }) {
  const { data: rules, isLoading, refetch } = useRules(version.id)
  const [editing, setEditing] = useState<RuleItem | null>(null)
  const [creating, setCreating] = useState(false)
  const user = useAuthStore((s) => s.user)
  const published = version.status === 'published'
  const archived = version.status === 'archived'
  const readonly = published || archived || user?.role !== 'admin'

  const publish = () => api.post(`/api/rules/versions/${version.id}/publish`)
    .then(() => { message.success('版本已发布，旧发布版本已归档'); refetch() })
    .catch((e) => message.error(e.response?.data?.detail || '发布失败'))

  const remove = (r: RuleItem) => Modal.confirm({
    title: `删除规则 ${r.code}？`,
    onOk: () => api.delete(`/api/rules/rules/${r.id}`).then(() => {
      message.success('已删除'); refetch()
    }).catch((e) => message.error(e.response?.data?.detail || '删除失败')),
  })

  return (
    <>
      <Descriptions size="small" column={4} bordered style={{ marginBottom: 12 }}>
        <Descriptions.Item label="版本号">{version.version}</Descriptions.Item>
        <Descriptions.Item label="状态">
          <Tag color={published ? 'green' : archived ? 'default' : 'gold'}>
            {published ? '已发布' : archived ? '已归档' : '草稿'}
          </Tag>
        </Descriptions.Item>
        <Descriptions.Item label="规则数">{version.rule_count}</Descriptions.Item>
        <Descriptions.Item label="更新时间">
          {dayjs(version.created_at).format('YYYY-MM-DD HH:mm')}
        </Descriptions.Item>
        <Descriptions.Item label="说明" span={4}>{version.note || '—'}</Descriptions.Item>
      </Descriptions>
      {readonly && user?.role !== 'admin' && (
        <Alert type="info" showIcon style={{ marginBottom: 10 }}
          message="仅管理员可编辑规则；已发布/归档版本为只读，需新建版本后调整。" />
      )}
      <Space style={{ marginBottom: 10 }}>
        {!readonly && (
          <>
            <Button type="primary" icon={<PlusOutlined />}
              onClick={() => setCreating(true)}>新建规则</Button>
            <Button type="primary" ghost icon={<SendOutlined />} onClick={publish}>
              发布此版本
            </Button>
          </>
        )}
        <Button onClick={() => refetch()}>刷新</Button>
      </Space>
      <Table
        rowKey="id" loading={isLoading} pagination={false} size="small"
        dataSource={rules || []}
        columns={[
          { title: '优先级', dataIndex: 'priority', width: 80, sorter: (a, b) =>
            a.priority - b.priority, defaultSortOrder: 'descend' },
          { title: '编码', dataIndex: 'code', width: 200 },
          { title: '名称', dataIndex: 'name', width: 180 },
          { title: '类型', dataIndex: 'rule_type', width: 100,
            render: (v: string) =>
              ({ chronic: '慢病', allergen: '过敏', religion: '宗教',
                drug_food: '药食', iddsi: '吞咽' } as Record<string, string>)[v] || v },
          { title: '动作', dataIndex: 'action', width: 80,
            render: (v: string) => <Tag color={v === 'forbid' ? 'red' : 'orange'}>
              {v === 'forbid' ? '禁止' : '警告'}</Tag> },
          { title: '条件', render: (_: unknown, r: RuleItem) => (
            <Space size={2} wrap>
              {Object.entries(r.condition).map(([k, v]) =>
                <Tag key={k}>{k}: {JSON.stringify(v)}</Tag>)}
            </Space>) },
          { title: '操作', width: 130,
            render: (_: unknown, r: RuleItem) => !readonly && (
              <Space>
                <Button size="small" onClick={() => setEditing(r)}>编辑</Button>
                <Button size="small" danger onClick={() => remove(r)}>删除</Button>
              </Space>) },
        ]}
      />
      {(creating || editing) && (
        <RuleModal versionId={version.id} rule={editing}
          onClose={() => { setCreating(false); setEditing(null); refetch() }} />
      )}
    </>
  )
}

export default function RulesPage() {
  const { data: versions, refetch } = useRuleVersions()
  const [active, setActive] = useState<string | undefined>(undefined)
  const [creating, setCreating] = useState(false)
  const user = useAuthStore((s) => s.user)
  const [form] = Form.useForm()

  useEffect(() => {
    if (versions?.length && !active) setActive(String(versions[0].id))
  }, [versions, active])

  const current = versions?.find((v) => String(v.id) === active)

  return (
    <Card
      title="禁忌规则（JSON 规则表 + Python 校验函数，带版本与优先级）"
      extra={user?.role === 'admin' && (
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setCreating(true)}>
          新建规则版本
        </Button>)}
    >
      <Space style={{ marginBottom: 12 }}>
        <span>选择版本：</span>
        <Select style={{ width: 260 }} value={active} onChange={setActive}
          options={(versions || []).map((v) => ({
            value: String(v.id),
            label: `${v.version}（${v.status}，${v.rule_count}条）`,
          }))} />
      </Space>
      {current && <VersionPanel key={current.id} version={current} />}
      <Modal
        open={creating} title="新建规则版本"
        onCancel={() => setCreating(false)}
        onOk={() => form.validateFields().then((v) =>
          api.post('/api/rules/versions', null, { params: {
            version: v.version, note: v.note } })
            .then(() => { message.success('草稿版本已创建'); setCreating(false); refetch() })
            .catch((e) => message.error(e.response?.data?.detail || '创建失败')))}
      >
        <Form form={form} layout="vertical" initialValues={{
          version: dayjs().format('YYYY.MM.') + '2', note: '' }}>
          <Form.Item name="version" label="版本号" rules={[{ required: true }]}>
            <Input placeholder="2026.10.1" />
          </Form.Item>
          <Form.Item name="note" label="变更说明">
            <Input.TextArea rows={3} />
          </Form.Item>
        </Form>
      </Modal>
    </Card>
  )
}
