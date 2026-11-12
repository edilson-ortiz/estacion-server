from datetime import timedelta
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings
from app.core.time import utcnow

# bcrypt_sha256 evita el límite de 72 bytes de bcrypt
pwd_context = CryptContext(schemes=["bcrypt_sha256"], deprecated="auto")

ACCESS = "access"
REFRESH = "refresh"


# ==============================
# Contraseñas
# ==============================

def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    return pwd_context.verify(password, hashed)


# ==============================
# JWT
# ==============================

def create_token(data: dict, expires_delta: timedelta) -> str:
    now = utcnow()
    to_encode = {**data, "exp": now + expires_delta, "iat": now}
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_access_token(user_id: int, session_id: str) -> str:
    return create_token(
        {"sub": str(user_id), "session_id": session_id, "type": ACCESS},
        timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )


def create_refresh_token(user_id: int, session_id: str) -> str:
    return create_token(
        {"sub": str(user_id), "session_id": session_id, "type": REFRESH},
        timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )


def create_token_pair(user_id: int, session_id: str) -> dict[str, str]:
    return {
        "access_token": create_access_token(user_id, session_id),
        "refresh_token": create_refresh_token(user_id, session_id),
    }


def decode_token(token: str, expected_type: str) -> tuple[int, str | None]:
    """Valida firma, expiración y tipo. Devuelve (user_id, session_id).

    Lanza ValueError si el token es inválido por cualquier motivo.
    """
    try:
        payload: dict[str, Any] = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
    except JWTError as exc:
        raise ValueError("invalid token") from exc

    if payload.get("type") != expected_type:
        raise ValueError("invalid token type")
    try:
        user_id = int(payload.get("sub"))
    except (TypeError, ValueError) as exc:
        raise ValueError("invalid subject") from exc
    return user_id, payload.get("session_id")
