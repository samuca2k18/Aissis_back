import json
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.database import Base
from app.models.agenda import Agenda
from app.models.cliente import Cliente
from app.models.documento import Documento
from app.models.negocio import Negocio
from app.models.whatsapp_session import WhatsappSession
from app.services import evolution_api
from app.services.whatsapp_bot import handle_message


def _build_db_session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    local_session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    return local_session()


def _seed_menu_session(db: Session, phone: str) -> WhatsappSession:
    session = WhatsappSession(phone=phone, state="menu", data_json="{}")
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


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


@pytest.mark.asyncio
async def test_receipt_menu_option_generates_pdf_document(monkeypatch):
    text_calls: list[str] = []
    media_calls: list[tuple[str, bytes, str]] = []

    async def fake_send_text(phone: str, text: str):
        text_calls.append(text)
        return {"status": "ok"}

    async def fake_send_buttons(phone: str, text: str, buttons: list[dict], title: str = "", footer: str = ""):
        text_calls.append(text)
        return {"status": "ok"}

    async def fake_send_media(phone: str, media_bytes: bytes, filename: str, caption: str = ""):
        media_calls.append((filename, media_bytes, caption))
        return {"status": "ok"}

    def fake_gerar_recibo_pdf(**kwargs):
        return b"%PDF-recibo"

    monkeypatch.setattr(evolution_api, "send_text", fake_send_text)
    monkeypatch.setattr(evolution_api, "send_buttons", fake_send_buttons)
    monkeypatch.setattr(evolution_api, "send_media", fake_send_media)
    monkeypatch.setattr("app.services.whatsapp_bot.gerar_recibo_pdf", fake_gerar_recibo_pdf)

    phone = "5585991234567"
    monkeypatch.setattr("app.services.whatsapp_bot.settings.WHATSAPP_ADMIN_PHONES", phone)
    db = _build_db_session()
    try:
        _seed_menu_session(db, phone)

        await handle_message(db, phone, "4")
        await handle_message(db, phone, "Maria Cliente")
        await handle_message(db, phone, "R$ 1.200,00")
        await handle_message(db, phone, "Afinacao completa")
        await handle_message(db, phone, "SIM")

        session = db.query(WhatsappSession).filter(WhatsappSession.phone == phone).first()
        assert session is not None
        assert session.state == "menu"

        documento = db.query(Documento).one()
        assert documento.tipo == "recibo"
        assert documento.pdf_bytes == b"%PDF-recibo"

        negocio = db.query(Negocio).one()
        assert negocio.status == "fechado"
        assert float(negocio.valor) == 1200.0

        assert len(media_calls) == 1
        assert media_calls[0][0] == f"recibo_{documento.id}.pdf"
    finally:
        db.close()


@pytest.mark.asyncio
async def test_quick_client_registration_flow_creates_client(monkeypatch):
    async def fake_send_text(phone: str, text: str):
        return {"status": "ok"}

    async def fake_send_buttons(phone: str, text: str, buttons: list[dict], title: str = "", footer: str = ""):
        return {"status": "ok"}

    monkeypatch.setattr(evolution_api, "send_text", fake_send_text)
    monkeypatch.setattr(evolution_api, "send_buttons", fake_send_buttons)

    phone = "5585997654321"
    monkeypatch.setattr("app.services.whatsapp_bot.settings.WHATSAPP_ADMIN_PHONES", phone)
    db = _build_db_session()
    try:
        _seed_menu_session(db, phone)

        await handle_message(db, phone, "7")
        await handle_message(db, phone, "Joao Cliente")
        await handle_message(db, phone, "85999990000")
        await handle_message(db, phone, "Fortaleza/CE")

        cliente = db.query(Cliente).one()
        assert cliente.nome == "Joao Cliente"
        assert cliente.telefone == "85999990000"
        assert cliente.cidade == "Fortaleza/CE"

        session = db.query(WhatsappSession).filter(WhatsappSession.phone == phone).first()
        assert session is not None
        assert session.state == "menu"
    finally:
        db.close()


@pytest.mark.asyncio
async def test_service_done_flow_marks_agenda_as_completed(monkeypatch):
    async def fake_send_text(phone: str, text: str):
        return {"status": "ok"}

    async def fake_send_buttons(phone: str, text: str, buttons: list[dict], title: str = "", footer: str = ""):
        return {"status": "ok"}

    monkeypatch.setattr(evolution_api, "send_text", fake_send_text)
    monkeypatch.setattr(evolution_api, "send_buttons", fake_send_buttons)

    phone = "5585981112222"
    monkeypatch.setattr("app.services.whatsapp_bot.settings.WHATSAPP_ADMIN_PHONES", phone)
    db = _build_db_session()
    try:
        _seed_menu_session(db, phone)
        evento = Agenda(
            titulo="Afinacao piano",
            data_hora=datetime.now() + timedelta(days=1),
            tipo="afinacao",
            descricao="Teste",
        )
        db.add(evento)
        db.commit()
        db.refresh(evento)

        await handle_message(db, phone, "9")
        await handle_message(db, phone, str(evento.id))
        await handle_message(db, phone, "NÃO")

        refreshed = db.query(Agenda).filter(Agenda.id == evento.id).one()
        assert refreshed.concluido is True

        session = db.query(WhatsappSession).filter(WhatsappSession.phone == phone).first()
        assert session is not None
        assert session.state == "menu"
    finally:
        db.close()
