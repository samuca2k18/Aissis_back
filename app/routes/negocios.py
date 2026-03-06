from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import schemas
from ..database import get_db
from ..services import negocio as negocio_service

router = APIRouter(prefix="/negocios", tags=["negócios"])


@router.post("", response_model=schemas.NegocioOut, status_code=201)
def criar_negocio(payload: schemas.NegocioCreate, db: Session = Depends(get_db)):
    return negocio_service.criar_negocio(db, payload)


@router.get("", response_model=list[schemas.NegocioOut])
def listar_negocios(
    status: str | None = None,
    tipo: str | None = None,
    cliente_id: int | None = None,
    db: Session = Depends(get_db),
):
    return negocio_service.listar_negocios(db, status, tipo, cliente_id)


@router.get("/{negocio_id}", response_model=schemas.NegocioOut)
def buscar_negocio(negocio_id: int, db: Session = Depends(get_db)):
    return negocio_service.buscar_negocio_por_id(db, negocio_id)


@router.put("/{negocio_id}/status", response_model=schemas.NegocioOut)
def atualizar_status(negocio_id: int, payload: schemas.NegocioUpdateStatus, db: Session = Depends(get_db)):
    return negocio_service.atualizar_status(db, negocio_id, payload)


@router.delete("/{negocio_id}", status_code=204)
def deletar_negocio(negocio_id: int, db: Session = Depends(get_db)):
    negocio_service.deletar_negocio(db, negocio_id)
