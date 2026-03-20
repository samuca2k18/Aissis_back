"""
Máquina de estados do bot do WhatsApp.

Gerencia o fluxo de conversa para:
  1. Gerar orçamento → coleta dados → gera PDF → envia
  2. Agendar afinação/manutenção → coleta dados → cria na agenda
  3. Consultar agenda do dia
"""

import json
import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.whatsapp_session import WhatsappSession
from app.services import evolution_api
from app.services.pdf_generator import gerar_orcamento_pdf
from app.models.agenda import Agenda
from app.models.cliente import Cliente
from app.models.negocio import Negocio
from app.models.documento import Documento

log = logging.getLogger(__name__)

MENU_TEXT = (
    "🎹 *Assis Pianos — Atendimento Automático*\n\n"
    "Olá! Como posso ajudar? Escolha uma opção:\n\n"
    "1️⃣  Solicitar *Orçamento*\n"
    "2️⃣  Agendar *Afinação / Manutenção*\n"
    "3️⃣  Consultar *Agenda do dia*\n"
    "0️⃣  Voltar ao menu\n\n"
    "_Responda com o número da opção._"
)


# ─── helpers ─────────────────────────────────────────────────────────────────

def _get_or_create_session(db: Session, phone: str) -> WhatsappSession:
    sess = db.query(WhatsappSession).filter(WhatsappSession.phone == phone).first()
    if not sess:
        sess = WhatsappSession(phone=phone, state="menu", data_json="{}")
        db.add(sess)
        db.commit()
        db.refresh(sess)
    return sess


def _save(db: Session, sess: WhatsappSession, state: str, data: dict | None = None):
    sess.state = state
    if data is not None:
        sess.data_json = json.dumps(data, ensure_ascii=False)
    db.commit()


def _data(sess: WhatsappSession) -> dict:
    try:
        return json.loads(sess.data_json or "{}")
    except json.JSONDecodeError:
        return {}


# ─── handler principal ──────────────────────────────────────────────────────

async def handle_message(db: Session, phone: str, text: str) -> None:
    """Processa uma mensagem recebida e responde via Evolution API."""
    text = text.strip()
    sess = _get_or_create_session(db, phone)

    # Comando global de reset
    if text == "0":
        _save(db, sess, "menu", {})
        if sess.state != "menu":
            await evolution_api.send_text(phone, MENU_TEXT)
        return

    handler = STATE_HANDLERS.get(sess.state, _handle_menu)
    await handler(db, sess, phone, text)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# MENU
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def _handle_menu(db: Session, sess: WhatsappSession, phone: str, text: str):
    if text == "1":
        _save(db, sess, "orc_nome", {})
        await evolution_api.send_text(phone, "📝 *Orçamento* — Vamos começar!\n\nQual o *nome completo* do cliente?")
    elif text == "2":
        _save(db, sess, "ag_titulo", {})
        await evolution_api.send_text(phone, "📅 *Agendamento* — Vamos agendar!\n\nQual o *título* do serviço? (ex: Afinação Piano Yamaha)")
    elif text == "3":
        await _enviar_agenda_dia(db, phone)
    else:
        await evolution_api.send_text(phone, MENU_TEXT)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# FLUXO: ORÇAMENTO
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def _orc_nome(db: Session, sess: WhatsappSession, phone: str, text: str):
    d = _data(sess)
    d["cliente_nome"] = text
    _save(db, sess, "orc_telefone", d)
    await evolution_api.send_text(phone, "📞 Qual o *telefone* do cliente?")


async def _orc_telefone(db: Session, sess: WhatsappSession, phone: str, text: str):
    d = _data(sess)
    d["cliente_telefone"] = text
    _save(db, sess, "orc_cidade", d)
    await evolution_api.send_text(phone, "🏙️ Qual a *cidade* do cliente?")


async def _orc_cidade(db: Session, sess: WhatsappSession, phone: str, text: str):
    d = _data(sess)
    d["cliente_cidade"] = text
    _save(db, sess, "orc_itens", d)
    await evolution_api.send_text(
        phone,
        "📦 Agora informe os *itens do orçamento*.\n\n"
        "Envie cada item no formato:\n"
        "`descricao ; valor`\n\n"
        "Exemplo:\n"
        "`Afinação completa ; 350`\n"
        "`Regulagem de teclas ; 500`\n\n"
        "Quando terminar, envie *OK*."
    )


