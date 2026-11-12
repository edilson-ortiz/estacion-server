"""Dependencias reutilizables de FastAPI (autenticación, roles)."""
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import ACCESS, decode_token
from app.db.session import get_db
from app.models import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    try:
        user_id, token_session_id = decode_token(token, ACCESS)
    except ValueError as exc:
        detail = "Invalid token type" if str(exc) == "invalid token type" else "Invalid token"
        raise HTTPException(status_code=401, detail=detail) from None

    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Sesión única: si inició sesión en otro dispositivo, este token ya no vale
    if user.session_id != token_session_id:
        raise HTTPException(
            status_code=401,
            detail="Session closed because you logged in on another device",
        )
    return user


async def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """Para las rutas del futuro panel administrativo."""
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Se requieren permisos de administrador.")
    return current_user
