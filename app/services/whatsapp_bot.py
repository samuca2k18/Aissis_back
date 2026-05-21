"""
Máquina de estados do bot do WhatsApp.

Melhorias implementadas:
  1. UX aprimorada: resumos formatados, erros com exemplos, timeout de sessão
  2. Ativador por palavra-chave: apenas "menu" ativa o bot (modo silencioso)
  3. Consulta de agenda por data: "hoje", "amanhã", "semana" ou DD/MM
  4. Envio do PDF por WhatsApp após confirmar orçamento
  5. Reconhecimento de cliente existente pelo número de telefone
  6. Modo Silencioso: bot no número pessoal, ignora tudo até receber "menu"
"""

import json
import logging
from datetime import UTC, datetime, timedelta, timezone

from sqlalchemy import Date, cast, func, or_
from sqlalchemy.orm import Session

from app.models.agenda import Agenda
from app.models.cliente import Cliente
from app.models.documento import Documento
from app.models.negocio import Negocio
from app.models.whatsapp_session import WhatsappSession
from app.services import evolution_api
from app.services.pdf_generator import gerar_orcamento_pdf, gerar_recibo_pdf
from app.settings import settings

log = logging.getLogger(__name__)

# ─── Timeout de sessão: 30 minutos sem interação → adormecer silenciosamente ─
SESSION_TIMEOUT_MINUTES = 30

MENU_TEXT = (
    "🎹 *Assis Pianos — Atendimento Automático*\n\n"
    "Olá! Como posso ajudar? Escolha uma opção abaixo:\n"
    "Digite *0* para sair e deixar o bot dormindo."
)

PUBLIC_MENU_BUTTONS = [
    {"label": "Solicitar Orçamento", "id": "1"},
    {"label": "Agendar Serviço", "id": "2"},
]

ADMIN_MENU_BUTTONS = [
    *PUBLIC_MENU_BUTTONS,
    {"label": "Consultar Agenda", "id": "3"},
    {"label": "Gerar Recibo", "id": "4"},
    {"label": "Agenda de Hoje", "id": "5"},
    {"label": "Remarcar/Cancelar", "id": "6"},
    {"label": "Cadastrar Cliente", "id": "7"},
    {"label": "Buscar Cliente", "id": "8"},
    {"label": "Serviço Feito", "id": "9"},
    {"label": "Enviar Lembrete", "id": "10"},
]

MENU_BUTTONS = ADMIN_MENU_BUTTONS

MENU_TEXT_FALLBACK = (
    f"{MENU_TEXT}\n\n"
    + "\n".join(f"{b['id']}️⃣  {b['label']}" for b in MENU_BUTTONS)
)

# ─── palavras-chave para atalho (SOMENTE dentro do fluxo ativo) ─────────────
_KW_ORCAMENTO  = {"orçamento", "orcamento", "orcar", "orçar", "preço", "preco", "valor", "quanto"}
_KW_AGENDAR    = {"agendar", "agendamento", "marcar"}
_KW_RECIBO     = {"recibo", "comprovante", "quitacao", "quitação", "pagamento", "pago"}
_KW_AGENDA_HOJE = {"agenda hoje", "agenda de hoje", "hoje", "compromissos hoje"}
_KW_BUSCAR_CLIENTE = {"buscar cliente", "procurar cliente", "cliente"}
_KW_SERVICO_FEITO = {"serviço feito", "servico feito", "concluir serviço", "concluir servico", "finalizar serviço", "finalizar servico"}
_WAKE_WORDS    = {"menu", "iniciar", "inicio", "start", "ajuda"}
_SLEEP_WORDS   = {"0", "sair", "dormir", "pausar", "silencio", "silêncio"}


# ─── helpers ─────────────────────────────────────────────────────────────────

def _get_or_create_session(db: Session, phone: str) -> WhatsappSession:
    sess = db.query(WhatsappSession).filter(WhatsappSession.phone == phone).first()
    if not sess:
        # Inicia em modo silencioso: bot só ativa quando o usuário enviar "menu"
        sess = WhatsappSession(phone=phone, state="sleeping", data_json="{}")
        db.add(sess)
        db.commit()
        db.refresh(sess)
    return sess


def _save(db: Session, sess: WhatsappSession, state: str, data: dict | None = None):
    sess.state = state
    if data is not None:
        sess.data_json = json.dumps(data, ensure_ascii=False)
    # Registrar timestamp da última interação
    extra = json.loads(sess.data_json) if sess.data_json else {}
    extra["_last_active"] = datetime.now(UTC).isoformat()
    sess.data_json = json.dumps(extra, ensure_ascii=False)
    db.commit()


def _data(sess: WhatsappSession) -> dict:
    try:
        return json.loads(sess.data_json or "{}")
    except json.JSONDecodeError:
        return {}


def _is_timed_out(sess: WhatsappSession) -> bool:
    """Retorna True se a sessão ficou mais de SESSION_TIMEOUT_MINUTES inativa."""
    d = _data(sess)
    last = d.get("_last_active")
    if not last:
        return False
    try:
        last_dt = datetime.fromisoformat(last)
        if last_dt.tzinfo is None:
            last_dt = last_dt.replace(tzinfo=UTC)
        delta = datetime.now(UTC) - last_dt
        return delta > timedelta(minutes=SESSION_TIMEOUT_MINUTES)
    except Exception:
        return False


def _fmt_brl(valor: float) -> str:
    s = f"{valor:,.2f}"
    return "R$ " + s.replace(",", "X").replace(".", ",").replace("X", ".")


def _parse_money(value: str) -> float | None:
    cleaned = value.lower().replace("r$", "").strip()
    cleaned = cleaned.replace(" ", "")
    cleaned = "".join(ch for ch in cleaned if ch.isdigit() or ch in ",.")
    if not cleaned:
        return None

    if "," in cleaned:
        normalized = cleaned.replace(".", "").replace(",", ".")
    elif cleaned.count(".") == 1 and len(cleaned.rsplit(".", 1)[1]) == 3:
        normalized = cleaned.replace(".", "")
    else:
        normalized = cleaned

    try:
        parsed = float(normalized)
    except ValueError:
        return None
    return parsed if parsed > 0 else None


def _digits_only(value: str | None) -> str:
    if not value:
        return ""
    return "".join(ch for ch in value if ch.isdigit())


def _phone_variants(phone: str) -> set[str]:
    digits = _digits_only(phone)
    if not digits:
        return set()
    variants = {digits}
    if len(digits) >= 12 and digits.startswith("55"):
        variants.add(digits[2:])  # sem DDI
    if len(digits) in {10, 11} and not digits.startswith("55"):
        variants.add("55" + digits)  # com DDI
    if len(digits) == 12 and digits.startswith("55"):
        variants.add(digits[:4] + "9" + digits[4:])
    if len(digits) == 13 and digits.startswith("55") and digits[4] == "9":
        variants.add(digits[:4] + digits[5:])
    if len(digits) == 10:
        variants.add(digits[:2] + "9" + digits[2:])
    if len(digits) == 11 and digits[2] == "9":
        variants.add(digits[:2] + digits[3:])
    return variants


def _is_admin_phone(phone: str) -> bool:
    admin_phones = settings.whatsapp_admin_phones
    if not admin_phones:
        return True

    incoming_variants = _phone_variants(phone)
    for admin_phone in admin_phones:
        if incoming_variants.intersection(_phone_variants(admin_phone)):
            return True
    return False


def _menu_buttons(phone: str) -> list[dict]:
    return ADMIN_MENU_BUTTONS if _is_admin_phone(phone) else PUBLIC_MENU_BUTTONS


