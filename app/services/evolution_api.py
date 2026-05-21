"""Cliente HTTP para a Evolution API (envio de mensagens e mídia via WhatsApp)."""

import json
import logging
import mimetypes
import re

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
def _load_lid_map() -> dict[str, str]:
    raw = settings.WHATSAPP_LID_MAP_JSON.strip()
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        log.warning("WHATSAPP_LID_MAP_JSON inválido. Ignorando mapa estático de LID.")
        return {}

    if not isinstance(parsed, dict):
        log.warning("WHATSAPP_LID_MAP_JSON deve ser um objeto JSON. Ignorando valor informado.")
        return {}

    normalized: dict[str, str] = {}
    for lid, jid in parsed.items():
        if isinstance(lid, str) and isinstance(jid, str) and lid.endswith("@lid") and "@" in jid:
            normalized[lid] = jid
    return normalized


_lid_cache: dict[str, str] = _load_lid_map()

# Cache reverso: phone@s.whatsapp.net → LID@lid
# Populado automaticamente quando o webhook resolve um LID
_phone_to_lid: dict[str, str] = {}


def register_lid_mapping(phone_jid: str, lid_jid: str) -> None:
    """Registra o mapeamento bidirecional entre phone JID e LID JID."""
    if lid_jid and phone_jid and lid_jid.endswith("@lid") and "@s.whatsapp.net" in phone_jid:
        _lid_cache[lid_jid] = phone_jid
        _phone_to_lid[phone_jid] = lid_jid
        # Também registra variantes BR do telefone
        digits = "".join(re.findall(r"\d+", phone_jid.split("@")[0]))
        for variant in _br_phone_variants(digits):
            variant_jid = f"{variant}@s.whatsapp.net"
            _phone_to_lid[variant_jid] = lid_jid
        log.info(f"📋 LID mapeado: {phone_jid} ↔ {lid_jid}")


def _br_phone_variants(digits: str) -> list[str]:
    """Gera variantes brasileiras de número (com/sem 9° dígito)."""
    variants: list[str] = []
    if not digits.startswith("55") or len(digits) not in (12, 13):
        return variants
    if len(digits) == 13 and digits[4] == "9":
        # 5585996224425 → 558596224425 (sem o 9)
        variants.append(digits[:4] + digits[5:])
    if len(digits) == 12:
        # 558596224425 → 5585996224425 (com o 9)
        variants.append(digits[:4] + "9" + digits[4:])
    return variants


def _url(path: str) -> str:
    return f"{_BASE}/{path}/{_INSTANCE}"


def _timeout(seconds: float | None = None) -> httpx.Timeout:
    return httpx.Timeout(seconds if seconds is not None else settings.EVOLUTION_API_TIMEOUT_SECONDS)


async def check_evolution_health() -> bool:
    """Verifica conectividade básica com a Evolution API."""
    if not _BASE:
        return False

    try:
        async with httpx.AsyncClient(timeout=_timeout(3.0)) as client:
            response = await client.get(f"{_BASE}/")
        return response.status_code < 500
    except Exception:
        return False


