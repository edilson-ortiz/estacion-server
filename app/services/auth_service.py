import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import REFRESH, decode_token, hash_password, verify_password
from app.models import User
from app.schemas.user import UserCreate


class AuthService:

    @staticmethod
    def new_session_id() -> str:
        return str(uuid.uuid4())

    @staticmethod
    async def get_user_by_id(db: AsyncSession, user_id: int) -> User | None:
        return await db.get(User, user_id)

    @staticmethod
    async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
        result = await db.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    @staticmethod
    async def phone_exists(db: AsyncSession, phone: str | None) -> bool:
        if not phone:
            return False
        result = await db.execute(select(User.id).where(User.phone == phone).limit(1))
        return result.first() is not None

    @staticmethod
    async def create_user(db: AsyncSession, user_data: UserCreate, session_id: str) -> User:
        user = User(
            email=user_data.email,
            hashed_password=hash_password(user_data.password),
            first_name=user_data.first_name,
            last_name=user_data.last_name,
            phone=user_data.phone,
            role=user_data.role,
            activity=user_data.activity,
            terms_accepted=user_data.terms_accepted,
            session_id=session_id,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user

    @staticmethod
    async def authenticate(db: AsyncSession, email: str, password: str) -> User | None:
        user = await AuthService.get_user_by_email(db, email)
        if not user or not verify_password(password, user.hashed_password):
            return None
        return user

    @staticmethod
    async def update_user(db: AsyncSession, user: User, **fields) -> User:
        """Actualiza campos del usuario. `password` se guarda hasheado."""
        for key, value in fields.items():
            if key == "password":
                user.hashed_password = hash_password(value)
            elif hasattr(user, key):
                setattr(user, key, value)
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user

    @staticmethod
    async def start_session(db: AsyncSession, user: User) -> str:
        """Genera y guarda un session_id nuevo (invalida los tokens de otros dispositivos)."""
        session_id = AuthService.new_session_id()
        await AuthService.update_user(db, user, session_id=session_id)
        return session_id

    @staticmethod
    def decode_refresh_token(token: str) -> tuple[int, str | None]:
        return decode_token(token, REFRESH)