async def _orc_itens(db: Session, sess: WhatsappSession, phone: str, text: str):
    d = _data(sess)
    itens = d.get("itens", [])

    if text.upper() == "OK":
        if not itens:
            await evolution_api.send_text(phone, "⚠️ Você não adicionou nenhum item. Envie os itens primeiro.")
            return
        _save(db, sess, "orc_pagamento", d)
        resumo = "\n".join(f"  • {i['descricao']} — R$ {i['valor']:.2f}" for i in itens)
        total = sum(i["valor"] for i in itens)
        await evolution_api.send_text(
            phone,
            f"📋 *Itens adicionados:*\n{resumo}\n\n"
            f"💰 *Total: R$ {total:.2f}*\n\n"
            "Qual a *condição de pagamento*?\n"
            "(ex: _50% na retirada e 50% na entrega_)\n\n"
            "Ou envie *pular* para usar o padrão."
        )
        return

    # parsear item
    parts = text.split(";")
    if len(parts) != 2:
        await evolution_api.send_text(phone, "⚠️ Formato inválido. Use: `descricao ; valor`\nExemplo: `Afinação completa ; 350`")
        return
    try:
        desc = parts[0].strip()
        valor = float(parts[1].strip().replace(",", "."))
    except ValueError:
        await evolution_api.send_text(phone, "⚠️ Valor inválido. Envie um número. Ex: `Afinação ; 350`")
        return

    itens.append({"descricao": desc, "valor": valor})
    d["itens"] = itens
    _save(db, sess, "orc_itens", d)
    await evolution_api.send_text(phone, f"✅ Item adicionado: *{desc}* — R$ {valor:.2f}\n\nEnvie mais itens ou *OK* para continuar.")


async def _orc_pagamento(db: Session, sess: WhatsappSession, phone: str, text: str):
    d = _data(sess)
    if text.lower() != "pular":
        d["condicoes_pagamento"] = text
    else:
        d["condicoes_pagamento"] = "40% na retirada e restante na entrega"
    _save(db, sess, "orc_confirmar", d)

    itens = d["itens"]
    total = sum(i["valor"] for i in itens)
    resumo = "\n".join(f"  • {i['descricao']} — R$ {i['valor']:.2f}" for i in itens)

    await evolution_api.send_text(
        phone,
        f"📄 *Resumo do Orçamento:*\n\n"
        f"👤 *Cliente:* {d['cliente_nome']}\n"
        f"📞 *Telefone:* {d['cliente_telefone']}\n"
        f"🏙️ *Cidade:* {d['cliente_cidade']}\n\n"
        f"📦 *Itens:*\n{resumo}\n\n"
        f"💰 *Total: R$ {total:.2f}*\n"
        f"💳 *Pagamento:* {d['condicoes_pagamento']}\n\n"
        "Confirma? Responda *SIM* ou *NÃO*."
    )


async def _orc_confirmar(db: Session, sess: WhatsappSession, phone: str, text: str):
    if text.upper() == "NÃO" or text.upper() == "NAO":
        _save(db, sess, "menu", {})
        await evolution_api.send_text(phone, "❌ Orçamento cancelado.\n\n" + MENU_TEXT)
        return

    if text.upper() != "SIM":
        await evolution_api.send_text(phone, "Responda *SIM* para confirmar ou *NÃO* para cancelar.")
        return

    d = _data(sess)

    await evolution_api.send_text(phone, "⏳ Gerando seu orçamento em PDF...")

    try:
        # 1. Criar ou encontrar o cliente
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
            tipo="servico",
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

        # 5. Enviar PDF via WhatsApp
        await evolution_api.send_media(
            phone,
            pdf_bytes,
            f"orcamento_{doc.id}.pdf",
            caption=f"📎 Orçamento #{doc.id} — {d['cliente_nome']}"
        )

        _save(db, sess, "menu", {})
        await evolution_api.send_text(phone, "✅ Orçamento gerado e enviado com sucesso!\n\n" + MENU_TEXT)

    except Exception as e:
        log.exception("Erro ao gerar orçamento via WhatsApp")
        await evolution_api.send_text(phone, f"❌ Ocorreu um erro ao gerar o orçamento: {e}\nTente novamente.")
        _save(db, sess, "menu", {})


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# FLUXO: AGENDAMENTO
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def _ag_titulo(db: Session, sess: WhatsappSession, phone: str, text: str):
    d = _data(sess)
    d["titulo"] = text
    _save(db, sess, "ag_data", d)
    await evolution_api.send_text(
        phone,
        "📆 Qual a *data e hora*?\n\n"
        "Formato: `DD/MM/AAAA HH:MM`\n"
        "Exemplo: `25/03/2026 14:00`"
    )