async def resolve_lid(lid_jid: str) -> str:
    """Resolve um JID @lid para o JID real @s.whatsapp.net.
    Tenta múltiplas estratégias: contact/profile, findChats, findContacts.
    Retorna o JID real se encontrado, caso contrário retorna o próprio lid_jid.
    """
    if lid_jid in _lid_cache:
        return _lid_cache[lid_jid]

    try:
        async with httpx.AsyncClient(timeout=_timeout()) as client:
            # Estratégia 0: contact/profile — endpoint mais confiável para resolver LID
            try:
                # Codifica o JID para usar na URL
                import urllib.parse
                encoded_jid = urllib.parse.quote(lid_jid, safe="")
                r = await client.get(
                    f"{_BASE}/chat/findContacts/{_INSTANCE}?where[id]={encoded_jid}",
                    headers=_HEADERS,
                )
                if r.status_code in (200, 201):
                    data = r.json()
                    log.info(f"🔍 findContacts (query) para {lid_jid}: {str(data)[:500]}")
                    contacts = data if isinstance(data, list) else [data] if isinstance(data, dict) else []
                    for contact in contacts:
                        # Tenta pegar o 'owner' que costuma ter o número real
                        for field in ("owner", "id"):
                            val = contact.get(field, "")
                            if isinstance(val, str) and val.endswith("@s.whatsapp.net"):
                                _lid_cache[lid_jid] = val
                                log.info(f"🔗 LID Resolvido via contact.{field}: {lid_jid} → {val}")
                                return val
                        # Tenta extrair o número do campo 'number' ou 'pushName'
                        for field in ("number", "phone"):
                            val = contact.get(field, "")
                            if val and str(val).replace("+", "").replace(" ", "").isdigit():
                                digits = str(val).replace("+", "").replace(" ", "")
                                resolved = f"{digits}@s.whatsapp.net"
                                _lid_cache[lid_jid] = resolved
                                log.info(f"🔗 LID Resolvido via contact.{field}: {lid_jid} → {resolved}")
                                return resolved
            except Exception as e:
                log.warning(f"🔍 Erro findContacts (query): {e}")

            # Estratégia 1: findChats — busca o chat pelo remoteJid do LID
            try:
                r = await client.post(
                    _url("chat/findChats"),
                    json={"where": {"remoteJid": lid_jid}},
                    headers=_HEADERS,
                )
                if r.status_code in (200, 201):
                    chats = r.json()
                    log.info(f"🔍 findChats para {lid_jid}: {str(chats)[:500]}")
                    if isinstance(chats, list):
                        for chat in chats:
                            # Procura campo 'phone' ou 'number' com o telefone real
                            for field in ("phone", "number", "name"):
                                val = chat.get(field, "")
                                if val and val.replace("+", "").replace(" ", "").isdigit():
                                    digits = val.replace("+", "").replace(" ", "")
                                    resolved = f"{digits}@s.whatsapp.net"
                                    _lid_cache[lid_jid] = resolved
                                    log.info(f"🔗 LID Resolvido via chat.{field}: {lid_jid} → {resolved}")
                                    return resolved
            except Exception as e:
                log.warning(f"🔍 Erro findChats: {e}")

            # Estratégia 2: findContacts (POST) — busca contato pelo ID do LID
            try:
                r = await client.post(
                    _url("chat/findContacts"),
                    json={"where": {"id": lid_jid}},
                    headers=_HEADERS,
                )
                if r.status_code in (200, 201):
                    contacts = r.json()
                    log.info(f"🔍 findContacts (POST) para {lid_jid}: {str(contacts)[:500]}")
                    if isinstance(contacts, list):
                        for contact in contacts:
                            # Procura o campo 'id' que seja @s.whatsapp.net
                            cid = contact.get("id", "")
                            if "@s.whatsapp.net" in cid:
                                _lid_cache[lid_jid] = cid
                                log.info(f"🔗 LID Resolvido via contact.id: {lid_jid} → {cid}")
                                return cid
            except Exception as e:
                log.warning(f"🔍 Erro findContacts (POST): {e}")

    except Exception as e:
        log.warning(f"🔍 Erro geral ao resolver LID {lid_jid}: {e}")

    log.warning(f"⚠️ LID não resolvido: {lid_jid} — mensagem pode não ser entregue")
    return lid_jid


