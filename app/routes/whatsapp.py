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
        log.warning("WEBHOOK: body inválido (não é JSON)")
        return {"status": "ignored", "reason": "invalid_json"}

    event = body.get("event", "unknown")
    log.info(f"📬 WEBHOOK EVENT: [{event}]")

    # Só processar mensagens recebidas (upsert)
    if event != "messages.upsert":
        return {"status": "ignored", "reason": f"event_{event}"}

    data = body.get("data", {})\
    
    # Log do remoteJid e messageType para diagnóstico
    key = data.get("key", {})
    remote_jid = key.get("remoteJid", "N/A")
    from_me = key.get("fromMe", False)
    message = data.get("message", {})
    msg_types = list(message.keys()) if message else []
    log.warning(f"📬 UPSERT → remoteJid={remote_jid} | fromMe={from_me} | msgTypes={msg_types}")

    # Ignorar se não houver corpo de mensagem (ex: só status/presença)
    if not message:
        return {"status": "ignored", "reason": "no_message_body"}

    # Ignorar mensagens enviadas por nós (fromMe)
    if from_me is True:
        return {"status": "ignored", "reason": "sent_by_me"}

    # Extrair JID e texto
    remote_jid = key.get("remoteJid", "")
    if not remote_jid or not (remote_jid.endswith("@s.whatsapp.net") or remote_jid.endswith("@lid")):
        log.warning(f"📬 IGNORADO: não é DM — remote_jid={remote_jid}")
        return {"status": "ignored", "reason": "not_a_dm"}

    # Extrair texto ou ID de botão/lista
    text = (
        message.get("conversation")
        or message.get("extendedTextMessage", {}).get("text")
        or message.get("buttonsResponseMessage", {}).get("selectedButtonId")
        or message.get("listResponseMessage", {}).get("singleSelectReply", {}).get("selectedRowId")
        or ""
    )

    if not text.strip():
        log.warning(f"📬 IGNORADO: sem texto — tipos disponíveis: {msg_types}")
        return {"status": "ignored", "reason": "non_text_message"}

    # ── LOG DE DIAGNÓSTICO (TEMPORÁRIO) ──────────────────────────────────
    import json
    log.warning(f"📬 FULL WEBHOOK BODY: {json.dumps(body, ensure_ascii=False)}")
    
    # O remote_jid é a fonte da verdade de quem enviou (pode vir como @s.whatsapp.net ou @lid)
    import re
    phone = "".join(re.findall(r"\d+", remote_jid.split("@")[0]))
    
    if not phone:
        log.warning(f"📬 IGNORADO: impossível extrair dígitos de remote_jid={remote_jid}")
        return {"status": "ignored", "reason": "invalid_phone"}

    log.warning(f"📩 MENSAGEM RECEBIDA [{phone}]: '{text[:80]}'")

    # EXECUÇÃO ASSÍNCRONA:
    # Passamos o 'remote_jid' como o 'target' para garantir entrega ao remetente original
    # Passamos o 'key' para permitir o "quoted reply" caso seja um LID bloqueado
    background_tasks.add_task(handle_message, db, phone, text, remote_jid, key)

    return {"status": "success", "message": "processing"}