def _menu_fallback(phone: str) -> str:
    return (
        f"{MENU_TEXT}\n\n"
        + "\n".join(f"{b['id']}️⃣  {b['label']}" for b in _menu_buttons(phone))
    )


def _menu_options_hint(phone: str) -> str:
    ids = ", ".join(str(b["id"]) for b in _menu_buttons(phone))
    return f"{ids} ou 0"


def _find_cliente_by_phone(db: Session, phone: str) -> Cliente | None:
    incoming_variants = _phone_variants(phone)
    if not incoming_variants:
        return None
    for candidate in db.query(Cliente).filter(Cliente.telefone.isnot(None)).all():
        candidate_digits = _digits_only(candidate.telefone)
        if candidate_digits and candidate_digits in incoming_variants:
            return candidate
    return None


def _parse_datetime_pt(text: str) -> datetime | None:
    t = text.strip().lower()
    BRT = timezone(timedelta(hours=-3))
    hoje = datetime.now(BRT).date()

    if t.startswith("hoje ") or t.startswith("hoje,"):
        hora_str = t.split(" ", 1)[1].strip()
        try:
            h, m = map(int, hora_str.replace("h", ":").split(":"))
            return datetime(hoje.year, hoje.month, hoje.day, h, m)
        except Exception:
            return None

    if t.startswith("amanhã ") or t.startswith("amanha "):
        hora_str = t.split(" ", 1)[1].strip()
        try:
            h, m = map(int, hora_str.replace("h", ":").split(":"))
            amanha = hoje + timedelta(days=1)
            return datetime(amanha.year, amanha.month, amanha.day, h, m)
        except Exception:
            return None

    for fmt in ("%d/%m/%Y %H:%M", "%d/%m %H:%M"):
        try:
            parsed = datetime.strptime(text.strip(), fmt)
            if fmt == "%d/%m %H:%M":
                parsed = parsed.replace(year=hoje.year)
            return parsed
        except ValueError:
            continue
    return None


def _tipo_emoji(tipo: str) -> str:
    return {
        "afinacao": "🎵",
        "manutencao": "🔧",
        "entrega": "🚚",
        "evento": "📍",
        "followup": "📞",
        "outro": "📌",
    }.get(tipo, "📌")


def _format_event_line(ev: Agenda, include_id: bool = True) -> str:
    prefix = f"#{ev.id} " if include_id else ""
    status = " ✅" if ev.concluido else ""
    return f"{prefix}{_tipo_emoji(ev.tipo)} {ev.data_hora.strftime('%d/%m %H:%M')} — {ev.titulo}{status}"


def _pending_events(db: Session, limit: int = 10) -> list[Agenda]:
    return (
        db.query(Agenda)
        .filter(Agenda.concluido.is_(False))
        .order_by(Agenda.data_hora.asc())
        .limit(limit)
        .all()
    )


def _get_event(db: Session, evento_id: int) -> Agenda | None:
    return db.query(Agenda).filter(Agenda.id == evento_id).first()


def _format_client_reminder(ev: Agenda) -> str:
    return (
        "Olá! Passando para lembrar do seu agendamento com a Assis Pianos:\n\n"
        f"📅 *{ev.data_hora.strftime('%d/%m/%Y às %H:%M')}*\n"
        f"🔧 *Serviço:* {ev.titulo}\n\n"
        "Se precisar remarcar, responda esta mensagem."
    )


# ─── handler principal ──────────────────────────────────────────────────────

async def handle_message(
    db: Session,
    phone: str,
    text: str,
    recipient_jid: str | None = None,
    message_key: dict | None = None,
) -> None:
    """
    Processa uma mensagem recebida e responde via Evolution API.
    phone: apenas os dígitos (ex: 558599... para CRM)
    recipient_jid: ID completo do chat (ex: ...@lid ou ...@s.whatsapp.net para resposta)
    message_key: objeto 'key' da mensagem original (usado para bypass do bloqueio de @lid via 'quoted')
    """
    text = text.strip()
    sess = _get_or_create_session(db, phone)

    # Se não informar JID completo, tenta montar o padrão
    target = recipient_jid or f"{phone}@s.whatsapp.net"

    # Se o target já foi resolvido para @s.whatsapp.net pela rota do webhook,
    # NÃO devemos sobrescrever com o LID bruto do message_key.
    # Registramos o mapeamento LID→phone para que send_text possa usar como fallback.
    if message_key:
        original_remote_jid = str(message_key.get("remoteJid") or "").strip()
        msg_id = message_key.get("id")

        # Se temos um target @s.whatsapp.net e o message_key tem um LID,
        # registra o mapeamento para fallback em send_text/send_media
        if original_remote_jid.endswith("@lid") and "@s.whatsapp.net" in target:
            evolution_api.register_lid_mapping(target.split("|")[0], original_remote_jid)

        # Anexa msg_id para quoted reply (melhora entrega em contatos LID via fallback)
        if msg_id and "|" not in target:
            target = f"{target}|{msg_id}"

    # ── MODO SILENCIOSO: bot está dormindo ───────────────────────────────────
    if sess.state == "sleeping":
        t = text.lower().strip()
        import re
        words = set(re.findall(r'\w+', t))
        if words.intersection(_WAKE_WORDS):
            _save(db, sess, "menu", {})
            await evolution_api.send_buttons(target, MENU_TEXT, _menu_buttons(phone))
        # Qualquer outra mensagem obscura: ignorar completamente (sem resposta)
        return

    # ── Timeout de sessão: adormecer silenciosamente ──────────────────────
    if _is_timed_out(sess):
        _save(db, sess, "sleeping", {})
        # Silenciosamente dorme, exigindo comando de menu para acordar de novo
        return

    # ── Comando global: sair/dormir coloca o bot em modo silencioso ───────
    if text.lower().strip() in _SLEEP_WORDS:
        _save(db, sess, "sleeping", {})
        if sess.state == "menu":
            await evolution_api.send_text(
                target,
                "😴 Bot em modo silencioso.\nEnvie *menu* para ativar novamente."
            )
        return

    # ── Atalhos por palavras-chave (dentro do fluxo ativo) ──────────────
    if sess.state == "menu":
        t = text.lower().strip()
        is_admin = _is_admin_phone(phone)
        if is_admin and any(kw in t for kw in _KW_AGENDA_HOJE):
            await _handle_agenda_hoje(db, sess, phone, target)
            return
        if is_admin and any(kw in t for kw in _KW_SERVICO_FEITO):
            await _iniciar_servico_feito(db, sess, phone, target)
            return
        if is_admin and any(kw in t for kw in _KW_BUSCAR_CLIENTE):
            _save(db, sess, "busca_cliente", {})
            await evolution_api.send_text(target, "🔎 Envie o *nome ou telefone* do cliente que deseja buscar.")
            return
        if is_admin and any(kw in t for kw in _KW_RECIBO):
            await _iniciar_recibo(db, sess, phone, target)
            return
        if any(kw in t for kw in _KW_ORCAMENTO):
            await _iniciar_orcamento(db, sess, phone, target)
            return
        if any(kw in t for kw in _KW_AGENDAR):
            _save(db, sess, "ag_titulo", {})
            await evolution_api.send_text(
                target,
                "📅 *Agendamento* — Vamos agendar!\n\nQual o *título* do serviço?\n_(ex: Afinação Piano Yamaha)_"
            )
            return

    handler = STATE_HANDLERS.get(sess.state)
    if handler is None:
        # Estado desconhecido ou sleeping — mostrar menu
        await evolution_api.send_buttons(target, MENU_TEXT, _menu_buttons(phone))
        return
    await handler(db, sess, phone, text, target)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# MENU
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def _handle_menu(db: Session, sess: WhatsappSession, phone: str, text: str, target: str):
    if not _is_admin_phone(phone) and text not in {"1", "2"}:
        await evolution_api.send_text(
            target,
            f"⚠️ Esta opção é interna.\n\n{_menu_fallback(phone)}"
        )
        return

    if text == "1":
        await _iniciar_orcamento(db, sess, phone, target)
    elif text == "2":
        _save(db, sess, "ag_titulo", {})
        await evolution_api.send_text(
            target,
            "📅 *Agendamento* — Vamos agendar!\n\nQual o *título* do serviço?\n_(ex: Afinação Piano Yamaha)_"
        )
    elif text == "3":
        await _handle_agenda_query(db, sess, phone, target)
    elif text == "4":
        await _iniciar_recibo(db, sess, phone, target)
    elif text == "5":
        await _handle_agenda_hoje(db, sess, phone, target)
    elif text == "6":
        await _iniciar_remarcar_cancelar(db, sess, phone, target)
    elif text == "7":
        _save(db, sess, "cli_nome", {})
        await evolution_api.send_text(target, "👤 *Cadastro rápido*\n\nQual o *nome* do cliente?")
    elif text == "8":
        _save(db, sess, "busca_cliente", {})
        await evolution_api.send_text(target, "🔎 Envie o *nome ou telefone* do cliente que deseja buscar.")
    elif text == "9":
        await _iniciar_servico_feito(db, sess, phone, target)
    elif text == "10":
        await _iniciar_lembrete_cliente(db, sess, phone, target)
    else:
        # Aviso curto em vez de repetir todos os botões e texto toda vez
        await evolution_api.send_text(
            target,
            f"⚠️ Opção não reconhecida.\nPor favor, **digite {_menu_options_hint(phone)}** (ou escolha no botão acima)."
        )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# FLUXOS INTERNOS: AGENDA, CLIENTES, SERVIÇOS E LEMBRETES
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def _handle_agenda_hoje(db: Session, sess: WhatsappSession, phone: str, target: str):
    hoje = datetime.now(timezone(timedelta(hours=-3))).date()
    eventos = (
        db.query(Agenda)
        .filter(
            cast(Agenda.data_hora, Date) == hoje,
            Agenda.concluido.is_(False),
        )
        .order_by(Agenda.data_hora.asc())
        .all()
    )
    _save(db, sess, "menu", {})

    if not eventos:
        await evolution_api.send_text(
            target,
            f"📅 *Agenda de hoje ({hoje.strftime('%d/%m/%Y')})*\n\n"
            f"Nenhum compromisso pendente.\n\n{_menu_fallback(phone)}"
        )
        return

    linhas = [_format_event_line(ev) for ev in eventos]
    await evolution_api.send_text(
        target,
        f"📅 *Agenda de hoje ({hoje.strftime('%d/%m/%Y')}):*\n\n"
        + "\n".join(linhas)
        + f"\n\nTotal: {len(eventos)} compromisso(s).\n\n"
        + _menu_fallback(phone)
    )


