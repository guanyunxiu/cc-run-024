"""老人档案与营养目标模型。"""
from datetime import date, datetime
from sqlmodel import SQLModel, Field


# 活动水平系数
ACTIVITY_FACTORS = {
    "bedridden": 1.10,   # 卧床
    "sedentary": 1.20,  # 久坐/极少活动
    "light": 1.35,      # 轻度活动
    "moderate": 1.50,   # 中度活动
}

# 营养目标类型
GOAL_TYPES = {
    "maintain": "维持体重",
    "gain": "增重/肌少症营养补充",
    "lose": "减重",
    "malnutrition": "营养不良干预",
}


class Elder(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True, max_length=64)
    gender: str = Field(default="male", max_length=8)     # male/female
    birth_date: date
    height_cm: float
    weight_kg: float
    activity_level: str = Field(default="sedentary", max_length=16)
    # 慢病: diabetes2,hypertension,dyslipidemia,ckd,gout,malnutrition,sarcopenia,osteoporosis,copd
    chronic_diseases: str = Field(default="", max_length=255)   # 逗号分隔
    allergies: str = Field(default="", max_length=255)          # 过敏原标签逗号分隔
    iddsi_level: int = Field(default=7)                         # 吞咽等级 0-7
    dislikes: str = Field(default="", max_length=255)           # 忌口（菜名/食材名关键字, 分号）
    religion: str = Field(default="none", max_length=16)        # none/islam/vegetarian/buddhist
    medications: str = Field(default="", max_length=255)        # 药物代码 warfarin,mao_i,levodopa...
    nutrition_goal: str = Field(default="maintain", max_length=16)
    # 手工覆盖目标（JSON），如 {"energy_kcal": 1800}；为空则全自动计算
    target_overrides: str = Field(default="", max_length=1000)
    target_explanation: str = Field(default="", max_length=4000)  # 目标计算过程说明
    cost_limit_day: float = 35.0                               # 每日餐费上限(元)
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
