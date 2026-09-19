export interface User {
  id: number
  username: string
  full_name: string
  role: 'admin' | 'nutritionist'
  is_active: boolean
}

export interface Ingredient {
  id?: number
  code: string
  name: string
  category: string
  edible_rate: number
  energy_kcal: number
  protein_g: number
  fat_g: number
  carbs_g: number
  dietary_fiber_g: number
  sodium_mg: number
  potassium_mg: number
  phosphorus_mg: number
  calcium_mg: number
  cholesterol_mg: number
  sugar_g: number
  purine_mg: number
  gi?: number | null
  allergen_tags: string
  tags: string
  unit_cost: number
  is_active: boolean
}

export interface RecipeRow {
  id?: number
  ingredient_id: number
  ingredient_name?: string
  gross_weight_g: number
  cooking_loss_rate: number
  edible_rate?: number
  unit_cost?: number
}

export interface Dish {
  id?: number
  code: string
  name: string
  dish_type: string
  cuisine: string
  portion_g: number
  portion_cost: number
  energy_kcal: number
  protein_g: number
  fat_g: number
  carbs_g: number
  dietary_fiber_g: number
  sodium_mg: number
  potassium_mg: number
  phosphorus_mg: number
  calcium_mg: number
  cholesterol_mg: number
  sugar_g: number
  purine_mg: number
  gi?: number | null
  allergen_tags: string
  tags: string
  iddsi_level: number
  meal_slots: string
  preference_score: number
  waste_rate: number
  is_active: boolean
  recipe?: RecipeRow[]
}

export interface TargetInfo {
  targets: Record<string, [number, number]>
  explanation: string[]
  conflict_notes: string[]
}

export interface Elder {
  id: number
  name: string
  gender: 'male' | 'female'
  birth_date: string
  height_cm: number
  weight_kg: number
  activity_level: string
  chronic_diseases: string
  allergies: string
  iddsi_level: number
  dislikes: string
  religion: string
  medications: string
  nutrition_goal: string
  target_overrides: string
  target_explanation: string
  target?: TargetInfo
  cost_limit_day: number
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface Violation {
  level: 'forbid' | 'warn'
  rule_code: string
  rule_name: string
  rule_type: string
  priority: number
  message: string
  suggestion: string
}

export interface MealItem {
  id?: number
  plan_id?: number
  day_index: number
  meal_date: string
  slot: string
  dish_id: number
  dish_name: string
  portion_g: number
  locked: boolean
  detail?: { cost?: number; dish_type?: string }
}

export interface ScoreBreakdown {
  avg_nutrient_deviation_pct: number
  nutrient_deviation_by_key_pct: Record<string, number>
  total_cost: number
  avg_day_cost: number
  waste_g_est: number
  avg_satisfaction: number
  repeat_extra_count: number
  risk_tag_hits: number
  distinct_dishes: number
  total_items: number
}

export interface PlanMetrics {
  daily_nutrients: Record<string, number>[]
  daily_costs: number[]
  total_cost: number
  score_breakdown: ScoreBreakdown
  relaxations: string[]
  warnings: string[]
  status: string
  objective: number
  candidate_count: number
  solve_seconds: number
  nutrient_check?: Record<string, { avg: number; target: [number, number]; in_range: boolean }>
}

export interface Plan {
  id: number
  elder_id: number
  elder_name?: string
  title: string
  period_type: 'day' | 'week'
  start_date: string
  end_date: string
  status: 'draft' | 'published' | 'archived'
  rule_version: string
  solver_params: string | Record<string, unknown>
  metrics_json?: string
  metrics?: PlanMetrics
  lock_version: number
  created_by: string
  created_at: string
  updated_at: string
  published_at?: string | null
  items: MealItem[]
}

export interface TaskInfo {
  id: number
  task_type: string
  status: 'pending' | 'running' | 'success' | 'failed'
  progress: number
  message: string
  result: { plan_id?: number; infeasible?: boolean; warnings?: string[]; relaxations?: string[] }
  created_by: string
  created_at: string
}

export interface RuleVersion {
  id: number
  version: string
  status: string
  note: string
  rule_count: number
  created_at: string
  published_at?: string | null
}

export interface RuleItem {
  id?: number
  version_id?: number
  code: string
  name: string
  rule_type: string
  subject: string
  action: 'forbid' | 'warn'
  priority: number
  condition: Record<string, unknown>
  message: string
  is_active: boolean
}

export interface AuditLog {
  id: number
  username: string
  action: string
  entity_type: string
  entity_id: string
  detail: Record<string, unknown>
  rule_version: string
  created_at: string
}

export const NUTRIENT_LABELS: Record<string, string> = {
  energy_kcal: '能量(kcal)',
  protein_g: '蛋白质(g)',
  fat_g: '脂肪(g)',
  carbs_g: '碳水(g)',
  dietary_fiber_g: '膳食纤维(g)',
  sodium_mg: '钠(mg)',
  potassium_mg: '钾(mg)',
  phosphorus_mg: '磷(mg)',
  calcium_mg: '钙(mg)',
  cholesterol_mg: '胆固醇(mg)',
  sugar_g: '糖(g)',
  purine_mg: '嘌呤(mg)',
}

export const DISEASE_LABELS: Record<string, string> = {
  diabetes2: '2型糖尿病',
  hypertension: '高血压',
  dyslipidemia: '血脂异常',
  ckd: '慢性肾病',
  gout: '痛风',
  malnutrition: '营养不良',
  sarcopenia: '肌少症',
  osteoporosis: '骨质疏松',
  copd: '慢阻肺',
}

export const IDDSI_LABELS: Record<number, string> = {
  0: '0级 稀薄液体', 1: '1级 微稠液体', 2: '2级 浓稠液体',
  3: '3级 流动糊状', 4: '4级 泥状/糊状', 5: '5级 碎软食',
  6: '6级 软质食', 7: '7级 普通食',
}

export const SLOT_LABELS: Record<string, string> = {
  breakfast: '早餐', lunch: '午餐', dinner: '晚餐',
}

export const DISH_TYPE_LABELS: Record<string, string> = {
  staple: '主食', liquid_staple: '流质主食', meat: '荤菜',
  egg: '蛋类', soy: '豆制品', vegetable: '蔬菜',
  soup: '汤羹', milk: '奶类', fruit: '水果', other: '其他',
}
