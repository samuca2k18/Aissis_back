import pytest

from app.routes.whatsapp import (
    _build_incoming_message,
    _extract_digits_from_jid,
    _is_direct_message,
    _is_messages_upsert_event,
    _normalize_br_phone,
)


def test_is_messages_upsert_event_accepts_supported_formats():
    assert _is_messages_upsert_event("messages.upsert")
    assert _is_messages_upsert_event("MESSAGES_UPSERT")
    assert not _is_messages_upsert_event("presence.update")


def test_phone_normalization_for_legacy_br_numbers():
    assert _normalize_br_phone("558596224480") == "5585996224480"
    assert _normalize_br_phone("5585996224425") == "5585996224425"


def test_jid_helpers():
    assert _is_direct_message("5585996224425@s.whatsapp.net")
    assert _is_direct_message("244770354012263@lid")
    assert not _is_direct_message("1203630@g.us")
    assert _extract_digits_from_jid("244770354012263@lid") == "244770354012263"


@pytest.mark.asyncio
async def test_build_incoming_message_prefers_remote_jid_alt_for_lid():
    body = {
        "data": {
            "key": {
                "remoteJid": "28952559136882@lid",
                "remoteJidAlt": "5519989881838@s.whatsapp.net",
                "fromMe": False,
                "id": "msg-1",
            },
            "message": {"conversation": "menu"},
        }
    }

    incoming = await _build_incoming_message(body)

    assert incoming is not None
    assert incoming.target == "5519989881838@s.whatsapp.net"
    assert incoming.phone == "5519989881838"
    assert incoming.message_id == "msg-1"


@pytest.mark.asyncio
async def test_build_incoming_message_uses_lid_resolver_when_no_alt(monkeypatch):
    async def fake_resolve_lid(_: str) -> str:
        return "5585996224425@s.whatsapp.net"

    monkeypatch.setattr("app.routes.whatsapp.resolve_lid", fake_resolve_lid)
    body = {
        "data": {
            "key": {
                "remoteJid": "244770354012263@lid",
                "fromMe": False,
                "id": "msg-2",
            },
            "message": {"conversation": "menu"},
        }
    }

    incoming = await _build_incoming_message(body)

    assert incoming is not None
    assert incoming.target == "5585996224425@s.whatsapp.net"
    assert incoming.phone == "5585996224425"
    assert incoming.message_id == "msg-2"
