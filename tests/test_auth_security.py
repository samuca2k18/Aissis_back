import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app.security import (
    ServicePrincipal,
    create_access_token,
    decode_access_token,
    has_permission,
    hash_password,
    require_bootstrap_token,
    require_whatsapp_webhook_token,
    verify_password,
)
from app.settings import settings


def test_hash_and_verify_password():
    hashed = hash_password("SenhaSegura123")
    assert verify_password("SenhaSegura123", hashed)
    assert not verify_password("SenhaErrada", hashed)


def test_access_token_roundtrip():
    principal = ServicePrincipal(id=99, nome="svc", email="svc@local", role="service")
    token, _ = create_access_token(principal)
    payload = decode_access_token(token)
    assert payload["sub"] == "99"
    assert payload["role"] == "service"


def test_role_permissions_matrix():
    assert has_permission("admin", "clientes", "write")
    assert has_permission("comercial", "negocios", "write")
    assert not has_permission("atendimento", "campanhas", "write")


def test_bootstrap_token_is_required_and_validated(monkeypatch):
    monkeypatch.setattr(settings, "AUTH_BOOTSTRAP_TOKEN", "bootstrap-seguro")
    with pytest.raises(HTTPException) as exc_missing:
        require_bootstrap_token(None)
    assert exc_missing.value.status_code == 401

    with pytest.raises(HTTPException) as exc_invalid:
        require_bootstrap_token("errado")
    assert exc_invalid.value.status_code == 401

    require_bootstrap_token("bootstrap-seguro")


def test_whatsapp_webhook_token_must_be_configured(monkeypatch):
    monkeypatch.setattr(settings, "WHATSAPP_WEBHOOK_TOKEN", "")
    request = Request({"type": "http", "headers": [], "query_string": b""})
    with pytest.raises(HTTPException) as exc:
        require_whatsapp_webhook_token(request, None, None, None)
    assert exc.value.status_code == 503


def test_whatsapp_webhook_token_accepts_query_token(monkeypatch):
    monkeypatch.setattr(settings, "WHATSAPP_WEBHOOK_TOKEN", "token-seguro")
    request = Request({"type": "http", "headers": [], "query_string": b"token=token-seguro"})
    require_whatsapp_webhook_token(request, None, "token-seguro", None)
