from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select,update
from app.models.user import User
from app.core.security import hash_password, verify_password
from app.schemas.user import UserCreate

class AuthService:

    @staticmethod
    async def get_user_by_email(db: AsyncSession, email: str):
        result = await db.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()
    @staticmethod
    async def get_user_by_number(db: AsyncSession, phone: str):
        result = await db.execute(select(User).where(User.phone == phone))
        return result.scalar_one_or_none()

    @staticmethod
    async def create_user(db: AsyncSession, user_data: UserCreate, session_id: str):
        user = User(
            email=user_data.email,
            hashed_password=hash_password(user_data.password),
            first_name=user_data.first_name,
            last_name=user_data.last_name,
            phone=user_data.phone,
            role=user_data.role,
            activity=user_data.activity,
            terms_accepted=user_data.terms_accepted,
            session_id=session_id
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user

    @staticmethod
    async def authenticate(db: AsyncSession, email: str, password: str):
        user = await AuthService.get_user_by_email(db, email)
        if not user:
            return None
        if not verify_password(password, user.hashed_password):
            return None
        return user
    @staticmethod
    async def update_user(db: AsyncSession, user: User, **kwargs):
        """
        Actualiza campos de un usuario.
        kwargs: los campos y valores a actualizar.
        """
        for key, value in kwargs.items():
            if hasattr(user, key):
                if key == "password":
                    # Si quieres actualizar password desde kwargs
                    setattr(user, "hashed_password", hash_password(value))
                else:
                    setattr(user, key, value)
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user
    
    @staticmethod
    async def update_session(db: AsyncSession, user_id: int,):

        result = await db.execute(
            select(User).where(User.id == user_id)
        )

        user = result.scalar_one_or_none()

        if not user:
            return None
        await db.commit()
        await db.refresh(user)

        return user