async def _ag_data(db: Session, sess: WhatsappSession, phone: str, text: str):
    try:
        dt = datetime.strptime(text.strip(), "%d/%m/%Y %H:%M")
    except ValueError:
        await evolution_api.send_text(phone, "⚠️ Formato inválido. Use `DD/MM/AAAA HH:MM` (ex: `25/03/2026 14:00`)")
        return

    d = _data(sess)
    d["data_hora"] = dt.isoformat()
    _save(db, sess, "ag_tipo", d)
    await evolution_api.send_text(
        phone,
        "🔧 Qual o *tipo* do serviço?\n\n"
        "1️⃣  Afinação\n"
        "2️⃣  Manutenção\n"
        "3️⃣  Entrega\n"
        "4️⃣  Outro"
    )


async def _ag_tipo(db: Session, sess: WhatsappSession, phone: str, text: str):
    tipos = {"1": "afinacao", "2": "manutencao", "3": "entrega", "4": "outro"}
    tipo = tipos.get(text)
    if not tipo:
        await evolution_api.send_text(phone, "⚠️ Opção inválida. Envie 1, 2, 3 ou 4.")
        return

    tipo_labels = {"afinacao": "Afinação", "manutencao": "Manutenção", "entrega": "Entrega", "outro": "Outro"}

    d = _data(sess)
    d["tipo"] = tipo
    _save(db, sess, "ag_confirmar", d)

    dt = datetime.fromisoformat(d["data_hora"])

    await evolution_api.send_text(
        phone,
        f"📋 *Resumo do Agendamento:*\n\n"
        f"📌 *Título:* {d['titulo']}\n"
        f"📆 *Data/Hora:* {dt.strftime('%d/%m/%Y às %H:%M')}\n"
        f"🔧 *Tipo:* {tipo_labels[tipo]}\n\n"
        "Confirma? Responda *SIM* ou *NÃO*."
    )


async def _ag_confirmar(db: Session, sess: WhatsappSession, phone: str, text: str):
    if text.upper() == "NÃO" or text.upper() == "NAO":
        _save(db, sess, "menu", {})
        await evolution_api.send_text(phone, "❌ Agendamento cancelado.\n\n" + MENU_TEXT)
        return

    if text.upper() != "SIM":
        await evolution_api.send_text(phone, "Responda *SIM* para confirmar ou *NÃO* para cancelar.")
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
            phone,
            f"✅ Agendamento #{ev.id} criado com sucesso!\n"
            f"📆 {dt.strftime('%d/%m/%Y às %H:%M')}\n\n" + MENU_TEXT
        )
    except Exception as e:
        log.exception("Erro ao criar agendamento via WhatsApp")
        await evolution_api.send_text(phone, f"❌ Erro ao agendar: {e}\nTente novamente.")
        _save(db, sess, "menu", {})


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CONSULTA AGENDA DO DIA
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def _enviar_agenda_dia(db: Session, phone: str):
    """Envia a lista de eventos do dia atual."""
    from sqlalchemy import func, cast, Date

    hoje = datetime.now(timezone.utc).date()
    eventos = (
        db.query(Agenda)
        .filter(
            cast(Agenda.data_hora, Date) == hoje,
            Agenda.concluido.is_(False),
        )
        .order_by(Agenda.data_hora.asc())
        .all()
    )

    if not eventos:
        await evolution_api.send_text(phone, "📅 *Agenda do dia*\n\nNenhum evento pendente para hoje! 🎉")
        return

    tipo_emoji = {
        "afinacao": "🎵", "manutencao": "🔧", "entrega": "🚚",
        "evento": "📍", "followup": "📞", "outro": "📌",
    }
    linhas = []
    for ev in eventos:
        emoji = tipo_emoji.get(ev.tipo, "📌")
        hora = ev.data_hora.strftime("%H:%M")
        linhas.append(f"  {emoji} *{hora}* — {ev.titulo}")

    msg = f"📅 *Agenda de hoje ({hoje.strftime('%d/%m/%Y')}):*\n\n" + "\n".join(linhas)
    await evolution_api.send_text(phone, msg)


# ─── mapa de estados → handlers ─────────────────────────────────────────────

STATE_HANDLERS = {
    "menu": _handle_menu,
    # Orçamento
    "orc_nome": _orc_nome,
    "orc_telefone": _orc_telefone,
    "orc_cidade": _orc_cidade,
    "orc_itens": _orc_itens,
    "orc_pagamento": _orc_pagamento,
    "orc_confirmar": _orc_confirmar,
    # Agendamento
    "ag_titulo": _ag_titulo,
    "ag_data": _ag_data,
    "ag_tipo": _ag_tipo,
    "ag_confirmar": _ag_confirmar,
}
