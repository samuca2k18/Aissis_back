from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from ..database import get_db
from .. import models, schemas

router = APIRouter(prefix="/agenda", tags=["agenda"])


@router.post("", response_model=schemas.AgendaOut, status_code=201)
def criar_evento(payload: schemas.AgendaCreate, db: Session = Depends(get_db)):
    ev = models.Agenda(**payload.model_dump())
    db.add(ev)
    db.commit()
    db.refresh(ev)
    return ev


@router.get("", response_model=list[schemas.AgendaOut])
def listar_eventos(
    apenas_pendentes: bool = False,
    tipo: str | None = None,
    db: Session = Depends(get_db),
):
    q = db.query(models.Agenda)
    if apenas_pendentes:
        q = q.filter(models.Agenda.concluido == False)  # noqa: E712
    if tipo:
        q = q.filter(models.Agenda.tipo == tipo)
    return q.order_by(models.Agenda.data_hora.asc()).all()


@router.put("/{evento_id}/concluir", response_model=schemas.AgendaOut)
def concluir_evento(evento_id: int, db: Session = Depends(get_db)):
    ev = db.query(models.Agenda).filter(models.Agenda.id == evento_id).first()
    if not ev:
        raise HTTPException(404, "Evento não encontrado.")
    ev.concluido = True
    db.commit()
    db.refresh(ev)
    return ev


@router.delete("/{evento_id}", status_code=204)
def deletar_evento(evento_id: int, db: Session = Depends(get_db)):
    ev = db.query(models.Agenda).filter(models.Agenda.id == evento_id).first()
    if not ev:
        raise HTTPException(404, "Evento não encontrado.")
    db.delete(ev)
    db.commit()
