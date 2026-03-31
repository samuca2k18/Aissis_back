from app.routes.whatsapp import (
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
