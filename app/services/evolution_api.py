"""Cliente HTTP para a Evolution API (envio de mensagens e mídia via WhatsApp)."""

import logging
from pathlib import Path

import httpx

from app.settings import settings

log = logging.getLogger(__name__)

_BASE = settings.EVOLUTION_API_URL.rstrip("/")
_INSTANCE = settings.EVOLUTION_API_INSTANCE
_HEADERS = {
    "apikey": settings.EVOLUTION_API_KEY,
    "Content-Type": "application/json",
}


def _url(path: str) -> str:
    return f"{_BASE}/{path}/{_INSTANCE}"


async def send_text(phone: str, text: str) -> dict:
    """Envia uma mensagem de texto simples via Evolution API v2."""
    # Adicionar sufixo se não houver
    if "@" not in phone:
        phone = f"{phone}@s.whatsapp.net"

    payload = {
        "number": phone,
        "text": text,
        "delay": 1200,
        "linkPreview": False
    }
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(_url("message/sendText"), json=payload, headers=_HEADERS)
        if r.status_code != 201 and r.status_code != 200:
             log.error(f"Erro Evolution: {r.status_code} - {r.text}")
        r.raise_for_status()
        return r.json()


async def send_media(phone: str, media_bytes: bytes, filename: str, caption: str = "") -> dict:
    """Envia um documento via Evolution API v2 usando base64."""
    import base64

    if "@" not in phone:
        phone = f"{phone}@s.whatsapp.net"

    media_b64 = base64.b64encode(media_bytes).decode()
    ext = Path(filename).suffix.lstrip(".")
    mime = {
        "pdf": "application/pdf",
        "png": "image/png",
        "jpg": "image/jpeg",
    }.get(ext, "application/octet-stream")

    payload = {
        "number": phone,
        "mediatype": "document",
        "media": media_b64,
        "mimetype": mime,
        "fileName": filename,
        "caption": caption,
    }
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(_url("message/sendMedia"), json=payload, headers=_HEADERS)
        if r.status_code != 201 and r.status_code != 200:
             log.error(f"Erro Evolution: {r.status_code} - {r.text}")
        r.raise_for_status()
        return r.json()


async def send_buttons(phone: str, text: str, buttons: list[dict], title: str = "", footer: str = "") -> dict:
    """Envia mensagens com botões interativos via Evolution API v2."""
    if "@" not in phone:
        phone = f"{phone}@s.whatsapp.net"

    # Formatar botões para o padrão da Evolution
    # Cada botão deve ser: {"type": "reply", "displayText": "Label", "id": "ID"}
    formatted_buttons = []
    for btn in buttons:
        formatted_buttons.append({
            "type": "reply",
            "displayText": btn.get("label", btn.get("displayText")),
            "id": btn.get("id", btn.get("label"))
        })

    payload = {
        "number": phone,
        "title": title,
        "description": text,
        "footer": footer,
        "buttons": formatted_buttons
    }

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(_url("message/sendButtons"), json=payload, headers=_HEADERS)
        if r.status_code != 201 and r.status_code != 200:
             log.error(f"Erro Evolution (Buttons): {r.status_code} - {r.text}")
        r.raise_for_status()
        return r.json()
