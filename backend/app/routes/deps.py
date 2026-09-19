"""FastAPI 依赖：当前用户。"""
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlmodel import Session, select

from ..database import get_session
from ..models import User
from ..core.security import decode_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def get_current_user(token: str = Depends(oauth2_scheme),
                     session: Session = Depends(get_session)) -> User:
    cred_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="登录凭证无效或已过期", headers={"WWW-Authenticate": "Bearer"})
    payload = decode_token(token)
    if not payload:
        raise cred_exc
    user = session.exec(select(User).where(User.username == payload.get("sub"))).first()
    if not user or not user.is_active:
        raise cred_exc
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return user
