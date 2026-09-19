"""数据库与会话管理（SQLModel + SQLite）。"""
from sqlmodel import SQLModel, Session, create_engine, select
from sqlalchemy.pool import StaticPool

from .config import DATABASE_URL

connect_args = {"check_same_thread": False}
if DATABASE_URL.endswith(":memory:"):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
else:
    engine = create_engine(DATABASE_URL, echo=False, connect_args=connect_args)


def init_db() -> None:
    # 确保所有模型被导入注册
    from . import models  # noqa: F401

    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session


def new_session() -> Session:
    return Session(engine)
