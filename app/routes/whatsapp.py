"""Webhook para receber mensagens do WhatsApp via Evolution API."""

import logging
import re
from dataclasses import dataclass
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from sqlalchemy.exc import IntegrityError

from app.database import SessionLocal
from app.models.webhook_message import WebhookMessage
from app.security import mask_jid, mask_phone, require_whatsapp_webhook_token
from app.services.evolution_api import resolve_lid
from app.services.whatsapp_bot import handle_message

log = logging.getLogger(__name__)

router = APIRouter(prefix="/whatsapp", tags=["whatsapp"])


class SimpleMsgCache:
    """Fallback em memória para deduplicação quando o banco não estiver disponível."""

    def __init__(self, max_size: int = 2000):
        self._set: set[str] = set()
        self._list: list[str] = []
        self._max = max_size

    def is_new(self, msg_id: str) -> bool:
        if msg_id in self._set:
            return False
        self._set.add(msg_id)
        self._list.append(msg_id)
        if len(self._list) > self._max:
            old = self._list.pop(0)
            self._set.discard(old)
        return True


@dataclass
class IncomingMessage:
    phone: str
    text: str
    target: str
    key: dict[str, Any]
    message_id: str | None


_fallback_cache = SimpleMsgCache()


def _extract_text(message: dict[str, Any]) -> str:
    return (
        message.get("conversation")
        or message.get("extendedTextMessage", {}).get("text")
        or message.get("buttonsResponseMessage", {}).get("selectedButtonId")
        or message.get("listResponseMessage", {}).get("singleSelectReply", {}).get("selectedRowId")
        or ""
    )


def _is_direct_message(remote_jid: str) -> bool:
    return remote_jid.endswith("@s.whatsapp.net") or remote_jid.endswith("@lid")


def _extract_digits_from_jid(jid: str) -> str:
    return "".join(re.findall(r"\d+", jid.split("@")[0]))


def _normalize_br_phone(phone: str) -> str:
    # 55 + DDD + 8 dígitos -> insere 9 para padronizar em 13 dígitos
    if len(phone) == 12 and phone.startswith("55"):
        return phone[:4] + "9" + phone[4:]
    return phone


def _is_messages_upsert_event(event: str) -> bool:
    normalized = event.strip().lower()
    return normalized in {"messages.upsert", "messages_upsert"}


def _persist_message_id(message_id: str, phone: str) -> bool:
    db = SessionLocal()
    try:
        db.add(WebhookMessage(message_id=message_id, phone=phone))
        db.commit()
        return True
    except IntegrityError:
        db.rollback()
        return False
    except Exception:
        db.rollback()
        # Fallback em memória para não perder deduplicação em caso de falha de DB.
        return _fallback_cache.is_new(message_id)
    finally:
        db.close()


async def _run_handler_async(phone: str, text: str, target: str, key: dict | None):
    db = SessionLocal()
    try:
        await handle_message(db, phone, text, target, key)
    except Exception:
        log.exception("whatsapp_handler_failed phone=%s target=%s", mask_phone(phone), mask_jid(target))
    finally:
        db.close()


async def _build_incoming_message(body: dict[str, Any]) -> IncomingMessage | None:
    data = body.get("data") or {}
    key = data.get("key") or {}
    message = data.get("message") or {}

    if not message or key.get("fromMe") is True:
        return None

    remote_jid = key.get("remoteJid", "")
    if not _is_direct_message(remote_jid):
        return None

    text = _extract_text(message).strip()
    if not text:
        return None

    phone = _normalize_br_phone(_extract_digits_from_jid(remote_jid))
    if not phone:
        return None

    target = remote_jid
    if remote_jid.endswith("@lid"):
        resolved_target = await resolve_lid(remote_jid)
        if resolved_target != remote_jid:
            target = resolved_target
            resolved_phone = _normalize_br_phone(_extract_digits_from_jid(resolved_target))
            if resolved_phone:
                phone = resolved_phone

    message_id = key.get("id")
    return IncomingMessage(phone=phone, text=text, target=target, key=key, message_id=message_id)


@router.post("/webhook", dependencies=[Depends(require_whatsapp_webhook_token)])
async def webhook(request: Request, background_tasks: BackgroundTasks):
    try:
        body = await request.json()
    except Exception:
        log.warning("whatsapp_webhook_ignored reason=invalid_json")
        return {"status": "ignored", "reason": "invalid_json"}

    event = body.get("event", "")
    if not _is_messages_upsert_event(event):
        log.info("whatsapp_webhook_ignored reason=event_not_supported event=%s", event or "unknown")
        return {"status": "ignored", "reason": f"event_{event or 'unknown'}"}

    incoming = await _build_incoming_message(body)
    if incoming is None:
        data = body.get("data") or {}
        key = data.get("key") or {}
        message = data.get("message") or {}
        log.info(
            "whatsapp_webhook_ignored reason=unsupported_message from_me=%s has_message=%s remote_jid=%s",
            key.get("fromMe"),
            bool(message),
            mask_jid(key.get("remoteJid", "")),
        )
        return {"status": "ignored", "reason": "unsupported_message"}

    if incoming.message_id and not _persist_message_id(incoming.message_id, incoming.phone):
        log.info(
            "whatsapp_webhook_ignored reason=duplicated_message message_id=%s phone=%s",
            incoming.message_id,
            mask_phone(incoming.phone),
        )
        return {"status": "ignored", "reason": "duplicated_message"}

    log.info(
        "whatsapp_message_received phone=%s target=%s message_id=%s",
        mask_phone(incoming.phone),
        mask_jid(incoming.target),
        incoming.message_id or "none",
    )

    background_tasks.add_task(
        _run_handler_async,
        incoming.phone,
        incoming.text,
        incoming.target,
        incoming.key,
    )
    return {"status": "success", "message": "processing"}
