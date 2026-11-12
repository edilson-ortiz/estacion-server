from fastapi import APIRouter, Depends, HTTPException
from fastapi.encoders import jsonable_encoder
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.security import create_token_pair, hash_password
from app.db.session import get_db
from app.models import User
from app.schemas.user import ResetPasswordRequest, TokenResponse, UserCreate, UserResponse, UserUpdate
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["Auth"])

# Campos del usuario que nunca deben salir en una respuesta
_PRIVATE_USER_FIELDS = {"hashed_password"}


def _public_user(user: User) -> dict:
    return jsonable_encoder({
        attr.key: getattr(user, attr.key)
        for attr in inspect(User).column_attrs
        if attr.key not in _PRIVATE_USER_FIELDS
    })


@router.post("/register")
async def register(user_data: UserCreate, db: AsyncSession = Depends(get_db)):
    if await AuthService.get_user_by_email(db, user_data.email):
        raise HTTPException(status_code=400, detail="El email ya está registrado")
    if await AuthService.phone_exists(db, user_data.phone):
        raise HTTPException(status_code=400, detail="El número de teléfono ya está registrado")

    session_id = AuthService.new_session_id()
    user = await AuthService.create_user(db, user_data, session_id)
    return {
        "detail": "User created",
        "user": _public_user(user),
        **create_token_pair(user.id, session_id),
    }


@router.post("/login", response_model=TokenResponse)
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    # username = email (formato OAuth2 form)
    user = await AuthService.authenticate(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(status_code=401, detail="Credenciales inválidas")

    session_id = await AuthService.start_session(db, user)
    return create_token_pair(user.id, session_id)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(refresh_token: str, db: AsyncSession = Depends(get_db)):
    try:
        user_id, token_session_id = AuthService.decode_refresh_token(refresh_token)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid refresh token") from None

    user = await AuthService.get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Sesión única: verificar que siga siendo la sesión activa
    if user.session_id != token_session_id:
        raise HTTPException(status_code=401, detail="Session expired. Logged in from another device")

    return create_token_pair(user_id, user.session_id)


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.post("/reset-password")
async def reset_password(
    data: ResetPasswordRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Cambia la contraseña del usuario actual (token en el header Authorization)."""
    current_user.hashed_password = hash_password(data.new_password)
    db.add(current_user)
    await db.commit()
    return {"message": "Password updated"}


@router.put("/update-me", response_model=UserResponse)
async def update_me(
    user_data: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Actualiza los campos del usuario actual."""
    return await AuthService.update_user(db, current_user, **user_data.model_dump(exclude_unset=True))
