from datetime import datetime, timedelta, timezone
from jose import jwt
from passlib.context import CryptContext
from app.config import settings





# ==============================
# Password Hashing (MEJORADO)
# ==============================

pwd_context = CryptContext(
    schemes=["bcrypt_sha256"],  # 👈 evita límite de 72 bytes
    deprecated="auto"
)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    return pwd_context.verify(password, hashed)


# ==============================
# JWT Creation (MEJORADO)
# ==============================

def create_token(data: dict, expires_delta: timedelta) -> str:
    to_encode = data.copy()

    expire = datetime.now(timezone.utc) + expires_delta  # 👈 correcto en 2026
    to_encode.update({
        "exp": expire,
        "iat": datetime.now(timezone.utc)  # 👈 agregado (issued at)
    })

    return jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM
    )


def create_access_token(user_id: int,session_id: str) -> str:
    return create_token(
        {
            "sub": str(user_id),
            "session_id": session_id,
            "type": "access",
            
        },
        timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )


def create_refresh_token(user_id: int,session_id: str) -> str:
    return create_token(
        {
            "sub": str(user_id),
            "session_id": session_id,
            "type": "refresh"
        },
        timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    )