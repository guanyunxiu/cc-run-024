"""Pydantic 请求/响应模型。"""
from datetime import date, datetime
from pydantic import BaseModel, Field


# ── 认证 ──
class LoginIn(BaseModel):
    username: str
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: "UserOut"


class UserOut(BaseModel):
    id: int
    username: str
    full_name: str
    role: str
    is_active: bool

    model_config = {"from_attributes": True}


# ── 食材 ──
class IngredientIn(BaseModel):
    code: str = Field(max_length=32)
    name: str = Field(max_length=64)
    category: str = ""
    edible_rate: float = Field(ge=0.1, le=1.0, default=1.0)
    energy_kcal: float = 0
    protein_g: float = 0
    fat_g: float = 0
    carbs_g: float = 0
    dietary_fiber_g: float = 0
    sodium_mg: float = 0
    potassium_mg: float = 0
    phosphorus_mg: float = 0
    calcium_mg: float = 0
    cholesterol_mg: float = 0
    sugar_g: float = 0
    purine_mg: float = 0
    gi: float | None = None
    allergen_tags: str = ""
    tags: str = ""
    unit_cost: float = Field(ge=0, default=0)
    is_active: bool = True


class IngredientOut(IngredientIn):
    id: int


# ── 菜品配方 ──
class RecipeItemIn(BaseModel):
    ingredient_id: int
    gross_weight_g: float = Field(gt=0)
    cooking_loss_rate: float = Field(ge=-0.8, le=0.95, default=0.0)


class DishIn(BaseModel):
    code: str = Field(max_length=32)
    name: str = Field(max_length=64)
    dish_type: str = ""
    cuisine: str = ""
    portion_g: float = Field(gt=0, default=200)
    portion_cost: float = Field(ge=0, default=0)
    iddsi_level: int = Field(ge=0, le=7, default=7)
    meal_slots: str = "breakfast,lunch,dinner"
    preference_score: float = Field(ge=1, le=5, default=3)
    waste_rate: float = Field(ge=0, le=0.8, default=0.08)
    allergen_tags: str = ""
    tags: str = ""
    is_active: bool = True
    recipe: list[RecipeItemIn] = []


class DishOut(BaseModel):
    id: int
    code: str
    name: str
    dish_type: str
    cuisine: str
    portion_g: float
    portion_cost: float
    energy_kcal: float
    protein_g: float
    fat_g: float
    carbs_g: float
    dietary_fiber_g: float
    sodium_mg: float
    potassium_mg: float
    phosphorus_mg: float
    calcium_mg: float
    cholesterol_mg: float
    sugar_g: float
    purine_mg: float
    gi: float | None
    allergen_tags: str
    tags: str
    iddsi_level: int
    meal_slots: str
    preference_score: float
    waste_rate: float
    is_active: bool
    recipe: list[dict] = []


# ── 老人 ──
class ElderIn(BaseModel):
    name: str = Field(max_length=64)
    gender: str = Field(pattern="^(male|female)$")
    birth_date: date
    height_cm: float = Field(gt=100, lt=230)
    weight_kg: float = Field(gt=25, lt=200)
    activity_level: str = "sedentary"
    chronic_diseases: str = ""
    allergies: str = ""
    iddsi_level: int = Field(ge=0, le=7, default=7)
    dislikes: str = ""
    religion: str = "none"
    medications: str = ""
    nutrition_goal: str = "maintain"
    target_overrides: dict[str, float | list[float]] = {}
    cost_limit_day: float = Field(ge=0, default=35)
    is_active: bool = True


class ElderOut(BaseModel):
    id: int
    name: str
    gender: str
    birth_date: date
    height_cm: float
    weight_kg: float
    activity_level: str
    chronic_diseases: str
    allergies: str
    iddsi_level: int
    dislikes: str
    religion: str
    medications: str
    nutrition_goal: str
    target_overrides: str
    target_explanation: str
    cost_limit_day: float
    is_active: bool
    created_at: datetime
    updated_at: datetime


# ── 规则 ──
class RuleIn(BaseModel):
    code: str
    name: str
    rule_type: str
    subject: str = "dish"
    action: str = "forbid"
    priority: int = 100
    condition: dict = {}
    message: str = ""
    is_active: bool = True


class RuleOut(BaseModel):
    id: int
    version_id: int
    code: str
    name: str
    rule_type: str
    subject: str
    action: str
    priority: int
    condition: dict
    message: str
    is_active: bool


class RuleVersionOut(BaseModel):
    id: int
    version: str
    status: str
    note: str
    published_at: datetime | None
    created_at: datetime
    rule_count: int = 0


# ── 配餐 ──
class SolveRequest(BaseModel):
    elder_id: int
    period_type: str = Field(pattern="^(day|week)$", default="day")
    start_date: date
    days: int = Field(ge=1, le=7, default=1)
    title: str = ""
    cost_limit_day: float | None = None
    weights: dict[str, float] | None = None
    time_limit_seconds: float = Field(ge=2, le=60, default=20)
    locked_items: list[dict] = []
    plan_id: int | None = None     # 局部重求解：基于现有方案


class ManualItemIn(BaseModel):
    day_index: int
    slot: str
    dish_id: int
    portion_g: float = Field(gt=0, default=200)
    locked: bool = False


class PlanUpdateIn(BaseModel):
    title: str | None = None
    items: list[ManualItemIn] | None = None
    lock_version: int


class PlanStatusIn(BaseModel):
    lock_version: int


# ── 任务 ──
class TaskOut(BaseModel):
    id: int
    task_type: str
    status: str
    progress: int
    message: str
    result_json: str
    params_json: str
    created_by: str
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


class CheckIn(BaseModel):
    """菜品试配校验（手动调整时实时冲突高亮）。"""
    elder_id: int
    dish_ids: list[int]


TokenOut.model_rebuild()
