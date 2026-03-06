from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import schemas
from ..database import get_db
from ..services import lead as lead_service

router = APIRouter(prefix="/leads", tags=["leads"])


@router.post("", response_model=schemas.LeadOut, status_code=201)
def criar_lead(payload: schemas.LeadCreate, db: Session = Depends(get_db)):
    return lead_service.criar_lead(db, payload)


@router.get("", response_model=list[schemas.LeadOut])
def listar_leads(
    status: str | None = None,
    temperatura: str | None = None,
    db: Session = Depends(get_db),
):
    return lead_service.listar_leads(db, status, temperatura)


@router.put("/{lead_id}/status", response_model=schemas.LeadOut)
def atualizar_status(lead_id: int, payload: schemas.LeadUpdateStatus, db: Session = Depends(get_db)):
    return lead_service.atualizar_status(db, lead_id, payload)


@router.put("/{lead_id}/converter", response_model=schemas.ClienteOut)
def converter_lead_em_cliente(
    lead_id: int,
    payload: schemas.ClienteCreate,
    db: Session = Depends(get_db),
):
    return lead_service.converter_lead_em_cliente(db, lead_id, payload)


@router.delete("/{lead_id}", status_code=204)
def deletar_lead(lead_id: int, db: Session = Depends(get_db)):
    lead_service.deletar_lead(db, lead_id)
