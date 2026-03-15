from pydantic import BaseModel, EmailStr
from typing import Optional
from app.models.user import UserRole




class UserCreate(BaseModel):
    email: EmailStr
    password: str
    first_name: str
    last_name: str
    phone: Optional[str] = None
    role: Optional[UserRole] = UserRole.client
    activity: Optional[str] = None
    terms_accepted: Optional[bool] = False

class UserLogin(BaseModel):
    id: int
    email: EmailStr
    first_name: str
    last_name: str
    phone: Optional[str]
    role: UserRole
    activity: Optional[str]
    terms_accepted: bool

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class UserResponse(BaseModel):
    id: int
    email: EmailStr
    first_name: str
    last_name: str
    phone: Optional[str] = None
    role: UserRole
    activity: Optional[str] = None
    is_active: bool

    class Config:
        orm_mode = True  # Muy importante para poder pasar directamente objetos SQLAlchemy

class ResetPasswordRequest(BaseModel):
    new_password: str


class UserUpdate(BaseModel):
    first_name: Optional[str]
    last_name: Optional[str]
    phone: Optional[str]