from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

UserRole = Literal["admin", "comercial", "atendimento"]


class UserCreate(BaseModel):
    nome: str = Field(min_length=2, max_length=150)
    email: str = Field(min_length=5, max_length=255)
    password: str = Field(min_length=8, max_length=128)
    role: UserRole = "atendimento"
    is_active: bool = True


class UserStatusUpdate(BaseModel):
    is_active: bool


class UserOut(BaseModel):
    id: int
    nome: str
    email: str
    role: UserRole
    is_active: bool
    last_login_at: datetime | None
    created_at: datetime
    model_config = {"from_attributes": True}
