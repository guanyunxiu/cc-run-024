"""公共依赖：当前用户、审计日志。"""
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlmodel import Session, select

from .database import get_session
from .models import AuditLog, User
from .security import decode_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


def get_current_user(token: str | None = Depends(oauth2_scheme),
                     session: Session = Depends(get_session)) -> User:
    cred_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="未认证或登录已过期", headers={"WWW-Authenticate": "Bearer"})
    if not token:
        raise cred_exc
    try:
        payload = decode_token(token)
        username = payload.get("sub")
    except Exception:
        raise cred_exc
    user = session.exec(select(User).where(User.username == username)).first()
    if not user or not user.is_active:
        raise cred_exc
    return user


def require_roles(*roles: str):
    def checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status_code=403, detail="权限不足")
        return user
    return checker


def audit(session: Session, user: User | str, action: str, entity: str,
          entity_id: str | int = "", detail: dict | None = None) -> None:
    username = user.username if isinstance(user, User) else str(user)
    session.add(AuditLog(username=username, action=action, entity=entity,
                         entity_id=str(entity_id), detail=detail or {}))
