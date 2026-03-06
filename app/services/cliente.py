from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.cliente import Cliente
from app.schemas.cliente import ClienteCreate, ClienteUpdate


def criar_cliente(db: Session, payload: ClienteCreate) -> Cliente:
    cliente = Cliente(**payload.model_dump())
    db.add(cliente)
    db.commit()
    db.refresh(cliente)
    return cliente


def listar_clientes(db: Session) -> list[Cliente]:
    return db.query(Cliente).order_by(Cliente.created_at.desc()).all()


def buscar_cliente_por_id(db: Session, cliente_id: int) -> Cliente:
    c = db.query(Cliente).filter(Cliente.id == cliente_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Cliente não encontrado.")
    return c


def atualizar_cliente(db: Session, cliente_id: int, payload: ClienteUpdate) -> Cliente:
    c = buscar_cliente_por_id(db, cliente_id)
    for k, v in payload.model_dump(exclude_none=True).items():
        setattr(c, k, v)
    db.commit()
    db.refresh(c)
    return c


def deletar_cliente(db: Session, cliente_id: int):
    c = buscar_cliente_por_id(db, cliente_id)
    db.delete(c)
    db.commit()
