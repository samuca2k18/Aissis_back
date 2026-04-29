from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.user import User
from app.security import hash_password, verify_password
from app.settings import settings


def has_any_user(db: Session) -> bool:
    return db.query(User.id).first() is not None


def normalize_email(email: str) -> str:
    return email.strip().lower()


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.query(User).filter(User.email == normalize_email(email)).first()


def list_users(db: Session) -> list[User]:
    return db.query(User).order_by(User.created_at.desc()).all()


def create_user(
    db: Session,
    nome: str,
    email: str,
    password: str,
    role: str,
    is_active: bool = True,
) -> User:
    role_normalized = role.strip().lower()
    if role_normalized not in {"admin", "comercial", "atendimento"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Role inválida.")

    normalized_email = normalize_email(email)
    exists = get_user_by_email(db, normalized_email)
    if exists:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Já existe um usuário com este e-mail.")

    user = User(
        nome=nome.strip(),
        email=normalized_email,
        password_hash=hash_password(password),
        role=role_normalized,
        is_active=is_active,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate_user(db: Session, email: str, password: str) -> User:
    user = get_user_by_email(db, email)
    if not user or not verify_password(password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciais inválidas.")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Usuário inativo.")
    user.last_login_at = datetime.now(UTC)
    db.commit()
    db.refresh(user)
    return user


def update_user_status(db: Session, user_id: int, is_active: bool) -> User:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuário não encontrado.")
    user.is_active = is_active
    db.commit()
    db.refresh(user)
    return user


def bootstrap_admin_if_needed(db: Session) -> None:
    if not settings.AUTH_BOOTSTRAP_ADMIN:
        return
    if not settings.INITIAL_ADMIN_EMAIL.strip() or not settings.INITIAL_ADMIN_PASSWORD.strip():
        return

    if has_any_user(db):
        return

    admin = get_user_by_email(db, settings.INITIAL_ADMIN_EMAIL)
    if admin:
        return

    create_user(
        db=db,
        nome=settings.INITIAL_ADMIN_NAME,
        email=settings.INITIAL_ADMIN_EMAIL,
        password=settings.INITIAL_ADMIN_PASSWORD,
        role="admin",
        is_active=True,
    )