async def _iniciar_remarcar_cancelar(db: Session, sess: WhatsappSession, phone: str, target: str):
    eventos = _pending_events(db)
    if not eventos:
        _save(db, sess, "menu", {})
        await evolution_api.send_text(target, "📅 Nenhum compromisso pendente para remarcar ou cancelar.\n\n" + _menu_fallback(phone))
        return

    _save(db, sess, "ev_acao_id", {})
    linhas = [_format_event_line(ev) for ev in eventos]
    await evolution_api.send_text(
        target,
        "📅 *Remarcar ou cancelar*\n\n"
        "Envie o *número* do compromisso:\n\n"
        + "\n".join(linhas)
        + "\n\nExemplo: `12`"
    )


async def _ev_acao_id(db: Session, sess: WhatsappSession, phone: str, text: str, target: str):
    try:
        evento_id = int(text.strip().lstrip("#"))
    except ValueError:
        await evolution_api.send_text(target, "⚠️ Envie apenas o número do compromisso. Exemplo: `12`")
        return

    ev = _get_event(db, evento_id)
    if not ev or ev.concluido:
        await evolution_api.send_text(target, "⚠️ Não encontrei esse compromisso pendente. Envie outro número.")
        return

    _save(db, sess, "ev_acao_tipo", {"evento_id": ev.id})
    await evolution_api.send_buttons(
        target,
        f"Selecionado:\n{_format_event_line(ev)}\n\nO que deseja fazer?",
        buttons=[
            {"label": "Remarcar", "id": "1"},
            {"label": "Cancelar", "id": "2"},
            {"label": "Voltar", "id": "3"},
        ],
    )


async def _ev_acao_tipo(db: Session, sess: WhatsappSession, phone: str, text: str, target: str):
    t = text.strip().lower()
    d = _data(sess)
    ev = _get_event(db, int(d.get("evento_id", 0)))
    if not ev:
        _save(db, sess, "menu", {})
        await evolution_api.send_text(target, "⚠️ Compromisso não encontrado.\n\n" + _menu_fallback(phone))
        return

    if t in {"1", "remarcar"}:
        _save(db, sess, "ev_remarcar_data", d)
        await evolution_api.send_text(
            target,
            "📅 Qual a *nova data e hora*?\n\n"
            "Formatos aceitos:\n"
            "`25/03/2026 14:00`\n"
            "`25/03 14:00`\n"
            "`hoje 14:00`\n"
            "`amanhã 09:30`"
        )
        return

    if t in {"2", "cancelar"}:
        _save(db, sess, "ev_cancelar_confirmar", d)
        await evolution_api.send_buttons(
            target,
            f"Confirma cancelar este compromisso?\n\n{_format_event_line(ev)}",
            buttons=[
                {"label": "SIM", "id": "SIM"},
                {"label": "NÃO", "id": "NÃO"},
            ],
        )
        return

    if t in {"3", "voltar", "cancelar operação", "cancelar operacao"}:
        _save(db, sess, "menu", {})
        await evolution_api.send_text(target, _menu_fallback(phone))
        return

    await evolution_api.send_text(target, "Responda *1* para remarcar, *2* para cancelar ou *3* para voltar.")


async def _ev_remarcar_data(db: Session, sess: WhatsappSession, phone: str, text: str, target: str):
    nova_data = _parse_datetime_pt(text)
    if nova_data is None:
        await evolution_api.send_text(target, "⚠️ Data inválida. Exemplo: `25/03/2026 14:00` ou `amanhã 09:30`")
        return

    d = _data(sess)
    ev = _get_event(db, int(d.get("evento_id", 0)))
    if not ev:
        _save(db, sess, "menu", {})
        await evolution_api.send_text(target, "⚠️ Compromisso não encontrado.\n\n" + _menu_fallback(phone))
        return

    ev.data_hora = nova_data
    db.commit()
    db.refresh(ev)
    _save(db, sess, "menu", {})
    await evolution_api.send_text(target, "✅ Compromisso remarcado:\n\n" + _format_event_line(ev) + "\n\n" + _menu_fallback(phone))