async def send_text(phone: str, text: str, _depth: int = 0) -> dict:
    """Envia uma mensagem de texto simples via Evolution API v2.
    _depth: controle interno de recursão para evitar loops infinitos de fallback.
    """
    if _depth > 3:
        log.error(f"send_text: profundidade máxima de fallback atingida para {phone}")
        return {"status": "error", "message": "max fallback depth reached"}

    # Adicionar sufixo
    if not phone.endswith("@s.whatsapp.net") and not phone.endswith("@g.us") and not phone.endswith("@lid") and "|" not in phone:
        phone = f"{phone}@s.whatsapp.net"

    msg_id: str | None = None
    quoted: dict[str, object] | None = None
    if "|" in phone:
        phone, msg_id = phone.split("|", 1)
        quoted_key: dict[str, object] = {"id": msg_id}
        if "@" in phone:
            quoted_key["remoteJid"] = phone
            quoted_key["fromMe"] = False
            quoted_key["participant"] = phone
            quoted_key["owner"] = phone
        quoted = {
            "key": {
                **quoted_key,
            }
        }

    payload: dict[str, object] = {
        "number": phone,
        "text": text,
        "delay": 0,
        "linkPreview": False,
    }
    if quoted:
        payload["quoted"] = quoted

    async with httpx.AsyncClient(timeout=_timeout(30.0)) as client:
        try:
            r = await client.post(_url("message/sendText"), json=payload, headers=_HEADERS)
            if r.status_code in (200, 201):
                return r.json()

            log.error(f"Erro Evolution (sendText): {r.status_code} - {r.text}")

            if r.status_code != 400:
                r.raise_for_status()

            # ── Cadeia de fallback para 400 Bad Request ──────────────────

            # Fallback 1: Se @s.whatsapp.net falhou, tenta variante BR (com/sem 9°)
            if "@s.whatsapp.net" in phone:
                digits = "".join(re.findall(r"\d+", phone.split("@")[0]))
                for variant in _br_phone_variants(digits):
                    variant_target = f"{variant}@s.whatsapp.net"
                    if variant_target != phone:
                        log.warning(f"🔄 Fallback variante BR: {phone} → {variant_target}")
                        result = await send_text(
                            f"{variant_target}|{msg_id}" if msg_id else variant_target,
                            text, _depth + 1,
                        )
                        if result.get("status") != "error":
                            return result

            # Fallback 2: Se @s.whatsapp.net (ou variante) falhou, tenta LID do cache reverso
            if "@s.whatsapp.net" in phone:
                mapped_lid = _phone_to_lid.get(phone)
                if not mapped_lid:
                    # Tenta buscar por variantes do telefone
                    digits = "".join(re.findall(r"\d+", phone.split("@")[0]))
                    for variant in _br_phone_variants(digits):
                        mapped_lid = _phone_to_lid.get(f"{variant}@s.whatsapp.net")
                        if mapped_lid:
                            break
                if mapped_lid:
                    lid_target = f"{mapped_lid}|{msg_id}" if msg_id else mapped_lid
                    log.warning(f"🔄 Fallback → LID do cache reverso: {phone} → {mapped_lid}")
                    return await send_text(lid_target, text, _depth + 1)

            # Fallback 3: Se @lid falhou, tenta JID canônico do _lid_cache
            if "@lid" in phone:
                mapped_jid = _lid_cache.get(phone)
                if mapped_jid and mapped_jid != phone:
                    retry_target = f"{mapped_jid}|{msg_id}" if msg_id else mapped_jid
                    log.warning(f"🔄 Fallback LID → JID mapeado: {phone} → {mapped_jid}")
                    return await send_text(retry_target, text, _depth + 1)
                # Último recurso: extrai dígitos do LID e tenta como @s.whatsapp.net
                digits = "".join(re.findall(r"\d+", phone.split("@")[0]))
                if digits:
                    log.warning(f"🔄 Fallback LID → dígitos: {digits}")
                    return await send_text(digits, text, _depth + 1)

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

    msg_id: str | None = None
    quoted: dict[str, object] | None = None
    if "|" in phone:
        phone, msg_id = phone.split("|", 1)
        quoted_key: dict[str, object] = {"id": msg_id}
        if "@" in phone:
            quoted_key["remoteJid"] = phone
            quoted_key["fromMe"] = False
            quoted_key["participant"] = phone
            quoted_key["owner"] = phone
        quoted = {
            "key": {
                **quoted_key,
            }
        }

    payload: dict[str, object] = {
        "number": phone,
        "mediatype": "document",
        "mimetype": mime_type,
        "media": b64_data,
        "fileName": filename,
        "caption": caption,
        "delay": 0,
    }
    if quoted:
        payload["quoted"] = quoted

    async with httpx.AsyncClient(timeout=_timeout(60.0)) as client:
        try:
            r = await client.post(_url("message/sendMedia"), json=payload, headers=_HEADERS)
            if r.status_code in (200, 201):
                return r.json()

            log.error(f"Erro Evolution (sendMedia): {r.status_code} - {r.text}")

            if r.status_code != 400:
                r.raise_for_status()

            # ── Cadeia de fallback para 400 (mesma lógica do send_text) ──

            # Fallback 1: variante BR (com/sem 9°)
            if "@s.whatsapp.net" in phone:
                digits = "".join(re.findall(r"\d+", phone.split("@")[0]))
                for variant in _br_phone_variants(digits):
                    variant_target = f"{variant}@s.whatsapp.net"
                    if variant_target != phone:
                        log.warning(f"🔄 Fallback variante BR (Media): {phone} → {variant_target}")
                        result = await send_media(
                            f"{variant_target}|{msg_id}" if msg_id else variant_target,
                            media_bytes, filename, caption,
                        )
                        if result.get("status") != "error":
                            return result

            # Fallback 2: LID do cache reverso
            if "@s.whatsapp.net" in phone:
                mapped_lid = _phone_to_lid.get(phone)
                if not mapped_lid:
                    digits = "".join(re.findall(r"\d+", phone.split("@")[0]))
                    for variant in _br_phone_variants(digits):
                        mapped_lid = _phone_to_lid.get(f"{variant}@s.whatsapp.net")
                        if mapped_lid:
                            break
                if mapped_lid:
                    lid_target = f"{mapped_lid}|{msg_id}" if msg_id else mapped_lid
                    log.warning(f"🔄 Fallback → LID (Media): {phone} → {mapped_lid}")
                    return await send_media(lid_target, media_bytes, filename, caption)

            # Fallback 3: @lid → JID canônico
            if "@lid" in phone:
                mapped_jid = _lid_cache.get(phone)
                if mapped_jid and mapped_jid != phone:
                    retry_target = f"{mapped_jid}|{msg_id}" if msg_id else mapped_jid
                    log.warning(f"🔄 Fallback LID → JID (Media): {phone} → {mapped_jid}")
                    return await send_media(retry_target, media_bytes, filename, caption)
                digits = "".join(re.findall(r"\d+", phone.split("@")[0]))
                if digits:
                    log.warning(f"🔄 Fallback LID → dígitos (Media): {digits}")
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

    if settings.WHATSAPP_USE_BUTTONS:
        payload = {
            "number": phone,
            "title": title,
            "description": text,
            "footer": footer,
            "buttons": formatted_buttons
        }

        try:
            async with httpx.AsyncClient(timeout=_timeout(30.0)) as client:
                r = await client.post(_url("message/sendButtons"), json=payload, headers=_HEADERS)
                if r.status_code in (200, 201):
                    return r.json()
                log.warning(f"send_buttons retornou {r.status_code} — usando fallback de texto. Body: {r.text[:200]}")
                # Se falhou com 400 em LID, o fallback de texto será chamado abaixo com o phone original
        except Exception as e:
            log.warning(f"send_buttons falhou ({e}) — usando fallback de texto")

    # ── Fallback: texto simples com opções numeradas ──────────────────────────
    opcoes_linhas: list[str] = []
    for btn in buttons:
        button_id = str(btn.get("id", "")).strip()
        label = btn.get("label", btn.get("displayText", button_id))
        prefix = f"{button_id})" if button_id else "-"
        opcoes_linhas.append(f"{prefix} {label}")
    opcoes = "\n".join(opcoes_linhas)
    fallback_text = f"{text}\n\n{opcoes}"
    if footer:
        fallback_text += f"\n\n_{footer}_"

    # Re-embutimos o msg_id para garantir que o send_text consiga fazer o quoted reply
    fallback_phone = f"{phone}|{msg_id}" if msg_id else phone
    return await send_text(fallback_phone, fallback_text)
