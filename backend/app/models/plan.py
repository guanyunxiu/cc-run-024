"""排餐方案、排餐条目模型（含乐观锁版本号）。"""
from datetime import datetime
from sqlmodel import SQLModel, Field


class MealPlan(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    elder_id: int = Field(foreign_key="elder.id", index=True)
    title: str = Field(default="", max_length=128)
    period_type: str = Field(default="day", max_length=8)   # day / week
    start_date: str = Field(index=True, max_length=10)      # YYYY-MM-DD
    end_date: str = Field(default="", max_length=10)
    status: str = Field(default="draft", max_length=16)     # draft/published/archived
    rule_version: str = Field(default="", max_length=32)
    # 求解器参数快照 JSON
    solver_params: str = Field(default="{}", max_length=2000)
    # 汇总指标 JSON: 营养合计、偏差、成本、满意度、浪费、软约束得分
    metrics_json: str = Field(default="{}", max_length=4000)
    # 乐观锁
    lock_version: int = Field(default=1)
    parent_plan_id: int | None = Field(default=None, foreign_key="mealplan.id")
    created_by: str = Field(default="", max_length=64)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    published_at: datetime | None = None


class MealItem(SQLModel, table=True):
    """一个餐次槽位的一道菜（可多道菜）。"""
    id: int | None = Field(default=None, primary_key=True)
    plan_id: int = Field(foreign_key="mealplan.id", index=True)
    day_index: int = Field(default=0)          # 周方案 0-6
    meal_date: str = Field(default="", max_length=10)
    slot: str = Field(max_length=16)           # breakfast/lunch/dinner
    dish_id: int = Field(foreign_key="dish.id")
    portion_g: float = 200.0
    locked: bool = Field(default=False)        # 手动锁定，局部重求解保持不变
    # 冗余快照（菜品被改后旧方案仍可追溯）
    dish_name: str = Field(default="", max_length=64)
    # 单条目成本与营养快照 JSON
    detail_json: str = Field(default="{}", max_length=1000)


class PlanVersionArchive(SQLModel, table=True):
    """方案发布/编辑的版本快照（用于版本对比与回滚）。"""
    id: int | None = Field(default=None, primary_key=True)
    plan_id: int = Field(foreign_key="mealplan.id", index=True)
    version_no: int
    status: str = Field(default="draft", max_length=16)
    snapshot_json: str = Field(default="{}", max_length=200000)
    metrics_json: str = Field(default="{}", max_length=4000)
    created_by: str = Field(default="", max_length=64)
    created_at: datetime = Field(default_factory=datetime.now)
