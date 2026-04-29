from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app import schemas
from app.database import get_db
from app.models.user import User
from app.security import (
    Principal,
    create_access_token,
    get_current_user_required,
    require_bootstrap_token,
    require_role,
)
from app.services import auth as auth_service
from app.settings import settings

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/bootstrap-admin", response_model=schemas.UserOut, status_code=201)
def bootstrap_admin(
    payload: schemas.BootstrapAdminInput,
    _: None = Depends(require_bootstrap_token),
    db: Session = Depends(get_db),
):
    if not settings.AUTH_BOOTSTRAP_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bootstrap de admin desabilitado.",
        )
    if auth_service.has_any_user(db):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Já existe usuário cadastrado. Use /auth/users com conta admin.",
        )
    return auth_service.create_user(
        db=db,
        nome=payload.nome,
        email=payload.email,
        password=payload.password,
        role="admin",
        is_active=True,
    )


@router.post("/login", response_model=schemas.TokenOutput)
def login(payload: schemas.LoginInput, db: Session = Depends(get_db)):
    user = auth_service.authenticate_user(db, payload.email, payload.password)
    access_token, expires_at = create_access_token(user)
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_at": expires_at,
        "user": user,
    }


@router.get("/me", response_model=schemas.UserOut)
def me(current_user: Principal = Depends(get_current_user_required)):
    if not isinstance(current_user, User):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token de usuário obrigatório.")
    return current_user


@router.get("/users", response_model=list[schemas.UserOut], dependencies=[Depends(require_role("admin"))])
def list_users(db: Session = Depends(get_db)):
    return auth_service.list_users(db)


@router.post("/users", response_model=schemas.UserOut, status_code=201, dependencies=[Depends(require_role("admin"))])
def create_user(payload: schemas.UserCreate, db: Session = Depends(get_db)):
    return auth_service.create_user(
        db=db,
        nome=payload.nome,
        email=payload.email,
        password=payload.password,
        role=payload.role,
        is_active=payload.is_active,
    )


@router.patch("/users/{user_id}/status", response_model=schemas.UserOut, dependencies=[Depends(require_role("admin"))])
def update_user_status(user_id: int, payload: schemas.UserStatusUpdate, db: Session = Depends(get_db)):
    return auth_service.update_user_status(db, user_id, payload.is_active)
