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
_lid_cache: dict[str, str] = {}


def _url(path: str) -> str:
    return f"{_BASE}/{path}/{_INSTANCE}"


async def resolve_lid(lid_jid: str) -> str:
    """Resolve um JID @lid para o JID real @s.whatsapp.net via contacts da Evolution API.
    Retorna o JID real se encontrado, caso contrário retorna o próprio lid_jid.
    """
    if lid_jid in _lid_cache:
        return _lid_cache[lid_jid]

    try:
        # Tenta buscar o contato pelo ID do LID
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(
                _url("chat/findContacts"),
                json={"where": {"id": lid_jid}},
                headers=_HEADERS,
            )
            if r.status_code in (200, 201):
                contacts = r.json()
                if isinstance(contacts, list) and contacts:
                    # Procurar um campo que contenha o número real
                    for contact in contacts:
                        # O campo 'owner' ou 'number' pode conter o número real
                        number = contact.get("number") or contact.get("pushName")
                        real_jid = contact.get("remoteJid") or contact.get("jid")
                        
                        # Se encontrou um JID @s.whatsapp.net diferente do @lid
                        if real_jid and "@s.whatsapp.net" in real_jid:
                            _lid_cache[lid_jid] = real_jid
                            log.warning(f"🔗 LID Resolvido: {lid_jid} → {real_jid}")
                            return real_jid
                        
                        # Se tem um campo 'number' com dígitos
                        if number and number.replace("+", "").isdigit():
                            resolved = f"{number.replace('+', '')}@s.whatsapp.net"
                            _lid_cache[lid_jid] = resolved
                            log.warning(f"🔗 LID Resolvido via number: {lid_jid} → {resolved}")
                            return resolved
                    
                    # Log do que foi retornado para diagnóstico
                    log.warning(f"🔍 Contacts para LID {lid_jid}: {contacts[:2]}")
                else:
                    log.warning(f"🔍 Nenhum contato encontrado para LID {lid_jid}")
            else:
                log.warning(f"🔍 findContacts retornou {r.status_code}: {r.text[:200]}")
    except Exception as e:
        log.warning(f"🔍 Erro ao resolver LID {lid_jid}: {e}")

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
