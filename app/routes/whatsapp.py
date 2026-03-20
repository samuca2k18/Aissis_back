"""Rota webhook para receber mensagens do WhatsApp via Evolution API."""

import logging

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.whatsapp_bot import handle_message

log = logging.getLogger(__name__)

router = APIRouter(prefix="/whatsapp", tags=["whatsapp"])


@router.post("/webhook")
async def webhook(request: Request, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """
    Endpoint que a Evolution API chama quando uma mensagem é recebida.
    """
    try:
        body = await request.json()
    except Exception:
        return {"status": "ignored", "reason": "invalid_json"}

    event = body.get("event", "unknown")

    # Log de debug para ver o flood de eventos
    log.info(f"WEBHOOK EVENT [{event}]")

    # Só processar mensagens recebidas (upsert)
    if event != "messages.upsert":
        return {"status": "ignored", "reason": f"event_{event}"}

    data = body.get("data", {})
    message = data.get("message", {})

    # Ignorar se não houver corpo de mensagem (ex: só status/presença)
    if not message:
        return {"status": "ignored", "reason": "no_message_body"}

    # Ignorar mensagens enviadas por nós (fromMe)
    key = data.get("key", {})
    if key.get("fromMe") is True:
        return {"status": "ignored", "reason": "sent_by_me"}

    # Extrair JID e texto
    remote_jid = key.get("remoteJid", "")
    if not remote_jid or not remote_jid.endswith("@s.whatsapp.net"):
        return {"status": "ignored", "reason": "not_a_dm"}

    text = (
        message.get("conversation")
        or message.get("extendedTextMessage", {}).get("text")
        or ""
    )

    if not text.strip():
        return {"status": "ignored", "reason": "non_text_message"}

    phone = remote_jid.split("@")[0]
    log.info(f"📩 MENSAGEM RECEBIDA [{phone}]: {text[:50]}...")

    # EXECUÇÃO ASSÍNCRONA:
    # Respondemos 200 OK imediatamente para evitar retries da Evolution API.
    background_tasks.add_task(handle_message, db, phone, text)

    return {"status": "success", "message": "processing"}
