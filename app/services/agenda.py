from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.agenda import Agenda
from app.schemas.agenda import AgendaCreate


def criar_evento(db: Session, payload: AgendaCreate) -> Agenda:
    ev = Agenda(**payload.model_dump())
    db.add(ev)
    db.commit()
    db.refresh(ev)
    return ev


def listar_eventos(db: Session, apenas_pendentes: bool = False, tipo: str | None = None) -> list[Agenda]:
    q = db.query(Agenda)
    if apenas_pendentes:
        q = q.filter(Agenda.concluido.is_(False))
    if tipo:
        q = q.filter(Agenda.tipo == tipo)
    return q.order_by(Agenda.data_hora.asc()).all()


def concluir_evento(db: Session, evento_id: int) -> Agenda:
    ev = db.query(Agenda).filter(Agenda.id == evento_id).first()
    if not ev:
        raise HTTPException(status_code=404, detail="Evento não encontrado.")
    ev.concluido = True
    db.commit()
    db.refresh(ev)
    return ev


def deletar_evento(db: Session, evento_id: int):
    ev = db.query(Agenda).filter(Agenda.id == evento_id).first()
    if not ev:
        raise HTTPException(status_code=404, detail="Evento não encontrado.")
    db.delete(ev)
    db.commit()
