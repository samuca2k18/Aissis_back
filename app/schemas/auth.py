from pydantic import BaseModel, Field

from app.schemas.user import UserOut


class LoginInput(BaseModel):
    email: str = Field(min_length=5, max_length=255)
    password: str = Field(min_length=8, max_length=128)


class BootstrapAdminInput(BaseModel):
    nome: str = Field(min_length=2, max_length=150)
    email: str = Field(min_length=5, max_length=255)
    password: str = Field(min_length=8, max_length=128)


class TokenOutput(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: int
    user: UserOut
