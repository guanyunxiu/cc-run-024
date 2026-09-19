"""SQLite 引擎与会话。"""
from sqlmodel import SQLModel, create_engine, Session
from .config import DATABASE_URL

connect_args = {"check_same_thread": False}
engine = create_engine(
    DATABASE_URL, echo=False, connect_args=connect_args
)


def init_db() -> None:
    # 触发模型注册
    from . import models  # noqa: F401

    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session
