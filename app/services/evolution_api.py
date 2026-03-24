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


# Cache de LID → JID real (evita consultas repetidas)
# Mapeamentos conhecidos podem ser adicionados aqui manualmente
_lid_cache: dict[str, str] = {
    "244770354012263@lid": "5585996224425@s.whatsapp.net",  # Maressa
}


def _url(path: str) -> str:
    return f"{_BASE}/{path}/{_INSTANCE}"


async def resolve_lid(lid_jid: str) -> str:
    """Resolve um JID @lid para o JID real @s.whatsapp.net.
    Tenta múltiplas estratégias: findChats, findContacts.
    Retorna o JID real se encontrado, caso contrário retorna o próprio lid_jid.
    """
    if lid_jid in _lid_cache:
        return _lid_cache[lid_jid]

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            # Estratégia 1: findChats — busca o chat pelo remoteJid do LID
            try:
                r = await client.post(
                    _url("chat/findChats"),
                    json={"where": {"remoteJid": lid_jid}},
                    headers=_HEADERS,
                )
                if r.status_code in (200, 201):
                    chats = r.json()
                    log.warning(f"🔍 findChats para {lid_jid}: {str(chats)[:500]}")
                    if isinstance(chats, list):
                        for chat in chats:
                            # Procura campo 'phone' ou 'number' com o telefone real
                            for field in ("phone", "number", "name"):
                                val = chat.get(field, "")
                                if val and val.replace("+", "").replace(" ", "").isdigit():
                                    digits = val.replace("+", "").replace(" ", "")
                                    resolved = f"{digits}@s.whatsapp.net"
                                    _lid_cache[lid_jid] = resolved
                                    log.warning(f"🔗 LID Resolvido via chat.{field}: {lid_jid} → {resolved}")
                                    return resolved
            except Exception as e:
                log.warning(f"🔍 Erro findChats: {e}")

            # Estratégia 2: findContacts — busca contato pelo ID do LID
            try:
                r = await client.post(
                    _url("chat/findContacts"),
                    json={"where": {"id": lid_jid}},
                    headers=_HEADERS,
                )
                if r.status_code in (200, 201):
                    contacts = r.json()
                    log.warning(f"🔍 findContacts para {lid_jid}: {str(contacts)[:500]}")
                    if isinstance(contacts, list):
                        for contact in contacts:
                            # Procura o campo 'id' que seja @s.whatsapp.net
                            cid = contact.get("id", "")
                            if "@s.whatsapp.net" in cid:
                                _lid_cache[lid_jid] = cid
                                log.warning(f"🔗 LID Resolvido via contact.id: {lid_jid} → {cid}")
                                return cid
            except Exception as e:
                log.warning(f"🔍 Erro findContacts: {e}")

    except Exception as e:
        log.warning(f"🔍 Erro geral ao resolver LID {lid_jid}: {e}")

    log.warning(f"⚠️ LID não resolvido: {lid_jid} — mensagem pode não ser entregue")
    return lid_jid


async def send_text(phone: str, text: str) -> dict:
    """Envia uma mensagem de texto simples via Evolution API v2."""
    # Adicionar sufixo
    if not phone.endswith("@s.whatsapp.net") and not phone.endswith("@g.us") and not phone.endswith("@lid") and "|" not in phone:
        phone = f"{phone}@s.whatsapp.net"

    options = {"delay": 0, "linkPreview": False}
    if "|" in phone:
        phone, msg_id = phone.split("|", 1)
        options["quoted"] = {
            "key": {
                "remoteJid": phone,
                "fromMe": False,
                "id": msg_id
            }
        }

    payload = {
        "number": phone,
        "text": text,
        "options": options
    }
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            r = await client.post(_url("message/sendText"), json=payload, headers=_HEADERS)
            if r.status_code != 201 and r.status_code != 200:
                log.error(f"Erro Evolution (sendText): {r.status_code} - {r.text}")
                # Se falhou com JID @lid, tenta converter para @s.whatsapp.net e re-enviar (fallback manual)
                if "@lid" in phone and r.status_code == 400:
                    import re
                    digits = "".join(re.findall(r"\d+", phone.split("@")[0]))
                    if digits:
                        log.warning(f"🔄 Fallback LID -> s.whatsapp.net: {digits}")
                        return await send_text(digits, text)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            log.error(f"ERRO CRÍTICO EVOLUTION (send_text): {e}")
            return {"status": "error", "message": str(e)}


