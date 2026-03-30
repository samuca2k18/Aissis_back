"""Rota webhook para receber mensagens do WhatsApp via Evolution API."""

import asyncio
import logging

from fastapi import APIRouter, Request

from app.database import SessionLocal
from app.services.whatsapp_bot import handle_message

log = logging.getLogger(__name__)

router = APIRouter(prefix="/whatsapp", tags=["whatsapp"])


async def _run_handler_async(phone: str, text: str, target: str, key: dict | None):
    """Wrapper que cria sua própria sessão DB para o processamento assíncrono."""
    db = SessionLocal()
    try:
        await handle_message(db, phone, text, target, key)
    except Exception as e:
        log.exception(f"❌ ERRO no handler assíncrono (handle_message): {e}")
    finally:
        db.close()


class SimpleMsgCache:
    """Cache em memória para evitar processamento duplicado da mesma mensagem."""
    def __init__(self, max_size=1000):
        self._set = set()
        self._list = []
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


_message_cache = SimpleMsgCache()


@router.post("/webhook")
async def webhook(request: Request):
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

    # ── Normalização de número BR ─────────────────────────────────────────
    # WhatsApp às vezes usa formato antigo de 8 dígitos (ex: 558596224425)
    # e às vezes o novo com 9 (ex: 5585996224425). Normalizamos para 13 dígitos.
    def _normalize_br_phone(p: str) -> str:
        if len(p) == 12 and p.startswith("55"):
            # 55 + DDD(2) + 8 dígitos → inserir o '9' após o DDD
            return p[:4] + "9" + p[4:]
        return p

    phone = _normalize_br_phone(phone)

    # ── Resolver LID → número real ────────────────────────────────────────
    # Se o JID é @lid, precisamos descobrir o número real do contato
    # para que a Evolution API consiga enviar a resposta
    from app.services.evolution_api import resolve_lid
    target = remote_jid
    if remote_jid.endswith("@lid"):
        target = await resolve_lid(remote_jid)
        log.warning(f"🔗 Target resolvido: {remote_jid} → {target}")
        # Se conseguimos resolver, usamos os dígitos do target real como phone
        if target != remote_jid:
            phone = _normalize_br_phone("".join(re.findall(r"\d+", target.split("@")[0])))

    log.warning(f"📩 MENSAGEM RECEBIDA [{phone}]: '{text[:80]}' | target={target}")

    # Evitar o problema de mensagens duplicadas disparadas pela Evolution API
    msg_id = key.get("id")
    if msg_id and not _message_cache.is_new(msg_id):
        log.warning(f"🚫 IGNORADO: Mensagem duplicada interceptada (ID já processado: {msg_id})")
        return {"status": "ignored", "reason": "duplicated_message"}

    # EXECUÇÃO ASSÍNCRONA: cria task independente com sessão DB própria
    asyncio.create_task(_run_handler_async(phone, text, target, key))

    return {"status": "success", "message": "processing"}
