from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from .. import models, schemas

router = APIRouter(prefix="/clientes", tags=["clientes"])


@router.post("", response_model=schemas.ClienteOut, status_code=201)
def criar_cliente(payload: schemas.ClienteCreate, db: Session = Depends(get_db)):
    cliente = models.Cliente(**payload.model_dump())
    db.add(cliente)
    db.commit()
    db.refresh(cliente)
    return cliente


@router.get("", response_model=list[schemas.ClienteOut])
def listar_clientes(db: Session = Depends(get_db)):
    return db.query(models.Cliente).order_by(models.Cliente.created_at.desc()).all()


@router.get("/{cliente_id}", response_model=schemas.ClienteOut)
def buscar_cliente(cliente_id: int, db: Session = Depends(get_db)):
    c = db.query(models.Cliente).filter(models.Cliente.id == cliente_id).first()
    if not c:
        raise HTTPException(404, "Cliente não encontrado.")
    return c


@router.put("/{cliente_id}", response_model=schemas.ClienteOut)
def atualizar_cliente(cliente_id: int, payload: schemas.ClienteUpdate, db: Session = Depends(get_db)):
    c = db.query(models.Cliente).filter(models.Cliente.id == cliente_id).first()
    if not c:
        raise HTTPException(404, "Cliente não encontrado.")
    for k, v in payload.model_dump(exclude_none=True).items():
        setattr(c, k, v)
    db.commit()
    db.refresh(c)
    return c


@router.delete("/{cliente_id}", status_code=204)
def deletar_cliente(cliente_id: int, db: Session = Depends(get_db)):
    c = db.query(models.Cliente).filter(models.Cliente.id == cliente_id).first()
    if not c:
        raise HTTPException(404, "Cliente não encontrado.")
    db.delete(c)
    db.commit()
