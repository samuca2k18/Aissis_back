"""Helpers de segurança e privacidade para a API."""

import re

from fastapi import Header, HTTPException, status

from app.settings import settings


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


def require_api_key(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> None:
    """Exige API key para rotas de negócio quando BACKEND_API_KEY estiver configurada."""
    expected = settings.BACKEND_API_KEY.strip()
    if not expected:
        return
    if x_api_key != expected:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key.")


def require_whatsapp_webhook_token(
    x_webhook_token: str | None = Header(default=None, alias="X-Webhook-Token"),
) -> None:
    """Protege webhook do WhatsApp quando WHATSAPP_WEBHOOK_TOKEN estiver configurada."""
    expected = settings.WHATSAPP_WEBHOOK_TOKEN.strip()
    if not expected:
        return
    if x_webhook_token != expected:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid webhook token.")
