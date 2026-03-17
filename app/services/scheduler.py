"""
Agendador de tarefas — envia resumo diário da agenda às 7h via WhatsApp.

Usa APScheduler para rodar um job cron.
"""

import logging
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import cast, Date

from app.database import SessionLocal
from app.models.agenda import Agenda
from app.services import evolution_api
from app.settings import settings

log = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


async def _enviar_resumo_diario():
    """Consulta a agenda do dia e envia via WhatsApp para o número do dono."""
    phone = settings.WHATSAPP_NOTIFY_PHONE
    if not phone:
        log.warning("WHATSAPP_NOTIFY_PHONE não configurado — pulando notificação.")
        return

    db = SessionLocal()
    try:
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
            msg = "☀️ *Bom dia!*\n\n📅 Nenhum compromisso para hoje. Bom descanso! 🎉"
        else:
            tipo_emoji = {
                "afinacao": "🎵", "manutencao": "🔧", "entrega": "🚚",
                "evento": "📍", "followup": "📞", "outro": "📌",
            }
            linhas = []
            for ev in eventos:
                emoji = tipo_emoji.get(ev.tipo, "📌")
                hora = ev.data_hora.strftime("%H:%M")
                titulo = ev.titulo
                desc = f"\n    _{ev.descricao}_" if ev.descricao else ""
                linhas.append(f"  {emoji} *{hora}* — {titulo}{desc}")

            msg = (
                f"☀️ *Bom dia! Agenda de hoje ({hoje.strftime('%d/%m/%Y')}):*\n\n"
                + "\n".join(linhas)
                + f"\n\n📊 *Total: {len(eventos)} compromisso(s)*"
            )

        await evolution_api.send_text(phone, msg)
        log.info("Resumo diário enviado para %s (%d eventos)", phone, len(eventos))

    except Exception:
        log.exception("Erro ao enviar resumo diário")
    finally:
        db.close()


def start_scheduler():
    """Registra o job e inicia o scheduler. Chamar no startup da app."""
    # Cron: às 7h, horário de Fortaleza (UTC-3)
    scheduler.add_job(
        _enviar_resumo_diario,
        CronTrigger(hour=7, minute=0, timezone="America/Fortaleza"),
        id="resumo_diario_whatsapp",
        replace_existing=True,
    )
    scheduler.start()
    log.info("Scheduler iniciado — resumo diário às 07:00 (America/Fortaleza)")


def stop_scheduler():
    """Para o scheduler graciosamente."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
