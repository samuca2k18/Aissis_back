from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.cliente import Cliente
from app.models.lead import Lead
from app.schemas.cliente import ClienteCreate
from app.schemas.lead import LeadCreate, LeadUpdateStatus


def criar_lead(db: Session, payload: LeadCreate) -> Lead:
    lead = Lead(**payload.model_dump())
    db.add(lead)
    db.commit()
    db.refresh(lead)
    return lead


def listar_leads(db: Session, status: str | None = None, temperatura: str | None = None) -> list[Lead]:
    q = db.query(Lead)
    if status:
        q = q.filter(Lead.status == status)
    if temperatura:
        q = q.filter(Lead.temperatura == temperatura)
    return q.order_by(Lead.created_at.desc()).all()


def buscar_lead_por_id(db: Session, lead_id: int) -> Lead:
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead não encontrado.")
    return lead


def atualizar_status(db: Session, lead_id: int, payload: LeadUpdateStatus) -> Lead:
    lead = buscar_lead_por_id(db, lead_id)
    lead.status = payload.status
    if payload.temperatura:
        lead.temperatura = payload.temperatura
    db.commit()
    db.refresh(lead)
    return lead


def converter_lead_em_cliente(db: Session, lead_id: int, payload: ClienteCreate) -> Cliente:
    lead = buscar_lead_por_id(db, lead_id)
    cliente = Cliente(**payload.model_dump())
    db.add(cliente)
    db.commit()
    db.refresh(cliente)

    lead.status = "convertido"
    lead.cliente_id = cliente.id
    db.commit()
    return cliente


def deletar_lead(db: Session, lead_id: int):
    lead = buscar_lead_por_id(db, lead_id)
    db.delete(lead)
    db.commit()
