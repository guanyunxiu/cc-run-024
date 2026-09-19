"""异步求解任务与操作审计日志。"""
from datetime import datetime
from sqlmodel import SQLModel, Field


class Task(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    task_type: str = Field(default="solve", max_length=16)   # solve / resolve / export
    status: str = Field(default="pending", max_length=16)    # pending/running/success/failed
    progress: int = Field(default=0)                          # 0-100
    message: str = Field(default="", max_length=500)
    result_json: str = Field(default="{}", max_length=4000)  # plan_id 等
    params_json: str = Field(default="{}", max_length=4000)
    created_by: str = Field(default="", max_length=64)
    created_at: datetime = Field(default_factory=datetime.now)
    started_at: datetime | None = None
    finished_at: datetime | None = None


class AuditLog(SQLModel, table=True):
    """操作日志（审计完整性）。"""
    id: int | None = Field(default=None, primary_key=True)
    username: str = Field(default="", max_length=64, index=True)
    action: str = Field(max_length=64, index=True)           # elder.update / plan.publish ...
    entity_type: str = Field(default="", max_length=32)
    entity_id: str = Field(default="", max_length=64)
    detail_json: str = Field(default="{}", max_length=4000)
    rule_version: str = Field(default="", max_length=32)
    created_at: datetime = Field(default_factory=datetime.now, index=True)
