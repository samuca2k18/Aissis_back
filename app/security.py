"""Autenticação, autorização e helpers de privacidade."""

import base64
import hashlib
import hmac
import json
import os
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import Depends, Header, HTTPException, Query, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.settings import settings

UserAction = str
UserModule = str


@dataclass
class ServicePrincipal:
    id: int = 0
    nome: str = "Service Account"
    email: str = "service@local"
    role: str = "service"
    is_active: bool = True


Principal = User | ServicePrincipal

_bearer_scheme = HTTPBearer(auto_error=False)

_ROLE_PERMISSIONS: dict[str, dict[UserModule, set[UserAction]]] = {
    "admin": {"*": {"read", "write"}},
    "service": {"*": {"read", "write"}},
    "comercial": {
        "clientes": {"read", "write"},
        "leads": {"read", "write"},
        "negocios": {"read", "write"},
        "documentos": {"read", "write"},
        "campanhas": {"read", "write"},
        "agenda": {"read"},
        "dashboard": {"read"},
        "auth": {"read"},
    },
    "atendimento": {
        "clientes": {"read", "write"},
        "leads": {"read"},
        "negocios": {"read"},
        "documentos": {"read", "write"},
        "campanhas": {"read"},
        "agenda": {"read", "write"},
        "dashboard": {"read"},
        "auth": {"read"},
    },
}


def mask_phone(value: str) -> str:
    digits = "".join(re.findall(r"\d+", value))
    if len(digits) <= 4:
        return "***"
    return f"{digits[:2]}***{digits[-2:]}"


def mask_jid(value: str) -> str:
    if not value:
        return "unknown"
    local, _, domain = value.partition("@")
    masked = mask_phone(local) if local else "***"
    return f"{masked}@{domain}" if domain else masked


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def _b64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def _sign(raw: bytes) -> str:
    secret = settings.AUTH_SECRET_KEY.encode("utf-8")
    return _b64url_encode(hmac.new(secret, raw, digestmod=hashlib.sha256).digest())


def hash_password(password: str) -> str:
    if len(password) < 8:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="A senha deve ter ao menos 8 caracteres.")
    salt = os.urandom(16)
    iterations = settings.AUTH_PASSWORD_ITERATIONS
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return (
        f"pbkdf2_sha256${iterations}$"
        f"{_b64url_encode(salt)}$"
        f"{_b64url_encode(digest)}"
    )


def verify_password(password: str, password_hash: str) -> bool:
    try:
        algorithm, iterations_str, salt_b64, digest_b64 = password_hash.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        iterations = int(iterations_str)
        salt = _b64url_decode(salt_b64)
        expected_digest = _b64url_decode(digest_b64)
    except Exception:
        return False

    actual_digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return hmac.compare_digest(expected_digest, actual_digest)


def create_access_token(principal: Principal) -> tuple[str, int]:
    expires_at = datetime.now(UTC) + timedelta(minutes=settings.AUTH_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": str(principal.id),
        "role": principal.role,
        "email": principal.email,
        "name": principal.nome,
        "exp": int(expires_at.timestamp()),
    }
    header_b64 = _b64url_encode(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode("utf-8"))
    payload_b64 = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{header_b64}.{payload_b64}".encode()
    signature = _sign(signing_input)
    token = f"{header_b64}.{payload_b64}.{signature}"
    return token, int(expires_at.timestamp())


def decode_access_token(token: str) -> dict[str, Any]:
    try:
        header_b64, payload_b64, signature = token.split(".", 2)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido.") from exc

    signing_input = f"{header_b64}.{payload_b64}".encode()
    expected_signature = _sign(signing_input)
    if not hmac.compare_digest(signature, expected_signature):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Assinatura do token inválida.")

    try:
        payload = json.loads(_b64url_decode(payload_b64).decode("utf-8"))
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Payload do token inválido.") from exc

    exp = payload.get("exp")
    if not isinstance(exp, int) or exp <= int(datetime.now(UTC).timestamp()):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expirado.")

    return payload