async def _ev_cancelar_confirmar(db: Session, sess: WhatsappSession, phone: str, text: str, target: str):
    upper = text.upper().strip()
    if upper in {"NÃO", "NAO", "N"}:
        _save(db, sess, "menu", {})
        await evolution_api.send_text(target, "Operação cancelada.\n\n" + _menu_fallback(phone))
        return
    if upper != "SIM":
        await evolution_api.send_text(target, "Responda *SIM* para cancelar ou *NÃO* para voltar.")
        return

    d = _data(sess)
    ev = _get_event(db, int(d.get("evento_id", 0)))
    if ev:
        resumo = _format_event_line(ev)
        db.delete(ev)
        db.commit()
        await evolution_api.send_text(target, "✅ Compromisso cancelado:\n\n" + resumo + "\n\n" + _menu_fallback(phone))
    else:
        await evolution_api.send_text(target, "⚠️ Compromisso não encontrado.\n\n" + _menu_fallback(phone))
    _save(db, sess, "menu", {})


async def _cli_nome(db: Session, sess: WhatsappSession, phone: str, text: str, target: str):
    d = _data(sess)
    d["nome"] = text.strip()
    _save(db, sess, "cli_telefone", d)
    await evolution_api.send_text(target, "📞 Qual o *telefone* do cliente?\n_(ex: 85999990000)_")


async def _cli_telefone(db: Session, sess: WhatsappSession, phone: str, text: str, target: str):
    d = _data(sess)
    d["telefone"] = text.strip()
    _save(db, sess, "cli_cidade", d)
    await evolution_api.send_text(target, "🏙️ Qual a *cidade* do cliente?\n_(ex: Fortaleza/CE)_")


async def _cli_cidade(db: Session, sess: WhatsappSession, phone: str, text: str, target: str):
    d = _data(sess)
    telefone = d["telefone"]
    cliente = _find_cliente_by_phone(db, telefone)
    if cliente:
        cliente.nome = d["nome"]
        cliente.cidade = text.strip()
    else:
        cliente = Cliente(
            nome=d["nome"],
            telefone=telefone,
            cidade=text.strip(),
            origem="whatsapp",
        )
        db.add(cliente)
    db.commit()
    db.refresh(cliente)
    _save(db, sess, "menu", {})
    await evolution_api.send_text(
        target,
        f"✅ Cliente salvo!\n\n"
        f"#{cliente.id} — *{cliente.nome}*\n"
        f"📞 {cliente.telefone}\n"
        f"🏙️ {cliente.cidade}\n\n"
        + _menu_fallback(phone)
    )


async def _busca_cliente(db: Session, sess: WhatsappSession, phone: str, text: str, target: str):
    termo = text.strip()
    digits = _digits_only(termo)
    filters = [func.lower(Cliente.nome).contains(termo.lower())]
    if digits:
        filters.append(Cliente.telefone.contains(digits))

    clientes = (
        db.query(Cliente)
        .filter(or_(*filters))
        .order_by(Cliente.created_at.desc())
        .limit(5)
        .all()
    )
    _save(db, sess, "menu", {})

    if not clientes:
        await evolution_api.send_text(target, "🔎 Nenhum cliente encontrado.\n\n" + _menu_fallback(phone))
        return

    linhas = []
    for cliente in clientes:
        negocio = (
            db.query(Negocio)
            .filter(Negocio.cliente_id == cliente.id)
            .order_by(Negocio.created_at.desc())
            .first()
        )
        agenda = (
            db.query(Agenda)
            .filter(Agenda.cliente_id == cliente.id, Agenda.concluido.is_(False))
            .order_by(Agenda.data_hora.asc())
            .first()
        )
        detalhes = [
            f"#{cliente.id} — *{cliente.nome}*",
            f"📞 {cliente.telefone}",
            f"🏙️ {cliente.cidade}",
        ]
        if negocio:
            detalhes.append(f"💼 Último negócio: {negocio.status} / {_fmt_brl(float(negocio.valor or 0))}")
        if agenda:
            detalhes.append(f"📅 Próximo: {agenda.data_hora.strftime('%d/%m %H:%M')} — {agenda.titulo}")
        linhas.append("\n".join(detalhes))

    await evolution_api.send_text(target, "🔎 *Clientes encontrados:*\n\n" + "\n\n".join(linhas) + "\n\n" + _menu_fallback(phone))


async def _iniciar_servico_feito(db: Session, sess: WhatsappSession, phone: str, target: str):
    eventos = _pending_events(db)
    if not eventos:
        _save(db, sess, "menu", {})
        await evolution_api.send_text(target, "📅 Nenhum compromisso pendente para concluir.\n\n" + _menu_fallback(phone))
        return

    _save(db, sess, "svc_done_id", {})
    linhas = [_format_event_line(ev) for ev in eventos]
    await evolution_api.send_text(
        target,
        "✅ *Registrar serviço feito*\n\n"
        "Envie o *número* do compromisso concluído:\n\n"
        + "\n".join(linhas)
    )


async def _svc_done_id(db: Session, sess: WhatsappSession, phone: str, text: str, target: str):
    try:
        evento_id = int(text.strip().lstrip("#"))
    except ValueError:
        await evolution_api.send_text(target, "⚠️ Envie apenas o número do compromisso. Exemplo: `12`")
        return

    ev = _get_event(db, evento_id)
    if not ev or ev.concluido:
        await evolution_api.send_text(target, "⚠️ Não encontrei esse compromisso pendente. Envie outro número.")
        return

    ev.concluido = True
    cliente = db.query(Cliente).filter(Cliente.id == ev.cliente_id).first() if ev.cliente_id else None
    if ev.negocio_id:
        negocio = db.query(Negocio).filter(Negocio.id == ev.negocio_id).first()
        if negocio:
            negocio.status = "fechado"
    db.commit()

    d = {
        "evento_id": ev.id,
        "pagador_nome": cliente.nome if cliente else "",
        "cliente_id": cliente.id if cliente else None,
    }
    _save(db, sess, "svc_done_recibo", d)
    await evolution_api.send_buttons(
        target,
        f"✅ Serviço marcado como feito:\n\n{_format_event_line(ev)}\n\nDeseja gerar recibo agora?",
        buttons=[
            {"label": "Gerar Recibo", "id": "SIM"},
            {"label": "Só Concluir", "id": "NÃO"},
        ],
    )


async def _svc_done_recibo(db: Session, sess: WhatsappSession, phone: str, text: str, target: str):
    upper = text.upper().strip()
    if upper in {"NÃO", "NAO", "N", "SÓ CONCLUIR", "SO CONCLUIR"}:
        _save(db, sess, "menu", {})
        await evolution_api.send_text(target, "✅ Serviço concluído.\n\n" + _menu_fallback(phone))
        return

    if upper not in {"SIM", "S", "GERAR RECIBO"}:
        await evolution_api.send_text(target, "Responda *SIM* para gerar recibo ou *NÃO* para só concluir.")
        return

    d = _data(sess)
    if d.get("pagador_nome"):
        _save(db, sess, "rec_valor", d)
        await evolution_api.send_text(target, "Qual o *valor recebido*?\n_(ex: 350,00 ou R$ 1.200,00)_")
    else:
        _save(db, sess, "rec_nome", d)
        await evolution_api.send_text(target, "Qual o *nome de quem pagou*?")


async def _iniciar_lembrete_cliente(db: Session, sess: WhatsappSession, phone: str, target: str):
    eventos = _pending_events(db)
    if not eventos:
        _save(db, sess, "menu", {})
        await evolution_api.send_text(target, "📅 Nenhum compromisso pendente para enviar lembrete.\n\n" + _menu_fallback(phone))
        return

    _save(db, sess, "lem_evento_id", {})
    linhas = [_format_event_line(ev) for ev in eventos]
    await evolution_api.send_text(
        target,
        "📨 *Enviar lembrete ao cliente*\n\n"
        "Envie o *número* do compromisso:\n\n"
        + "\n".join(linhas)
    )


