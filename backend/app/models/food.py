"""食材、菜品模型与营养/成本字段。

营养换算链路：
  菜品 --(RecipeItem: 食材净重g, 烹饪损失率, 生熟系数)--> 食材每100g营养成分
  成品每100g营养 = Σ(净重 * (1-损失率) * 食材每100g营养/100) / 成品总重 * 100
"""
from datetime import datetime
from sqlmodel import SQLModel, Field


class Ingredient(SQLModel, table=True):
    """食材（每100g可食部的营养成分）。"""
    id: int | None = Field(default=None, primary_key=True)
    code: str = Field(index=True, unique=True, max_length=32)
    name: str = Field(index=True, max_length=64)
    category: str = Field(default="", max_length=32)        # 谷薯/蔬菜/肉蛋/奶豆/水果/油脂...
    edible_rate: float = Field(default=1.0)                 # 可食部比例 0-1
    # 每 100g 可食部营养
    energy_kcal: float = 0.0
    protein_g: float = 0.0
    fat_g: float = 0.0
    carbs_g: float = 0.0
    dietary_fiber_g: float = 0.0
    sodium_mg: float = 0.0
    potassium_mg: float = 0.0
    phosphorus_mg: float = 0.0
    calcium_mg: float = 0.0
    cholesterol_mg: float = 0.0
    sugar_g: float = 0.0
    purine_mg: float = 0.0
    gi: float | None = None                                  # 血糖生成指数
    # 过敏原标签: peanut/seafood/fish/egg/milk/nuts/soy/wheat
    allergen_tags: str = Field(default="", max_length=255)  # 逗号分隔
    tags: str = Field(default="", max_length=255)           # 其他标签: pork,alcohol,beef...
    unit_cost: float = 0.0                                  # 每100g成本(元)
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.now)


class Dish(SQLModel, table=True):
    """菜品。"""
    id: int | None = Field(default=None, primary_key=True)
    code: str = Field(index=True, unique=True, max_length=32)
    name: str = Field(index=True, max_length=64)
    dish_type: str = Field(default="", max_length=16)       # staple荤菜/素菜/汤羹/水果/奶/流质
    cuisine: str = Field(default="", max_length=32)
    # 默认一份：成品重量g + 建议单价(元)，允许求解器在份量档位中选择
    portion_g: float = 200.0
    portion_cost: float = 0.0                               # 0 则按配方成本自动核算
    # 每100g成品营养（由配方聚合写入，见 services/nutrition.refresh_dish_nutrition）
    energy_kcal: float = 0.0
    protein_g: float = 0.0
    fat_g: float = 0.0
    carbs_g: float = 0.0
    dietary_fiber_g: float = 0.0
    sodium_mg: float = 0.0
    potassium_mg: float = 0.0
    phosphorus_mg: float = 0.0
    calcium_mg: float = 0.0
    cholesterol_mg: float = 0.0
    sugar_g: float = 0.0
    purine_mg: float = 0.0
    gi: float | None = None
    # 标签（聚合自食材 + 人工补充）
    allergen_tags: str = Field(default="", max_length=255)
    tags: str = Field(default="", max_length=255)           # pork/beef/alcohol...
    iddsi_level: int = Field(default=7)                     # 菜品质地 IDDSI 0-7
    meal_slots: str = Field(default="breakfast,lunch,dinner", max_length=64)
    preference_score: float = Field(default=3.0)           # 满意度评分 1-5
    waste_rate: float = Field(default=0.08)                 # 预估浪费率
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.now)


class RecipeItem(SQLModel, table=True):
    """菜品配方行：食材净重（市品g）、烹饪损失率。"""
    id: int | None = Field(default=None, primary_key=True)
    dish_id: int = Field(foreign_key="dish.id", index=True)
    ingredient_id: int = Field(foreign_key="ingredient.id", index=True)
    gross_weight_g: float = 0.0     # 投料（市品）重量
    cooking_loss_rate: float = 0.0  # 烹饪损失率（吸水菜为负）
