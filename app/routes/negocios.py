from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from .. import models, schemas

router = APIRouter(prefix="/negocios", tags=["negócios"])


@router.post("", response_model=schemas.NegocioOut, status_code=201)
def criar_negocio(payload: schemas.NegocioCreate, db: Session = Depends(get_db)):
    cliente = db.query(models.Cliente).filter(models.Cliente.id == payload.cliente_id).first()
    if not cliente:
        raise HTTPException(404, "Cliente não encontrado.")
    negocio = models.Negocio(**payload.model_dump())
    db.add(negocio)
    db.commit()
    db.refresh(negocio)
    return negocio


@router.get("", response_model=list[schemas.NegocioOut])
def listar_negocios(
    status: str | None = None,
    tipo: str | None = None,
    cliente_id: int | None = None,
    db: Session = Depends(get_db),
):
    q = db.query(models.Negocio)
    if status:
        q = q.filter(models.Negocio.status == status)
    if tipo:
        q = q.filter(models.Negocio.tipo == tipo)
    if cliente_id:
        q = q.filter(models.Negocio.cliente_id == cliente_id)
    return q.order_by(models.Negocio.created_at.desc()).all()


@router.get("/{negocio_id}", response_model=schemas.NegocioOut)
def buscar_negocio(negocio_id: int, db: Session = Depends(get_db)):
    n = db.query(models.Negocio).filter(models.Negocio.id == negocio_id).first()
    if not n:
        raise HTTPException(404, "Negócio não encontrado.")
    return n


@router.put("/{negocio_id}/status", response_model=schemas.NegocioOut)
def atualizar_status(negocio_id: int, payload: schemas.NegocioUpdateStatus, db: Session = Depends(get_db)):
    n = db.query(models.Negocio).filter(models.Negocio.id == negocio_id).first()
    if not n:
        raise HTTPException(404, "Negócio não encontrado.")
    n.status = payload.status
    db.commit()
    db.refresh(n)
    return n


@router.delete("/{negocio_id}", status_code=204)
def deletar_negocio(negocio_id: int, db: Session = Depends(get_db)):
    n = db.query(models.Negocio).filter(models.Negocio.id == negocio_id).first()
    if not n:
        raise HTTPException(404, "Negócio não encontrado.")
    db.delete(n)
    db.commit()
