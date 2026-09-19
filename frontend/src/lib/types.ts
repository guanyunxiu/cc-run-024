export interface Resident {
  id: number
  name: string
  gender: string
  age: number
  height_cm: number
  weight_kg: number
  activity_level: string
  swallowing_level: number
  chronic_conditions: string[]
  allergies: string[]
  dislikes: string[]
  religion: string
  medications: string[]
  nutrition_goal_type: string
  custom_targets: Record<string, number>
  targets: TargetSnapshot
  note?: string
  version: number
  applicable_rules?: ApplicableRule[]
}

export interface NutSpec {
  min?: number
  max?: number
  target?: number
}

export interface TargetSnapshot {
  targets: Record<string, NutSpec>
  conflicts: { nutrient: string; topic: string; resolution: string }[]
  assumptions: string[]
  bmr: number
  tdee: number
  bmi: number
}

export interface ApplicableRule {
  code: string
  name: string
  type: string
  severity: string
  priority: number
  version: string
  rationale: string
  params: Record<string, any>
}

export interface Dish {
  id: number
  name: string
  category: string
  iddsi_level: number
  serving_desc: string
  energy_kcal: number
  protein_g: number
  fat_g: number
  carb_g: number
  sodium_mg: number
  potassium_mg: number
  phosphorus_mg: number
  fiber_g: number
  calcium_mg: number
  vitamin_k_ug?: number
  cost: number
  allergens: string[]
  tags: string[]
  satisfaction: number
  waste_index: number
  active: boolean
  note?: string
  recipe?: RecipeItem[]
  check?: { hard: any[]; soft: any[]; eligible: boolean }
}

export interface RecipeItem {
  id?: number
  ingredient_id: number
  gross_g: number
  cooking_loss_pct: number
  note?: string
}

export interface Ingredient {
  id: number
  name: string
  category: string
  edible_pct: number
  energy_kcal: number
  protein_g: number
  fat_g: number
  carb_g: number
  sodium_mg: number
  potassium_mg: number
  phosphorus_mg: number
  fiber_g: number
  calcium_mg: number
  vitamin_k_ug: number
  unit_cost: number
  allergens: string[]
  tags: string[]
  note?: string
}

export interface Rule {
  id?: number
  code: string
  name: string
  rule_type: string
  severity: string
  priority: number
  version: string
  active: boolean
  params: Record<string, any>
  rationale: string
}

export interface MenuItem {
  id?: number
  day_index: number
  slot: string
  line: string
  dish_id: number
  dish_name: string
  category: string
  iddsi_level: number
  cost: number
  locked: boolean
  locked_by?: string
}

export interface PlanScore {
  objective?: number
  avg_attainment_pct: number
  attainment: Record<string, number>
  avg_satisfaction: number
  estimated_waste_cost: number
  total_cost: number
  avg_cost_per_day: number
  distinct_dishes: number
  soft_violation_count: number
  status: string
  solve_time_sec: number
}

export interface Plan {
  id: number
  name: string
  resident_id: number
  start_date: string
  days: number
  status: string
  budget_per_day: number
  version: number
  targets_snapshot: TargetSnapshot
  rule_version: string
  solver_params: any
  score: PlanScore
  totals: any
  created_by: string
  created_at: string
  published_at?: string
  items: MenuItem[]
}

export interface SolveTask {
  id: number
  task_type: string
  plan_id: number
  resident_id: number
  status: 'pending' | 'running' | 'success' | 'failed'
  progress: number
  message: string
  error: string
  result: any
  created_at: string
}

export interface Conflict {
  day_index: number
  slot: string
  line?: string
  dish_name?: string
  rule_code?: string
  rule_name?: string
  severity?: string
  message: string
  rationale?: string
}

export const NUTRIENTS = [
  'energy_kcal', 'protein_g', 'fat_g', 'carb_g', 'sodium_mg',
  'potassium_mg', 'phosphorus_mg', 'fiber_g', 'calcium_mg',
]

export const NUT_LABELS: Record<string, string> = {
  energy_kcal: '能量(kcal)',
  protein_g: '蛋白质(g)',
  fat_g: '脂肪(g)',
  carb_g: '碳水(g)',
  sodium_mg: '钠(mg)',
  potassium_mg: '钾(mg)',
  phosphorus_mg: '磷(mg)',
  fiber_g: '纤维(g)',
  calcium_mg: '钙(mg)',
}

export const SLOT_LABELS: Record<string, string> = {
  breakfast: '早餐',
  morning_snack: '上午加餐',
  lunch: '午餐',
  afternoon_snack: '下午加餐',
  dinner: '晚餐',
}

export const SLOT_ORDER = ['breakfast', 'morning_snack', 'lunch', 'afternoon_snack', 'dinner']

export const CATEGORY_LABELS: Record<string, string> = {
  staple: '主食',
  entree: '主菜',
  vegetable: '蔬菜',
  soup: '汤羹',
  egg: '蛋类',
  soy: '豆制品',
  snack: '加餐',
  fruit: '水果',
  dairy: '奶制品',
  pickle: '腌制菜',
}