def has_permission(role: str, module: str, action: str) -> bool:
    role_perms = _ROLE_PERMISSIONS.get(role, {})
    if "*" in role_perms and action in role_perms["*"]:
        return True
    module_perms = role_perms.get(module, set())
    return action in module_perms


def require_api_key(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> None:
    """Exige API key para acesso técnico quando BACKEND_API_KEY estiver configurada."""
    expected = settings.BACKEND_API_KEY.strip()
    if not expected:
        return
    if x_api_key != expected:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key.")


def require_whatsapp_webhook_token(
    request: Request,
    x_webhook_token: str | None = Header(default=None, alias="X-Webhook-Token"),
    webhook_token: str | None = Query(default=None, alias="webhook_token"),
    token: str | None = Query(default=None, alias="token"),
) -> None:
    """Protege webhook do WhatsApp com token obrigatorio."""
    expected = settings.WHATSAPP_WEBHOOK_TOKEN.strip()
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Webhook token nao configurado no servidor.",
        )
    provided_token = x_webhook_token or webhook_token or token
    if not provided_token:
        provided_token = request.query_params.get("x_webhook_token")
    if not provided_token or not hmac.compare_digest(provided_token, expected):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid webhook token.")


def require_bootstrap_token(
    x_bootstrap_token: str | None = Header(default=None, alias="X-Bootstrap-Token"),
) -> None:
    """Exige token para bootstrap do primeiro admin."""
    expected = settings.AUTH_BOOTSTRAP_TOKEN.strip()
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Bootstrap token nao configurado no servidor.",
        )
    if not x_bootstrap_token or not hmac.compare_digest(x_bootstrap_token, expected):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid bootstrap token.")


def _resolve_api_key_principal(x_api_key: str | None) -> Principal | None:
    expected_api_key = settings.BACKEND_API_KEY.strip()
    if not x_api_key:
        return None
    if not expected_api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key.")
    if x_api_key != expected_api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key.")
    return ServicePrincipal()


def _attach_principal_to_request(request: Request, principal: Principal | None) -> None:
    request.state.auth_user = principal
    request.state.auth_user_id = getattr(principal, "id", None)
    request.state.auth_user_role = getattr(principal, "role", None)


def get_current_user_optional(
    request: Request,
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> Principal | None:
    if credentials is not None:
        payload = decode_access_token(credentials.credentials)
        user_id_str = str(payload.get("sub", "")).strip()
        if not user_id_str.isdigit():
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido.")
        user_id = int(user_id_str)
        user = db.query(User).filter(User.id == user_id).first()
        if not user or not user.is_active:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuário inválido ou inativo.")
        _attach_principal_to_request(request, user)
        return user

    principal = _resolve_api_key_principal(x_api_key)
    _attach_principal_to_request(request, principal)
    return principal


def get_current_user_required(
    current_user: Principal | None = Depends(get_current_user_optional),
) -> Principal:
    if current_user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Autenticação obrigatória.")
    return current_user


def require_role(role: str) -> Callable[[Principal | None], Principal]:
    def dependency(current_user: Principal | None = Depends(get_current_user_optional)) -> Principal:
        if not settings.AUTH_REQUIRED and current_user is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Autenticação obrigatória.")
        if current_user is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Autenticação obrigatória.")
        if current_user.role != role and current_user.role != "admin":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sem permissão para esta ação.")
        return current_user

    return dependency


def require_permission(module: str, action: str = "read") -> Callable[[Principal | None], Principal | None]:
    def dependency(current_user: Principal | None = Depends(get_current_user_optional)) -> Principal | None:
        if not settings.AUTH_REQUIRED and current_user is None:
            return None
        if current_user is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Autenticação obrigatória.")
        if not has_permission(current_user.role, module, action):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sem permissão para este módulo.")
        return current_user

    return dependency
