"""请求/响应 Schema。"""
from datetime import date, datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


# ---------- 认证 ----------

class LoginIn(BaseModel):
    username: str
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict


class UserIn(BaseModel):
    username: str
    password: str = Field(min_length=4)
    name: str
    role: str = "nutritionist"


class UserOut(BaseModel):
    id: int
    username: str
    name: str
    role: str
    is_active: bool
    created_at: datetime


# ---------- 食材 / 菜品 ----------

class IngredientIn(BaseModel):
    name: str
    category: str = "其他"
    edible_pct: float = 100.0
    energy_kcal: float = 0
    protein_g: float = 0
    fat_g: float = 0
    carb_g: float = 0
    sodium_mg: float = 0
    potassium_mg: float = 0
    phosphorus_mg: float = 0
    fiber_g: float = 0
    calcium_mg: float = 0
    vitamin_k_ug: float = 0
    purine_mg: float = 0
    glycemic_index: float = 0
    allergens: list[str] = []
    tags: list[str] = []
    unit_cost: float = 0
    note: str = ""


class RecipeItem(BaseModel):
    ingredient_id: int
    gross_g: float = 0
    cooking_loss_pct: float = 0
    note: str = ""


class DishIn(BaseModel):
    name: str
    category: str
    iddsi_level: int = 7
    serving_desc: str = "每份"
    satisfaction: float = 3.0
    waste_index: float = 0.1
    active: bool = True
    note: str = ""
    # 营养可直接填写；若提供配方则由配方换算覆盖
    energy_kcal: float = 0
    protein_g: float = 0
    fat_g: float = 0
    carb_g: float = 0
    sodium_mg: float = 0
    potassium_mg: float = 0
    phosphorus_mg: float = 0
    fiber_g: float = 0
    calcium_mg: float = 0
    cost: float = 0
    allergens: list[str] = []
    tags: list[str] = []
    recipe: list[RecipeItem] = []


# ---------- 规则 ----------

class RuleIn(BaseModel):
    code: str
    name: str = ""
    rule_type: str = "chronic"
    severity: str = "hard"
    priority: int = 100
    version: str = "1.0.0"
    active: bool = True
    params: dict[str, Any] = {}
    rationale: str = ""


# ---------- 老人 ----------

class ResidentIn(BaseModel):
    name: str
    gender: str = "male"
    age: int = Field(ge=60, le=120)
    height_cm: float = Field(ge=130, le=210)
    weight_kg: float = Field(ge=30, le=150)
    activity_level: str = "light"
    swallowing_level: int = Field(ge=0, le=7)
    chronic_conditions: list[str] = []
    allergies: list[str] = []
    dislikes: list[str] = []
    religion: str = "none"
    medications: list[str] = []
    nutrition_goal_type: str = "maintain"
    custom_targets: dict[str, float] = {}
    note: str = ""


class ResidentUpdate(ResidentIn):
    version: int


# ---------- 方案 ----------

class PlanCreate(BaseModel):
    name: str = ""
    resident_id: int
    start_date: date = Field(default_factory=date.today)
    days: int = Field(default=1, ge=1, le=7)
    budget_per_day: float = Field(default=40, ge=0, le=500)


class PlanItemPatch(BaseModel):
    """手动调整：替换某槽位的菜品。"""
    day_index: int
    slot: str
    line: str = "main"
    dish_id: int
    locked: bool = False
    version: int


class LockItem(BaseModel):
    item_id: int
    locked: bool
    version: int


class PublishIn(BaseModel):
    note: str = ""
    version: int


class ResolveIn(BaseModel):
    """局部重求解（保持锁定项不变）。"""
    version: int
    day_index: Optional[int] = None   # None = 全部未锁定槽位
    time_limit_sec: int = 20


class CheckPlanIn(BaseModel):
    resident_id: int
    items: list[dict]  # [{day_index, slot, line, dish_id}]


class TaskOut(BaseModel):
    id: int
    task_type: str
    plan_id: Optional[int]
    resident_id: int
    status: str
    progress: int
    message: str
    error: str
    result: dict
    created_at: datetime
