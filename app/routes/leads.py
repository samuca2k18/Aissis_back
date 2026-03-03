from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from .. import models, schemas

router = APIRouter(prefix="/leads", tags=["leads"])


@router.post("", response_model=schemas.LeadOut, status_code=201)
def criar_lead(payload: schemas.LeadCreate, db: Session = Depends(get_db)):
    lead = models.Lead(**payload.model_dump())
    db.add(lead)
    db.commit()
    db.refresh(lead)
    return lead


@router.get("", response_model=list[schemas.LeadOut])
def listar_leads(
    status: str | None = None,
    temperatura: str | None = None,
    db: Session = Depends(get_db),
):
    q = db.query(models.Lead)
    if status:
        q = q.filter(models.Lead.status == status)
    if temperatura:
        q = q.filter(models.Lead.temperatura == temperatura)
    return q.order_by(models.Lead.created_at.desc()).all()


@router.put("/{lead_id}/status", response_model=schemas.LeadOut)
def atualizar_status(lead_id: int, payload: schemas.LeadUpdateStatus, db: Session = Depends(get_db)):
    lead = db.query(models.Lead).filter(models.Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(404, "Lead não encontrado.")
    lead.status = payload.status
    if payload.temperatura:
        lead.temperatura = payload.temperatura
    db.commit()
    db.refresh(lead)
    return lead


@router.put("/{lead_id}/converter", response_model=schemas.ClienteOut)
def converter_lead_em_cliente(
    lead_id: int,
    payload: schemas.ClienteCreate,
    db: Session = Depends(get_db),
):
    """Converte um lead em cliente e atualiza o status do lead."""
    lead = db.query(models.Lead).filter(models.Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(404, "Lead não encontrado.")

    cliente = models.Cliente(**payload.model_dump())
    db.add(cliente)
    db.commit()
    db.refresh(cliente)

    lead.status = "convertido"
    lead.cliente_id = cliente.id
    db.commit()

    return cliente


@router.delete("/{lead_id}", status_code=204)
def deletar_lead(lead_id: int, db: Session = Depends(get_db)):
    lead = db.query(models.Lead).filter(models.Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(404, "Lead não encontrado.")
    db.delete(lead)
    db.commit()
