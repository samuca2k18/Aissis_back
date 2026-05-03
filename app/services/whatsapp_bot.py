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

from sqlalchemy.orm import Session

from app.models.agenda import Agenda
from app.models.cliente import Cliente
from app.models.documento import Documento
from app.models.negocio import Negocio
from app.models.whatsapp_session import WhatsappSession
from app.services import evolution_api
from app.services.pdf_generator import gerar_orcamento_pdf

log = logging.getLogger(__name__)

# ─── Timeout de sessão: 30 minutos sem interação → adormecer silenciosamente ─
SESSION_TIMEOUT_MINUTES = 30

MENU_TEXT = (
    "🎹 *Assis Pianos — Atendimento Automático*\n\n"
    "Olá! Como posso ajudar? Escolha uma opção abaixo:\n"
    "Digite *0* para sair e deixar o bot dormindo."
)

MENU_BUTTONS = [
    {"label": "Solicitar Orçamento", "id": "1"},
    {"label": "Agendar Serviço", "id": "2"},
    {"label": "Consultar Agenda", "id": "3"},
]

MENU_TEXT_FALLBACK = (
    f"{MENU_TEXT}\n\n"
    + "\n".join(f"{b['id']}️⃣  {b['label']}" for b in MENU_BUTTONS)
)

# ─── palavras-chave para atalho (SOMENTE dentro do fluxo ativo) ─────────────
_KW_ORCAMENTO  = {"orçamento", "orcamento", "orcar", "orçar", "preço", "preco", "valor", "quanto"}
_KW_AGENDAR    = {"agendar", "agendamento", "marcar"}
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
            await evolution_api.send_buttons(target, MENU_TEXT, MENU_BUTTONS)
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
        await evolution_api.send_buttons(target, MENU_TEXT, MENU_BUTTONS)
        return
    await handler(db, sess, phone, text, target)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# MENU
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def _handle_menu(db: Session, sess: WhatsappSession, phone: str, text: str, target: str):
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
    else:
        # Aviso curto em vez de repetir todos os botões e texto toda vez
        await evolution_api.send_text(
            target,
            "⚠️ Opção não reconhecida.\nPor favor, **digite 1, 2, 3 ou 0** (ou escolha no botão acima)."
        )


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
            f"O PDF foi enviado acima. ☝️\n\n" + MENU_TEXT_FALLBACK
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
        await evolution_api.send_text(target, "❌ Agendamento cancelado.\n\n" + MENU_TEXT_FALLBACK)
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
            f"🔧 {d['titulo']}\n\n" + MENU_TEXT_FALLBACK
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
            f"📅 *Agenda — {label}*\n\nNenhum evento pendente! 🎉\n\n" + MENU_TEXT_FALLBACK
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
    await evolution_api.send_text(target, msg + "\n\n" + MENU_TEXT_FALLBACK)


# ─── mapa de estados → handlers ───────────────────────────────────────────────────────

STATE_HANDLERS = {
    # Modo silencioso: sem handler (tratado diretamente em handle_message)
    "sleeping": None,
    # Menu principal
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
    # Agenda por período
    "agenda_periodo": _agenda_periodo,
}
