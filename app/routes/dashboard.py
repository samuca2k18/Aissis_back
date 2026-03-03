from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timezone
from ..database import get_db
from .. import models, schemas

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("", response_model=schemas.DashboardOut)
def dashboard(db: Session = Depends(get_db)):
    total_clientes = db.query(func.count(models.Cliente.id)).scalar() or 0
    total_negocios = db.query(func.count(models.Negocio.id)).scalar() or 0
    total_leads = db.query(func.count(models.Lead.id)).scalar() or 0

    # Receita de negócios fechados
    receita_row = (
        db.query(func.sum(models.Negocio.valor))
        .filter(models.Negocio.status == "fechado")
        .scalar()
    )
    receita_fechada = float(receita_row) if receita_row else 0.0

    # Por status
    rows_status = (
        db.query(models.Negocio.status, func.count(models.Negocio.id))
        .group_by(models.Negocio.status)
        .all()
    )
    por_status = {status: count for status, count in rows_status}

    # Leads por origem
    rows_origem = (
        db.query(models.Lead.origem, func.count(models.Lead.id))
        .filter(models.Lead.origem.isnot(None))
        .group_by(models.Lead.origem)
        .all()
    )
    leads_por_origem = {orig: count for orig, count in rows_origem}

    # Próximos eventos (pendentes)
    agora = datetime.now(timezone.utc)
    proximos_eventos = (
        db.query(func.count(models.Agenda.id))
        .filter(models.Agenda.concluido == False, models.Agenda.data_hora >= agora)  # noqa: E712
        .scalar()
        or 0
    )

    return schemas.DashboardOut(
        total_clientes=total_clientes,
        total_negocios=total_negocios,
        total_leads=total_leads,
        receita_fechada=receita_fechada,
        por_status=por_status,
        leads_por_origem=leads_por_origem,
        proximos_eventos=proximos_eventos,
    )
