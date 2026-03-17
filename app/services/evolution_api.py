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
    """Envia uma mensagem de texto simples via Evolution API."""
    payload = {
        "number": phone,
        "text": text,
    }
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(_url("message/sendText"), json=payload, headers=_HEADERS)
        r.raise_for_status()
        return r.json()


async def send_media(phone: str, media_bytes: bytes, filename: str, caption: str = "") -> dict:
    """Envia um documento (PDF, imagem etc.) via Evolution API usando base64."""
    import base64

    media_b64 = base64.b64encode(media_bytes).decode()
    ext = Path(filename).suffix.lstrip(".")
    mime = {
        "pdf": "application/pdf",
        "png": "image/png",
        "jpg": "image/jpeg",
    }.get(ext, "application/octet-stream")

    payload = {
        "number": phone,
        "media": media_b64,
        "mimetype": mime,
        "fileName": filename,
        "caption": caption,
    }
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(_url("message/sendMedia"), json=payload, headers=_HEADERS)
        r.raise_for_status()
        return r.json()
