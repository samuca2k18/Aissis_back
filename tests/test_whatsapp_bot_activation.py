import json
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.database import Base
from app.models.whatsapp_session import WhatsappSession
from app.services import evolution_api
from app.services.whatsapp_bot import handle_message


def _build_db_session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    local_session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    return local_session()


@pytest.mark.asyncio
async def test_sleeping_mode_ignores_non_menu_messages(monkeypatch):
    calls: list[tuple[str, str]] = []

    async def fake_send_text(phone: str, text: str):
        calls.append((phone, text))
        return {"status": "ok"}

    async def fake_send_buttons(phone: str, text: str, buttons: list[dict], title: str = "", footer: str = ""):
        calls.append((phone, text))
        return {"status": "ok"}

    monkeypatch.setattr(evolution_api, "send_text", fake_send_text)
    monkeypatch.setattr(evolution_api, "send_buttons", fake_send_buttons)

    db = _build_db_session()
    try:
        await handle_message(db, "5585999999999", "oi")
        session = db.query(WhatsappSession).filter(WhatsappSession.phone == "5585999999999").first()
        assert session is not None
        assert session.state == "sleeping"
        assert calls == []
    finally:
        db.close()


@pytest.mark.asyncio
async def test_sleeping_mode_wakes_with_menu_like_command(monkeypatch):
    calls: list[tuple[str, str]] = []

    async def fake_send_buttons(phone: str, text: str, buttons: list[dict], title: str = "", footer: str = ""):
        calls.append((phone, text))
        return {"status": "ok"}

    async def fake_send_text(phone: str, text: str):
        calls.append((phone, text))
        return {"status": "ok"}

    monkeypatch.setattr(evolution_api, "send_buttons", fake_send_buttons)
    monkeypatch.setattr(evolution_api, "send_text", fake_send_text)

    db = _build_db_session()
    try:
        await handle_message(db, "5585998888777", "menu")
        session = db.query(WhatsappSession).filter(WhatsappSession.phone == "5585998888777").first()
        assert session is not None
        assert session.state == "menu"
        assert len(calls) == 1
    finally:
        db.close()


@pytest.mark.asyncio
async def test_session_times_out_after_30_minutes_and_goes_to_sleep(monkeypatch):
    async def fake_send_buttons(phone: str, text: str, buttons: list[dict], title: str = "", footer: str = ""):
        return {"status": "ok"}

    async def fake_send_text(phone: str, text: str):
        return {"status": "ok"}

    monkeypatch.setattr(evolution_api, "send_buttons", fake_send_buttons)
    monkeypatch.setattr(evolution_api, "send_text", fake_send_text)

    db = _build_db_session()
    try:
        stale_at = (datetime.now(UTC) - timedelta(minutes=31)).isoformat()
        session = WhatsappSession(
            phone="5585988877665",
            state="menu",
            data_json=json.dumps({"_last_active": stale_at}),
        )
        db.add(session)
        db.commit()

        await handle_message(db, "5585988877665", "1")
        refreshed = db.query(WhatsappSession).filter(WhatsappSession.phone == "5585988877665").first()
        assert refreshed is not None
        assert refreshed.state == "sleeping"
    finally:
        db.close()
