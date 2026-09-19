"""禁忌规则模型（JSON 规则表 + 版本）。"""
from datetime import datetime
from sqlmodel import SQLModel, Field


class RuleVersion(SQLModel, table=True):
    """规则版本。"""
    id: int | None = Field(default=None, primary_key=True)
    version: str = Field(index=True, unique=True, max_length=32)  # 语义化版本 2026.09.1
    status: str = Field(default="draft", max_length=16)           # draft/published/archived
    note: str = Field(default="", max_length=500)
    published_at: datetime | None = None
    created_at: datetime = Field(default_factory=datetime.now)


class Rule(SQLModel, table=True):
    """单条规则。

    rule_type:
      allergen        过敏原禁忌 —— condition: {"allergen": "peanut"}
      chronic         慢病禁忌 —— condition: {"disease": "hypertension", "tags_any": ["high_sodium"]}
      drug_food       药食交互 —— condition: {"drug": "warfarin", "tags_any": ["vitamin_k_rich"]}
      religion        宗教禁忌 —— condition: {"religion": "islam", "tags_any": ["pork","alcohol"]}
      iddsi           吞咽质地 —— 无需 condition，按等级比较
      dislike         忌口关键字 —— 由老人档案动态生成，不入库
    action: forbid（硬禁） / warn（软警告）
    subject: dish 或 ingredient
    priority: 数字越大优先级越高（冲突解释时排序）
    """
    id: int | None = Field(default=None, primary_key=True)
    version_id: int = Field(foreign_key="ruleversion.id", index=True)
    code: str = Field(index=True, max_length=48)
    name: str = Field(max_length=128)
    rule_type: str = Field(max_length=16)
    subject: str = Field(default="dish", max_length=16)
    action: str = Field(default="forbid", max_length=8)
    priority: int = 100
    condition_json: str = Field(default="{}", max_length=2000)
    message: str = Field(default="", max_length=300)
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.now)
