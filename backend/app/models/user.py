"""用户模型。"""
from datetime import datetime
from sqlmodel import SQLModel, Field


class User(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    username: str = Field(index=True, unique=True, max_length=64)
    hashed_password: str = Field(max_length=255)
    full_name: str = Field(default="", max_length=64)
    role: str = Field(default="nutritionist", max_length=32)  # admin / nutritionist
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.now)
