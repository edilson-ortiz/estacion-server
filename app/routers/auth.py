from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models.user import User
from app.schemas.user import ResetPasswordRequest, UserCreate, UserLogin, TokenResponse, UserResponse, UserUpdate
from app.services.auth_service import AuthService
from app.core.security import create_access_token, create_refresh_token, hash_password
from app.dependencies.auth import get_current_user
from fastapi.security import OAuth2PasswordRequestForm
import uuid

router = APIRouter(prefix="/auth", tags=["Auth"])

@router.post("/register")
async def register(user_data: UserCreate, db: AsyncSession = Depends(get_db)):
    existing = await AuthService.get_user_by_email(db, user_data.email)
    existing_by_phone = await AuthService.get_user_by_number(db, user_data.phone)
    if existing:
        raise HTTPException(status_code=400, detail="El email ya está registrado")
    if existing_by_phone:
        raise HTTPException(status_code=400, detail="El número de teléfono ya está registrado")
        # generar nueva sesión
    new_session_id = str(uuid.uuid4())
    user = await AuthService.create_user(db, user_data, new_session_id)  # <- ahora también recibe session_id

    return {
        "detail": "User created",
        "user": user,
        "access_token": create_access_token(user.id, new_session_id),
        "refresh_token": create_refresh_token(user.id, new_session_id)
    }



@router.post("/login", response_model=TokenResponse)
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    # form_data.username y form_data.password vienen del formulario
    user = await AuthService.authenticate(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(status_code=401, detail="Credenciales inválidas")

        # generar nueva sesión
    new_session_id = str(uuid.uuid4())

    # guardar en DB
    await AuthService.update_user(db, user, session_id=new_session_id)
    return {
        "access_token": create_access_token(user.id, new_session_id),
        "refresh_token": create_refresh_token(user.id,  new_session_id)
    }
@router.post("/refresh", response_model=TokenResponse)
async def refresh(refresh_token: str,db: AsyncSession = Depends(get_db)):
    from jose import jwt
    from app.config import settings

    try:
        payload = jwt.decode(refresh_token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid token type")

        user_id = int(payload.get("sub"))
        token_session_id = payload.get("session_id")
    except:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    user = await AuthService.update_session(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # 🔐 verificar sesión activa
    if user.session_id != token_session_id:
        raise HTTPException(
            status_code=401,
            detail="Session expired. Logged in from another device"
        )
    return {
        "access_token": create_access_token(user_id,user.session_id),
        "refresh_token": create_refresh_token(user_id, user.session_id)
    }

@router.get("/me", response_model=UserResponse)
async def get_me(current_user = Depends(get_current_user)):
    # Devuelve el objeto completo
    return current_user

@router.post("/reset-password")
async def reset_password(
    data: ResetPasswordRequest,
    current_user: User = Depends(get_current_user),  # <- token automáticamente en Authorization Bearer
    db: AsyncSession = Depends(get_db)
):
    """
    Cambia la contraseña del usuario actual. 
    No necesitas enviar token en el body, solo Authorization header.
    """
    current_user.hashed_password = hash_password(data.new_password)
    db.add(current_user)
    await db.commit()
    return {"message": "Password updated"}

@router.put("/update-me", response_model=UserResponse)
async def update_me(
    user_data: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Actualiza los campos del usuario actual.
    """
    update_fields = user_data.dict(exclude_unset=True)
    user = await AuthService.update_user(db, current_user, **update_fields)
    return user