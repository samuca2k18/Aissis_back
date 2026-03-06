from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import schemas
from ..database import get_db
from ..services import cliente as cliente_service

router = APIRouter(prefix="/clientes", tags=["clientes"])


@router.post("", response_model=schemas.ClienteOut, status_code=201)
def criar_cliente(payload: schemas.ClienteCreate, db: Session = Depends(get_db)):
    return cliente_service.criar_cliente(db, payload)


@router.get("", response_model=list[schemas.ClienteOut])
def listar_clientes(db: Session = Depends(get_db)):
    return cliente_service.listar_clientes(db)


@router.get("/{cliente_id}", response_model=schemas.ClienteOut)
def buscar_cliente(cliente_id: int, db: Session = Depends(get_db)):
    return cliente_service.buscar_cliente_por_id(db, cliente_id)


@router.put("/{cliente_id}", response_model=schemas.ClienteOut)
def atualizar_cliente(cliente_id: int, payload: schemas.ClienteUpdate, db: Session = Depends(get_db)):
    return cliente_service.atualizar_cliente(db, cliente_id, payload)


@router.delete("/{cliente_id}", status_code=204)
def deletar_cliente(cliente_id: int, db: Session = Depends(get_db)):
    cliente_service.deletar_cliente(db, cliente_id)