async def send_media(phone: str, media_bytes: bytes, filename: str, caption: str = "") -> dict:
    """Envia um documento via Evolution API v2 usando base64."""
    import base64

    if not phone.endswith("@s.whatsapp.net") and not phone.endswith("@g.us") and not phone.endswith("@lid") and "|" not in phone:
        phone = f"{phone}@s.whatsapp.net"

    b64_data = base64.b64encode(media_bytes).decode("utf-8")
    mime_type, _ = mimetypes.guess_type(filename)
    if not mime_type:
        mime_type = "application/octet-stream"
        
    options = {"delay": 0}
    if "|" in phone:
        phone, msg_id = phone.split("|", 1)
        options["quoted"] = {
            "key": {
                "remoteJid": phone,
                "fromMe": False,
                "id": msg_id
            }
        }

    payload = {
        "number": phone,
        "mediatype": "document",
        "mimetype": mime_type,
        "media": b64_data,
        "fileName": filename,
        "caption": caption,
        "options": options
    }
    async with httpx.AsyncClient(timeout=60) as client:
        try:
            r = await client.post(_url("message/sendMedia"), json=payload, headers=_HEADERS)
            if r.status_code != 201 and r.status_code != 200:
                log.error(f"Erro Evolution (sendMedia): {r.status_code} - {r.text}")
                # Fallback LID
                if "@lid" in phone and r.status_code == 400:
                    import re
                    digits = "".join(re.findall(r"\d+", phone.split("@")[0]))
                    if digits:
                        log.warning(f"🔄 Fallback LID -> s.whatsapp.net (Media): {digits}")
                        return await send_media(digits, media_bytes, filename, caption)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            log.error(f"ERRO CRÍTICO EVOLUTION (send_media): {e}")
            return {"status": "error", "message": str(e)}


async def send_buttons(phone: str, text: str, buttons: list[dict], title: str = "", footer: str = "") -> dict:
    """Envia mensagens com botões interativos via Evolution API v2.
    Se a API não suportar botões, faz fallback para texto simples com opções numeradas.
    """
    if "@" not in phone and "|" not in phone:
        phone = f"{phone}@s.whatsapp.net"
        
    # Extrai msg_id se existir, para o fallback
    msg_id = None
    if "|" in phone:
        phone, msg_id = phone.split("|", 1)

    formatted_buttons = []
    for btn in buttons:
        label = btn.get("label", btn.get("displayText", btn.get("text")))
        formatted_buttons.append({
            "type": "reply",
            "displayText": label,
            "text": label,
            "id": str(btn.get("id", label))
        })

    payload = {
        "number": phone,
        "title": title,
        "description": text,
        "footer": footer,
        "buttons": formatted_buttons
    }

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(_url("message/sendButtons"), json=payload, headers=_HEADERS)
            if r.status_code in (200, 201):
                return r.json()
            log.warning(f"send_buttons retornou {r.status_code} — usando fallback de texto. Body: {r.text[:200]}")
            # Se falhou com 400 em LID, o fallback de texto será chamado abaixo com o phone original
    except Exception as e:
        log.warning(f"send_buttons falhou ({e}) — usando fallback de texto")

    # ── Fallback: texto simples com opções numeradas ──────────────────────────
    opcoes = "\n".join(
        f"{btn.get('id')}️⃣  {btn.get('label', btn.get('displayText'))}"
        for btn in buttons
    )
    fallback_text = f"{text}\n\n{opcoes}"
    if footer:
        fallback_text += f"\n\n_{footer}_"
        
    # Re-embutimos o msg_id para garantir que o send_text consiga fazer o quoted reply
    fallback_phone = f"{phone}|{msg_id}" if msg_id else phone
    return await send_text(fallback_phone, fallback_text)
