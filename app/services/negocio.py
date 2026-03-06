from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.cliente import Cliente
from app.models.negocio import Negocio
from app.schemas.negocio import NegocioCreate, NegocioUpdateStatus


def criar_negocio(db: Session, payload: NegocioCreate) -> Negocio:
    cliente = db.query(Cliente).filter(Cliente.id == payload.cliente_id).first()
    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente não encontrado.")
    negocio = Negocio(**payload.model_dump())
    db.add(negocio)
    db.commit()
    db.refresh(negocio)
    return negocio


def listar_negocios(
    db: Session, status: str | None = None, tipo: str | None = None, cliente_id: int | None = None
) -> list[Negocio]:
    q = db.query(Negocio)
    if status:
        q = q.filter(Negocio.status == status)
    if tipo:
        q = q.filter(Negocio.tipo == tipo)
    if cliente_id:
        q = q.filter(Negocio.cliente_id == cliente_id)
    return q.order_by(Negocio.created_at.desc()).all()


def buscar_negocio_por_id(db: Session, negocio_id: int) -> Negocio:
    n = db.query(Negocio).filter(Negocio.id == negocio_id).first()
    if not n:
        raise HTTPException(status_code=404, detail="Negócio não encontrado.")
    return n


def atualizar_status(db: Session, negocio_id: int, payload: NegocioUpdateStatus) -> Negocio:
    n = buscar_negocio_por_id(db, negocio_id)
    n.status = payload.status
    db.commit()
    db.refresh(n)
    return n


def deletar_negocio(db: Session, negocio_id: int):
    n = buscar_negocio_por_id(db, negocio_id)
    db.delete(n)
    db.commit()