async def _lem_evento_id(db: Session, sess: WhatsappSession, phone: str, text: str, target: str):
    try:
        evento_id = int(text.strip().lstrip("#"))
    except ValueError:
        await evolution_api.send_text(target, "⚠️ Envie apenas o número do compromisso. Exemplo: `12`")
        return

    ev = _get_event(db, evento_id)
    if not ev or ev.concluido:
        await evolution_api.send_text(target, "⚠️ Não encontrei esse compromisso pendente. Envie outro número.")
        return

    cliente = db.query(Cliente).filter(Cliente.id == ev.cliente_id).first() if ev.cliente_id else None
    if cliente and cliente.telefone:
        await evolution_api.send_text(cliente.telefone, _format_client_reminder(ev))
        _save(db, sess, "menu", {})
        await evolution_api.send_text(target, f"✅ Lembrete enviado para *{cliente.nome}*.\n\n" + _menu_fallback(phone))
        return

    _save(db, sess, "lem_phone", {"evento_id": ev.id})
    await evolution_api.send_text(target, "Esse compromisso não tem cliente vinculado. Envie o *telefone* para mandar o lembrete.")


async def _lem_phone(db: Session, sess: WhatsappSession, phone: str, text: str, target: str):
    d = _data(sess)
    ev = _get_event(db, int(d.get("evento_id", 0)))
    if not ev:
        _save(db, sess, "menu", {})
        await evolution_api.send_text(target, "⚠️ Compromisso não encontrado.\n\n" + _menu_fallback(phone))
        return

    await evolution_api.send_text(text.strip(), _format_client_reminder(ev))
    _save(db, sess, "menu", {})
    await evolution_api.send_text(target, "✅ Lembrete enviado.\n\n" + _menu_fallback(phone))


# ── Melhoria 5: Iniciar orçamento reconhecendo cliente existente ─────────────

async def _iniciar_orcamento(db: Session, sess: WhatsappSession, phone: str, target: str):
    """Inicia o fluxo de orçamento, reconhecendo cliente já cadastrado."""
    incoming_variants = _phone_variants(phone)
    cliente = None
    if incoming_variants:
        # Evita falso positivo por "contains": normaliza e compara variantes equivalentes.
        for candidate in db.query(Cliente).filter(Cliente.telefone.isnot(None)).all():
            candidate_digits = _digits_only(candidate.telefone)
            if candidate_digits and candidate_digits in incoming_variants:
                cliente = candidate
                break

    if cliente:
        # Melhoria 5: cliente já existe — preencher dados automaticamente
        d = {
            "cliente_nome": cliente.nome,
            "cliente_telefone": cliente.telefone,
            "cliente_cidade": cliente.cidade or "",
            "cliente_existente": True,
        }
        _save(db, sess, "orc_itens", d)
        await evolution_api.send_text(
            target,
            f"👋 Olá, *{cliente.nome}*! Encontrei seu cadastro.\n\n"
            f"📦 Agora informe os *itens do orçamento*.\n\n"
            "Envie cada item no formato:\n"
            "`descricao ; valor` ou `descricao valor`\n\n"
            "Exemplos:\n"
            "`Afinação completa ; 350`\n"
            "`Regulagem 500`\n\n"
            "💡 Pode enviar *vários de uma vez* (um por linha)!\n"
            "Quando terminar, envie *OK*."
        )
    else:
        _save(db, sess, "orc_nome", {})
        await evolution_api.send_text(
            target,
            "📝 *Orçamento* — Vamos começar!\n\nQual o *nome completo* do cliente?"
        )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# FLUXO: ORÇAMENTO
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def _orc_nome(db: Session, sess: WhatsappSession, phone: str, text: str, target: str):
    d = _data(sess)
    d["cliente_nome"] = text
    _save(db, sess, "orc_telefone", d)
    await evolution_api.send_text(target, "📞 Qual o *telefone* do cliente?\n_(ex: 85999990000)_")


async def _orc_telefone(db: Session, sess: WhatsappSession, phone: str, text: str, target: str):
    d = _data(sess)
    d["cliente_telefone"] = text
    _save(db, sess, "orc_cidade", d)
    await evolution_api.send_text(target, "🏙️ Qual a *cidade* do cliente?\n_(ex: Fortaleza/CE)_")


async def _orc_cidade(db: Session, sess: WhatsappSession, phone: str, text: str, target: str):
    d = _data(sess)
    d["cliente_cidade"] = text
    _save(db, sess, "orc_itens", d)
    await evolution_api.send_text(
        target,
        "📦 Informe os *itens do orçamento*.\n\n"
        "Envie cada item no formato:\n"
        "`descricao ; valor` ou `descricao valor`\n\n"
        "Exemplos:\n"
        "`Afinação completa ; 350`\n"
        "`Regulagem 500`\n\n"
        "💡 Pode enviar *vários de uma vez* (um por linha)!\n"
        "Quando terminar, envie *OK*."
    )


def _parse_item_line(line: str) -> tuple[str, float] | None:
    """Tenta parsear uma linha como item de orçamento.
    Suporta dois formatos:
      1. 'descricao ; valor'   → Afinação completa ; 350
      2. 'descricao valor'     → Afinação completa 350
    Retorna (descricao, valor) ou None se não conseguiu parsear.
    """
    line = line.strip()
    if not line:
        return None

    # Formato 1: com ponto-e-vírgula
    if ";" in line:
        parts = line.split(";")
        if len(parts) == 2:
            try:
                desc = parts[0].strip()
                valor = float(parts[1].strip().replace(",", "."))
                if desc and valor > 0:
                    return (desc, valor)
            except ValueError:
                pass
        return None

    # Formato 2: última "palavra" é o valor numérico
    tokens = line.rsplit(None, 1)  # split da direita, max 1 vez
    if len(tokens) == 2:
        try:
            desc = tokens[0].strip()
            valor = float(tokens[1].strip().replace(",", "."))
            if desc and valor > 0:
                return (desc, valor)
        except ValueError:
            pass

    return None


async def _orc_itens(db: Session, sess: WhatsappSession, phone: str, text: str, target: str):
    d = _data(sess)
    itens = d.get("itens", [])

    if text.upper() == "OK":
        if not itens:
            await evolution_api.send_text(
                target,
                "⚠️ Nenhum item adicionado ainda.\n\n"
                "Envie no formato: `descricao ; valor`\n"
                "Exemplo: `Afinação completa ; 350`"
            )
            return
        _save(db, sess, "orc_pagamento", d)
        resumo = "\n".join(f"  • {i['descricao']} — {_fmt_brl(i['valor'])}" for i in itens)
        total = sum(i["valor"] for i in itens)
        await evolution_api.send_text(
            target,
            f"📋 *Itens adicionados:*\n{resumo}\n\n"
            f"💰 *Total: {_fmt_brl(total)}*\n\n"
            "Qual a *condição de pagamento*?\n"
            "_(ex: 50% na retirada e 50% na entrega)_\n\n"
            "Ou envie *pular* para usar o padrão."
        )
        return

    # ── Parsear itens (suporta múltiplas linhas numa só mensagem) ──────────
    linhas = text.strip().split("\n")
    adicionados = []
    erros = []

    for linha in linhas:
        resultado = _parse_item_line(linha)
        if resultado:
            desc, valor = resultado
            itens.append({"descricao": desc, "valor": valor})
            adicionados.append(f"  ✅ {desc} — {_fmt_brl(valor)}")
        elif linha.strip():
            erros.append(f"  ⚠️ `{linha.strip()}`")

    if not adicionados and erros:
        await evolution_api.send_text(
            target,
            "⚠️ Não consegui ler os itens. Use um dos formatos:\n\n"
            "`descricao ; valor`\n"
            "`descricao valor`\n\n"
            "Exemplos:\n"
            "`Afinação completa ; 350`\n"
            "`Regulagem 500`\n\n"
            "Pode enviar *vários de uma vez* (um por linha)!"
        )
        return

    d["itens"] = itens
    _save(db, sess, "orc_itens", d)
    total_parcial = sum(i["valor"] for i in itens)

    msg = "\n".join(adicionados)
    if erros:
        msg += "\n\n⚠️ Linhas não reconhecidas:\n" + "\n".join(erros)
    msg += f"\n\n💰 *Subtotal: {_fmt_brl(total_parcial)}*"
    msg += "\n\nEnvie mais itens ou *OK* para continuar."

    await evolution_api.send_text(target, msg)


