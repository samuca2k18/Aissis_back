"""Rota webhook para receber mensagens do WhatsApp via Evolution API."""

import logging

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.whatsapp_bot import handle_message

log = logging.getLogger(__name__)

router = APIRouter(prefix="/whatsapp", tags=["whatsapp"])


@router.post("/webhook")
async def webhook(request: Request, db: Session = Depends(get_db)):
    """
    Endpoint que a Evolution API chama quando uma mensagem é recebida.

    O payload da Evolution API v2 tem a seguinte estrutura (simplificada):
    {
      "event": "messages.upsert",
      "data": {
        "key": { "remoteJid": "5585999999999@s.whatsapp.net", "fromMe": false },
        "message": { "conversation": "texto da mensagem" }
      }
    }
    """
    try:
        body = await request.json()
    except Exception:
        return {"status": "ignored", "reason": "invalid json"}

    event = body.get("event", "")

    # Só processar mensagens recebidas
    if event != "messages.upsert":
        return {"status": "ignored", "reason": f"event={event}"}

    data = body.get("data", {})

    # Ignorar mensagens enviadas por nós
    key = data.get("key", {})
    if key.get("fromMe", True):
        return {"status": "ignored", "reason": "fromMe"}

    remote_jid = key.get("remoteJid", "")

    if not remote_jid:
        return {"status": "ignored", "reason": "no jid"}

    # Ignorar grupos (@g.us) e status (@broadcast) — só responder DMs
    if not remote_jid.endswith("@s.whatsapp.net"):
        return {"status": "ignored", "reason": "not a DM"}

    # Extrair apenas o número (sem sufixo)
    phone = remote_jid.split("@")[0]

    # Extrair texto da mensagem
    message = data.get("message", {})
    text = (
        message.get("conversation")
        or message.get("extendedTextMessage", {}).get("text")
        or ""
    )

    if not text.strip():
        return {"status": "ignored", "reason": "empty text"}

    log.info("WhatsApp msg de %s: %s", phone, text[:100])

    await handle_message(db, phone, text)

    return {"status": "ok"}
