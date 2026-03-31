from app.security import mask_jid, mask_phone


def test_mask_phone_keeps_only_small_exposure():
    assert mask_phone("5585996224425") == "55***25"
    assert mask_phone("85-99622-4480") == "85***80"


def test_mask_jid_masks_local_part():
    assert mask_jid("5585996224425@s.whatsapp.net") == "55***25@s.whatsapp.net"
    assert mask_jid("") == "unknown"