async def _orc_pagamento(db: Session, sess: WhatsappSession, phone: str, text: str, target: str):
    d = _data(sess)
    if text.lower() != "pular":
        d["condicoes_pagamento"] = text
    else:
        d["condicoes_pagamento"] = "40% na retirada e restante na entrega"
    _save(db, sess, "orc_confirmar", d)

    itens = d["itens"]
    total = sum(i["valor"] for i in itens)
    resumo = "\n".join(f"  • {i['descricao']} — {_fmt_brl(i['valor'])}" for i in itens)

    await evolution_api.send_buttons(
        target,
        f"📄 *Resumo do Orçamento:*\n\n"
        f"👤 *Cliente:* {d['cliente_nome']}\n"
        f"📞 *Telefone:* {d['cliente_telefone']}\n"
        f"🏙️ *Cidade:* {d['cliente_cidade']}\n\n"
        f"📦 *Itens:*\n{resumo}\n\n"
        f"💰 *Total: {_fmt_brl(total)}*\n"
        f"💳 *Pagamento:* {d['condicoes_pagamento']}\n\n"
        "Confirma?",
        buttons=[
            {"label": "SIM", "id": "SIM"},
            {"label": "NÃO", "id": "NÃO"}
        ]
    )


async def _orc_confirmar(db: Session, sess: WhatsappSession, phone: str, text: str, target: str):
    upper = text.upper().strip()
    if upper in ("NÃO", "NAO", "N", "CANCELAR"):
        _save(db, sess, "menu", {})
        await evolution_api.send_text(target, "❌ Orçamento cancelado.\n\n" + MENU_TEXT)
        return

    if upper != "SIM":
        await evolution_api.send_text(target, "Responda *SIM* para confirmar ou *NÃO* para cancelar.")
        return

    d = _data(sess)

    await evolution_api.send_text(target, "⏳ Gerando seu orçamento em PDF...")

    try:
        # 1. Criar ou reusar cliente
        cliente = db.query(Cliente).filter(Cliente.telefone == d["cliente_telefone"]).first()
        if not cliente:
            cliente = Cliente(
                nome=d["cliente_nome"],
                telefone=d["cliente_telefone"],
                cidade=d["cliente_cidade"],
                origem="whatsapp",
            )
            db.add(cliente)
            db.commit()
            db.refresh(cliente)

        # 2. Criar negócio
        total = sum(i["valor"] for i in d["itens"])
        negocio = Negocio(
            cliente_id=cliente.id,
            tipo="manutencao",
            status="orcamento_enviado",
            valor=total,
            observacoes="Criado via WhatsApp Bot",
        )
        db.add(negocio)
        db.commit()
        db.refresh(negocio)

        # 3. Gerar PDF
        itens = [{"descricao": i["descricao"], "valor": i["valor"]} for i in d["itens"]]
        pdf_bytes = gerar_orcamento_pdf(
            cliente_nome=d["cliente_nome"],
            cliente_cpf_cnpj=None,
            cliente_telefone=d["cliente_telefone"],
            cliente_cidade=d["cliente_cidade"],
            itens=itens,
            valor_total=total,
            condicoes_pagamento=d.get("condicoes_pagamento", ""),
            prazo_entrega_dias=None,
            data_emissao=None,
        )

        # 4. Salvar documento
        doc = Documento(
            negocio_id=negocio.id,
            tipo="orcamento",
            conteudo=f"Orçamento gerado via WhatsApp para {d['cliente_nome']}",
            pdf_bytes=pdf_bytes,
        )
        db.add(doc)
        db.commit()
        db.refresh(doc)

        # 5. Melhoria 4: Enviar PDF via WhatsApp (já implementado)
        await evolution_api.send_media(
            target,
            pdf_bytes,
            f"orcamento_{doc.id}.pdf",
            caption=(
                f"📎 *Orçamento #{doc.id}*\n"
                f"👤 {d['cliente_nome']}\n"
                f"💰 Total: {_fmt_brl(total)}"
            )
        )

        _save(db, sess, "menu", {})
        await evolution_api.send_text(
            target,
            f"✅ *Orçamento #{doc.id} gerado com sucesso!*\n"
            f"O PDF foi enviado acima. ☝️\n\n" + _menu_fallback(phone)
        )

    except Exception:
        log.exception("Erro ao gerar orçamento via WhatsApp")
        await evolution_api.send_text(
            target,
            "❌ Ocorreu um erro ao gerar o orçamento.\n"
            "Por favor, tente novamente ou entre em contato diretamente."
        )
        _save(db, sess, "menu", {})


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# FLUXO: RECIBO
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def _iniciar_recibo(db: Session, sess: WhatsappSession, phone: str, target: str):
    """Inicia o fluxo de recibo, reaproveitando cliente quando o telefone existe."""
    cliente = _find_cliente_by_phone(db, phone)
    if cliente:
        d = {
            "pagador_nome": cliente.nome,
            "cliente_id": cliente.id,
            "cliente_existente": True,
        }
        _save(db, sess, "rec_valor", d)
        await evolution_api.send_text(
            target,
            f"🧾 *Recibo* — Encontrei o cadastro de *{cliente.nome}*.\n\n"
            "Qual o *valor recebido*?\n"
            "_(ex: 350,00 ou R$ 1.200,00)_"
        )
        return

    _save(db, sess, "rec_nome", {})
    await evolution_api.send_text(
        target,
        "🧾 *Recibo* — Vamos começar!\n\nQual o *nome de quem pagou*?"
    )


async def _rec_nome(db: Session, sess: WhatsappSession, phone: str, text: str, target: str):
    d = _data(sess)
    d["pagador_nome"] = text.strip()
    _save(db, sess, "rec_valor", d)
    await evolution_api.send_text(
        target,
        "Qual o *valor recebido*?\n_(ex: 350,00 ou R$ 1.200,00)_"
    )


async def _rec_valor(db: Session, sess: WhatsappSession, phone: str, text: str, target: str):
    valor = _parse_money(text)
    if valor is None:
        await evolution_api.send_text(
            target,
            "⚠️ Valor inválido. Envie apenas o valor recebido.\n"
            "Exemplos: `350,00`, `R$ 1.200,00`, `1200.50`"
        )
        return

    d = _data(sess)
    d["valor"] = valor
    _save(db, sess, "rec_descricao", d)
    await evolution_api.send_text(
        target,
        "Referente a quê?\n"
        "_(ex: REFORMA DE UM PIANO ESSENFELDER, AFINAÇÃO, TRANSPORTE)_"
    )


