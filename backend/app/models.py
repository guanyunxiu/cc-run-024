"""数据库模型（SQLModel）。"""
from datetime import datetime, date
from typing import Any, Optional

from sqlalchemy import JSON, Column, Text
from sqlmodel import Field, SQLModel


def _json_field(default=None):
    return Field(default_factory=(default or (lambda: None)), sa_column=Column(JSON))


# ---------- 用户 ----------

class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(index=True, unique=True)
    password_hash: str
    name: str
    role: str = Field(default="nutritionist")  # admin / nutritionist / viewer
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ---------- 食材 ----------

class Ingredient(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    category: str = Field(default="其他")          # 主食/肉类/蔬菜/蛋奶/豆制品/水果/调味/油脂
    edible_pct: float = Field(default=100.0)      # 可食部 %
    # 每 100g 可食部营养成分
    energy_kcal: float = 0.0
    protein_g: float = 0.0
    fat_g: float = 0.0
    carb_g: float = 0.0
    sodium_mg: float = 0.0
    potassium_mg: float = 0.0
    phosphorus_mg: float = 0.0
    fiber_g: float = 0.0
    calcium_mg: float = 0.0
    vitamin_k_ug: float = 0.0
    purine_mg: float = 0.0
    glycemic_index: float = 0.0
    allergens: list = _json_field(list)           # egg/milk/fish/...
    tags: list = _json_field(list)                # pork/alcohol/meat/fish/high_sugar/fried/...
    unit_cost: float = Field(default=0.0)         # 元 / kg（毛重）
    note: str = Field(default="", sa_column=Column(Text, default=""))


# ---------- 菜品 ----------

class Dish(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    category: str = Field(index=True)             # staple/entree/vegetable/soup/egg/soy/snack/fruit/dairy/pickle
    iddsi_level: int = Field(default=7)           # 食用该菜品所需最低 IDDSI 等级（≤ 老人等级才可选）
    serving_desc: str = Field(default="每份")
    energy_kcal: float = 0.0
    protein_g: float = 0.0
    fat_g: float = 0.0
    carb_g: float = 0.0
    sodium_mg: float = 0.0
    potassium_mg: float = 0.0
    phosphorus_mg: float = 0.0
    fiber_g: float = 0.0
    calcium_mg: float = 0.0
    vitamin_k_ug: float = 0.0
    cost: float = 0.0
    allergens: list = _json_field(list)
    tags: list = _json_field(list)
    satisfaction: float = Field(default=3.0)      # 老人喜好/满意度 1-5
    waste_index: float = Field(default=0.1)       # 预计浪费比例 0-1
    active: bool = True
    note: str = Field(default="", sa_column=Column(Text, default=""))


class DishIngredient(SQLModel, table=True):
    """菜品配方：每份成品对应的食材毛重 g（含择损/烹饪损失换算）。"""
    id: Optional[int] = Field(default=None, primary_key=True)
    dish_id: int = Field(foreign_key="dish.id", index=True)
    ingredient_id: int = Field(foreign_key="ingredient.id")
    gross_g: float = Field(default=0.0)            # 投料毛重 g
    cooking_loss_pct: float = Field(default=0.0)   # 烹饪损耗 %（吸水为负）
    note: str = ""


# ---------- 禁忌规则（JSON 规则表） ----------

class Rule(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    code: str = Field(index=True, unique=True)
    name: str = ""
    rule_type: str = Field(default="chronic")      # allergen/chronic/medication/iddsi/religion
    severity: str = Field(default="hard")          # hard / soft
    priority: int = Field(default=100)             # 数字越小优先级越高
    version: str = Field(default="1.0.0")
    active: bool = True
    # 规则参数，如 {"condition": "hypertension", "tag": "high_sodium", "limit_mg": 500}
    params: dict = _json_field(dict)
    rationale: str = Field(default="", sa_column=Column(Text, default=""))


# ---------- 老人档案 ----------

class Resident(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    gender: str = Field(default="male")            # male/female
    age: int = 80
    height_cm: float = 165.0
    weight_kg: float = 60.0
    activity_level: str = Field(default="light")   # bedridden/sedentary/light/moderate/active
    swallowing_level: int = Field(default=7)       # IDDSI 0-7
    chronic_conditions: list = _json_field(list)   # hypertension/diabetes/ckd/hyperlipidemia/gout/...
    allergies: list = _json_field(list)
    dislikes: list = _json_field(list)             # 忌口（软约束）
    religion: str = Field(default="none")          # none/islam/buddhist/vegetarian
    medications: list = _json_field(list)          # ["warfarin", ...]
    nutrition_goal_type: str = Field(default="maintain")  # maintain/lose/gain
    custom_targets: dict = _json_field(dict)       # 营养师手工覆盖
    targets: dict = _json_field(dict)              # 最近一次系统计算结果（快照）
    note: str = Field(default="", sa_column=Column(Text, default=""))
    version: int = Field(default=1)                # 乐观锁
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# ---------- 排餐方案 ----------

class MenuPlan(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = ""
    resident_id: int = Field(foreign_key="resident.id", index=True)
    start_date: date = Field(default_factory=date.today)
    days: int = Field(default=1)                   # 1 或 7
    status: str = Field(default="draft", index=True)  # draft/published/archived
    budget_per_day: float = Field(default=40.0)
    targets_snapshot: dict = _json_field(dict)     # 求解时营养目标
    rule_version: str = Field(default="")
    solver_params: dict = _json_field(dict)
    score: dict = _json_field(dict)                # 目标函数/达标率
    totals: dict = _json_field(dict)               # 实际营养/成本汇总
    version: int = Field(default=1)                # 乐观锁
    created_by: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)
    published_at: Optional[datetime] = None
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class MenuItem(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    plan_id: int = Field(foreign_key="menuplan.id", index=True)
    day_index: int = Field(index=True)             # 0..days-1
    slot: str = Field(index=True)                  # breakfast/lunch/...
    line: str = Field(default="main")              # 同一餐次内的槽线 staple/entree/vegetable/soup/snack/protein
    dish_id: int = Field(foreign_key="dish.id")
    locked: bool = False
    locked_by: str = ""


class PlanVersion(SQLModel, table=True):
    """发布快照，用于版本对比与回滚。"""
    id: Optional[int] = Field(default=None, primary_key=True)
    plan_id: int = Field(foreign_key="menuplan.id", index=True)
    version_no: int
    snapshot: dict = _json_field(dict)
    score: dict = _json_field(dict)
    created_by: str = ""
    note: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ---------- 求解任务 ----------

class SolveTask(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    task_type: str = Field(default="solve")        # solve / resolve
    plan_id: Optional[int] = Field(default=None, foreign_key="menuplan.id")
    resident_id: int = Field(foreign_key="resident.id")
    params: dict = _json_field(dict)
    status: str = Field(default="pending", index=True)  # pending/running/success/failed
    progress: int = Field(default=0)
    message: str = ""
    result: dict = _json_field(dict)
    error: str = ""
    created_by: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None


# ---------- 审计日志 ----------

class AuditLog(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    ts: datetime = Field(default_factory=datetime.utcnow, index=True)
    username: str = Field(default="", index=True)
    action: str = Field(index=True)                # create/update/delete/solve/publish/rollback/export/login
    entity: str = Field(index=True)
    entity_id: str = Field(default="")
    detail: dict = _json_field(dict)
