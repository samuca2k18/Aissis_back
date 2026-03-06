from datetime import datetime, timezone
from typing import cast

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.agenda import Agenda
from app.models.cliente import Cliente
from app.models.lead import Lead
from app.models.negocio import Negocio
from app.schemas.dashboard import DashboardOut


def obter_dashboard(db: Session) -> DashboardOut:
    total_clientes = db.query(func.count(Cliente.id)).scalar() or 0
    total_negocios = db.query(func.count(Negocio.id)).scalar() or 0
    total_leads = db.query(func.count(Lead.id)).scalar() or 0

    receita_row = db.query(func.sum(Negocio.valor)).filter(Negocio.status == "fechado").scalar()
    receita_fechada = float(receita_row) if receita_row else 0.0

    rows_status = db.query(Negocio.status, func.count(Negocio.id)).group_by(Negocio.status).all()
    por_status = dict(cast(list[tuple[str, int]], rows_status))

    rows_origem = db.query(Lead.origem, func.count(Lead.id)).filter(Lead.origem.isnot(None)).group_by(Lead.origem).all()
    leads_por_origem = dict(cast(list[tuple[str, int]], rows_origem))

    agora = datetime.now(timezone.utc)
    proximos_eventos = (
        db.query(func.count(Agenda.id)).filter(Agenda.concluido.is_(False), Agenda.data_hora >= agora).scalar() or 0
    )

    return DashboardOut(
        total_clientes=total_clientes,
        total_negocios=total_negocios,
        total_leads=total_leads,
        receita_fechada=receita_fechada,
        por_status=por_status,
        leads_por_origem=leads_por_origem,
        proximos_eventos=proximos_eventos,
    )