async def _rec_descricao(db: Session, sess: WhatsappSession, phone: str, text: str, target: str):
    d = _data(sess)
    d["descricao"] = text.strip()
    _save(db, sess, "rec_confirmar", d)

    await evolution_api.send_buttons(
        target,
        f"📄 *Resumo do Recibo:*\n\n"
        f"👤 *Pagador:* {d['pagador_nome']}\n"
        f"💰 *Valor:* {_fmt_brl(d['valor'])}\n"
        f"📝 *Referente a:* {d['descricao']}\n\n"
        "Confirma?",
        buttons=[
            {"label": "SIM", "id": "SIM"},
            {"label": "NÃO", "id": "NÃO"}
        ]
    )


async def _rec_confirmar(db: Session, sess: WhatsappSession, phone: str, text: str, target: str):
    upper = text.upper().strip()
    if upper in ("NÃO", "NAO", "N", "CANCELAR"):
        _save(db, sess, "menu", {})
        await evolution_api.send_text(target, "❌ Recibo cancelado.\n\n" + _menu_fallback(phone))
        return

    if upper != "SIM":
        await evolution_api.send_text(target, "Responda *SIM* para confirmar ou *NÃO* para cancelar.")
        return

    d = _data(sess)
    await evolution_api.send_text(target, "⏳ Gerando seu recibo em PDF...")

    try:
        cliente = None
        cliente_id = d.get("cliente_id")
        if cliente_id:
            cliente = db.query(Cliente).filter(Cliente.id == cliente_id).first()
        if cliente is None:
            cliente = _find_cliente_by_phone(db, phone)
        if cliente is None:
            cliente = Cliente(
                nome=d["pagador_nome"],
                telefone=phone,
                cidade="Nao informado",
                origem="whatsapp",
            )
            db.add(cliente)
            db.commit()
            db.refresh(cliente)

        valor = float(d["valor"])
        negocio = (
            db.query(Negocio)
            .filter(
                Negocio.cliente_id == cliente.id,
                Negocio.status.notin_(["fechado", "perdido"]),
            )
            .order_by(Negocio.created_at.desc())
            .first()
        )
        if negocio is None:
            negocio = Negocio(
                cliente_id=cliente.id,
                tipo="manutencao",
                status="fechado",
                valor=valor,
                observacoes="Recibo criado via WhatsApp Bot",
            )
            db.add(negocio)
        else:
            negocio.status = "fechado"
            negocio.valor = valor
        db.commit()
        db.refresh(negocio)

        pdf_bytes = gerar_recibo_pdf(
            pagador_nome=d["pagador_nome"],
            valor=valor,
            descricao=d["descricao"],
            data_recibo=None,
        )

        doc = Documento(
            negocio_id=negocio.id,
            tipo="recibo",
            conteudo=f"Recibo gerado via WhatsApp para {d['pagador_nome']}",
            pdf_bytes=pdf_bytes,
        )
        db.add(doc)
        db.commit()
        db.refresh(doc)

        await evolution_api.send_media(
            target,
            pdf_bytes,
            f"recibo_{doc.id}.pdf",
            caption=(
                f"🧾 *Recibo #{doc.id}*\n"
                f"👤 {d['pagador_nome']}\n"
                f"💰 Valor: {_fmt_brl(valor)}"
            )
        )

        _save(db, sess, "menu", {})
        await evolution_api.send_text(
            target,
            f"✅ *Recibo #{doc.id} gerado com sucesso!*\n"
            f"O PDF foi enviado acima. ☝️\n\n" + _menu_fallback(phone)
        )

    except Exception:
        log.exception("Erro ao gerar recibo via WhatsApp")
        await evolution_api.send_text(
            target,
            "❌ Ocorreu um erro ao gerar o recibo.\n"
            "Por favor, tente novamente ou entre em contato diretamente."
        )
        _save(db, sess, "menu", {})


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# FLUXO: AGENDAMENTO
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def _ag_titulo(db: Session, sess: WhatsappSession, phone: str, text: str, target: str):
    d = _data(sess)
    d["titulo"] = text
    _save(db, sess, "ag_data", d)
    await evolution_api.send_text(
        target,
        "📆 Qual a *data e hora*?\n\n"
        "Formato: `DD/MM/AAAA HH:MM`\n"
        "Exemplo: `25/03/2026 14:00`\n\n"
        "_Ou envie *hoje*, *amanhã* + hora. Ex: `hoje 14:00`_"
    )


async def _ag_data(db: Session, sess: WhatsappSession, phone: str, text: str, target: str):
    t = text.strip().lower()
    dt = None

    # Melhoria 3: aceitar "hoje HH:MM" e "amanhã HH:MM"
    # Usando fuso horário de Brasília (UTC-3)
    BRT = timezone(timedelta(hours=-3))
    hoje = datetime.now(BRT).date()
    if t.startswith("hoje ") or t.startswith("hoje,"):
        hora_str = t.split(" ", 1)[1].strip()
        try:
            h, m = map(int, hora_str.replace("h", ":").split(":"))
            dt = datetime(hoje.year, hoje.month, hoje.day, h, m)
        except Exception:
            pass
    elif t.startswith("amanhã ") or t.startswith("amanha "):
        hora_str = t.split(" ", 1)[1].strip()
        try:
            h, m = map(int, hora_str.replace("h", ":").split(":"))
            amanha = hoje + timedelta(days=1)
            dt = datetime(amanha.year, amanha.month, amanha.day, h, m)
        except Exception:
            pass
    else:
        try:
            dt = datetime.strptime(text.strip(), "%d/%m/%Y %H:%M")
        except ValueError:
            pass

    if dt is None:
        await evolution_api.send_text(
            target,
            "⚠️ Data inválida. Use um dos formatos:\n\n"
            "  • `25/03/2026 14:00`\n"
            "  • `hoje 14:00`\n"
            "  • `amanhã 09:30`"
        )
        return

    d = _data(sess)
    d["data_hora"] = dt.isoformat()
    _save(db, sess, "ag_tipo", d)
    await evolution_api.send_buttons(
        target,
        "🔧 Qual o *tipo* do serviço?",
        buttons=[
            {"label": "Afinação", "id": "1"},
            {"label": "Manutenção", "id": "2"},
            {"label": "Entrega", "id": "3"},
            {"label": "Outro", "id": "4"},
        ]
    )


async def _ag_tipo(db: Session, sess: WhatsappSession, phone: str, text: str, target: str):
    tipos = {"1": "afinacao", "2": "manutencao", "3": "entrega", "4": "outro"}
    # Melhoria 1: aceitar texto além de número
    t = text.strip().lower()
    tipo = tipos.get(t)
    if not tipo:
        for k, v in {"afinac": "afinacao", "manut": "manutencao", "entrega": "entrega"}.items():
            if k in t:
                tipo = v
                break
    if not tipo:
        await evolution_api.send_text(
            target,
            "⚠️ Opção inválida. Responda com:\n"
            "  *1* — Afinação\n"
            "  *2* — Manutenção\n"
            "  *3* — Entrega\n"
            "  *4* — Outro"
        )
        return

    tipo_labels = {
        "afinacao": "Afinação 🎵",
        "manutencao": "Manutenção 🔧",
        "entrega": "Entrega 🚚",
        "outro": "Outro 📌",
    }

    d = _data(sess)
    d["tipo"] = tipo
    _save(db, sess, "ag_confirmar", d)

    dt = datetime.fromisoformat(d["data_hora"])
    await evolution_api.send_buttons(
        target,
        f"📋 *Resumo do Agendamento:*\n\n"
        f"📌 *Serviço:* {d['titulo']}\n"
        f"📆 *Data/Hora:* {dt.strftime('%d/%m/%Y às %H:%M')}\n"
        f"🔧 *Tipo:* {tipo_labels[tipo]}\n\n"
        "Confirma?",
        buttons=[
            {"label": "SIM", "id": "SIM"},
            {"label": "NÃO", "id": "NÃO"}
        ]
    )


