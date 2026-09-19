"""认证路由。"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel import Session, select

from ..database import get_session
from ..deps import audit, get_current_user
from ..models import User
from ..schemas import LoginIn, TokenOut, UserOut
from ..security import create_access_token, verify_password

router = APIRouter(prefix="/api/auth", tags=["认证"])


def _login(session: Session, username: str, password: str) -> TokenOut:
    user = session.exec(select(User).where(User.username == username)).first()
    if not user or not verify_password(password, user.password_hash):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="账号已停用")
    token = create_access_token(user.username, user.role)
    audit(session, user, "login", "user", user.id, {"name": user.name})
    session.commit()
    return TokenOut(access_token=token, user={
        "id": user.id, "username": user.username, "name": user.name,
        "role": user.role,
    })


@router.post("/login", response_model=TokenOut)
def login_json(body: LoginIn, session: Session = Depends(get_session)):
    return _login(session, body.username, body.password)


@router.post("/token", response_model=TokenOut, include_in_schema=False)
def login_form(form: OAuth2PasswordRequestForm = Depends(),
               session: Session = Depends(get_session)):
    return _login(session, form.username, form.password)


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user