async def _ag_confirmar(db: Session, sess: WhatsappSession, phone: str, text: str, target: str):
    upper = text.upper().strip()
    if upper in ("NÃO", "NAO", "N", "CANCELAR"):
        _save(db, sess, "menu", {})
        await evolution_api.send_text(target, "❌ Agendamento cancelado.\n\n" + _menu_fallback(phone))
        return

    if upper != "SIM":
        await evolution_api.send_text(target, "Responda *SIM* para confirmar ou *NÃO* para cancelar.")
        return

    d = _data(sess)

    try:
        ev = Agenda(
            titulo=d["titulo"],
            data_hora=datetime.fromisoformat(d["data_hora"]),
            tipo=d["tipo"],
            descricao="Agendado via WhatsApp Bot",
        )
        db.add(ev)
        db.commit()
        db.refresh(ev)

        _save(db, sess, "menu", {})
        dt = datetime.fromisoformat(d["data_hora"])
        await evolution_api.send_text(
            target,
            f"✅ *Agendamento #{ev.id} criado com sucesso!*\n"
            f"📆 {dt.strftime('%d/%m/%Y às %H:%M')}\n"
            f"🔧 {d['titulo']}\n\n" + _menu_fallback(phone)
        )
    except Exception:
        log.exception("Erro ao criar agendamento via WhatsApp")
        await evolution_api.send_text(
            target,
            "❌ Erro ao criar agendamento. Tente novamente."
        )
        _save(db, sess, "menu", {})


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# MELHORIA 3: CONSULTA DE AGENDA (hoje / amanhã / semana / DD/MM)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def _handle_agenda_query(db: Session, sess: WhatsappSession, phone: str, target: str):
    """Pergunta qual período o usuário quer ver."""
    _save(db, sess, "agenda_periodo", {})
    await evolution_api.send_buttons(
        target,
        "📅 *Consultar Agenda*\n\n"
        "Qual período deseja visualizar?",
        buttons=[
            {"label": "Hoje", "id": "1"},
            {"label": "Amanhã", "id": "2"},
            {"label": "Próximos 7 dias", "id": "3"},
        ],
        footer="Ou envie uma data específica: 25/03"
    )


async def _agenda_periodo(db: Session, sess: WhatsappSession, phone: str, text: str, target: str):
    from sqlalchemy import Date, cast

    hoje = datetime.now(timezone(timedelta(hours=-3))).date()
    t = text.strip().lower()

    data_inicio = None
    data_fim = None
    label = ""

    if t in ("1", "hoje"):
        data_inicio = data_fim = hoje
        label = f"hoje ({hoje.strftime('%d/%m/%Y')})"
    elif t in ("2", "amanhã", "amanha"):
        amanha = hoje + timedelta(days=1)
        data_inicio = data_fim = amanha
        label = f"amanhã ({amanha.strftime('%d/%m/%Y')})"
    elif t in ("3", "semana", "7 dias", "próximos 7 dias"):
        data_inicio = hoje
        data_fim = hoje + timedelta(days=6)
        label = "próximos 7 dias"
    else:
        # Tentar parsear DD/MM ou DD/MM/AAAA
        for fmt in ("%d/%m", "%d/%m/%Y"):
            try:
                parsed = datetime.strptime(text.strip(), fmt)
                if fmt == "%d/%m":
                    parsed = parsed.replace(year=hoje.year)
                data_inicio = data_fim = parsed.date()
                label = parsed.strftime("%d/%m/%Y")
                break
            except ValueError:
                continue

    if data_inicio is None:
        await evolution_api.send_text(
            target,
            "⚠️ Não entendi. Responda:\n"
            "  *1* — Hoje\n"
            "  *2* — Amanhã\n"
            "  *3* — Próximos 7 dias\n"
            "  ou envie uma data: `25/03`"
        )
        return

    eventos = (
        db.query(Agenda)
        .filter(
            cast(Agenda.data_hora, Date) >= data_inicio,
            cast(Agenda.data_hora, Date) <= data_fim,
            Agenda.concluido.is_(False),
        )
        .order_by(Agenda.data_hora.asc())
        .all()
    )

    _save(db, sess, "menu", {})

    if not eventos:
        await evolution_api.send_text(
            target,
            f"📅 *Agenda — {label}*\n\nNenhum evento pendente! 🎉\n\n" + _menu_fallback(phone)
        )
        return

    tipo_emoji = {
        "afinacao": "🎵", "manutencao": "🔧", "entrega": "🚚",
        "evento": "📍", "followup": "📞", "outro": "📌",
    }
    linhas = []
    data_atual = None
    for ev in eventos:
        ev_date = ev.data_hora.date()
        if ev_date != data_atual:
            if data_atual is not None:
                linhas.append("")
            linhas.append(f"*{ev_date.strftime('%d/%m/%Y')}*")
            data_atual = ev_date
        emoji = tipo_emoji.get(ev.tipo, "📌")
        hora = ev.data_hora.strftime("%H:%M")
        linhas.append(f"  {emoji} {hora} — {ev.titulo}")

    msg = f"📅 *Agenda — {label}:*\n\n" + "\n".join(linhas)
    await evolution_api.send_text(target, msg + "\n\n" + _menu_fallback(phone))


# ─── mapa de estados → handlers ───────────────────────────────────────────────────────

STATE_HANDLERS = {
    # Modo silencioso: sem handler (tratado diretamente em handle_message)
    "sleeping": None,
    # Menu principal
    "menu": _handle_menu,
    # Agenda interna
    "ev_acao_id": _ev_acao_id,
    "ev_acao_tipo": _ev_acao_tipo,
    "ev_remarcar_data": _ev_remarcar_data,
    "ev_cancelar_confirmar": _ev_cancelar_confirmar,
    # Cliente rapido
    "cli_nome": _cli_nome,
    "cli_telefone": _cli_telefone,
    "cli_cidade": _cli_cidade,
    "busca_cliente": _busca_cliente,
    # Servico feito
    "svc_done_id": _svc_done_id,
    "svc_done_recibo": _svc_done_recibo,
    # Lembretes
    "lem_evento_id": _lem_evento_id,
    "lem_phone": _lem_phone,
    # Orçamento
    "orc_nome": _orc_nome,
    "orc_telefone": _orc_telefone,
    "orc_cidade": _orc_cidade,
    "orc_itens": _orc_itens,
    "orc_pagamento": _orc_pagamento,
    "orc_confirmar": _orc_confirmar,
    # Recibo
    "rec_nome": _rec_nome,
    "rec_valor": _rec_valor,
    "rec_descricao": _rec_descricao,
    "rec_confirmar": _rec_confirmar,
    # Agendamento
    "ag_titulo": _ag_titulo,
    "ag_data": _ag_data,
    "ag_tipo": _ag_tipo,
    "ag_confirmar": _ag_confirmar,
    # Agenda por período
    "agenda_periodo": _agenda_periodo,
}
