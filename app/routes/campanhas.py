from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import schemas
from ..database import get_db
from ..services import campanha as campanha_service

router = APIRouter(prefix="/campanhas", tags=["marketing"])


@router.post("", response_model=schemas.CampanhaOut, status_code=201)
def criar_campanha(payload: schemas.CampanhaCreate, db: Session = Depends(get_db)):
    return campanha_service.criar_campanha(db, payload)


@router.get("", response_model=list[schemas.CampanhaOut])
def listar_campanhas(db: Session = Depends(get_db)):
    return campanha_service.listar_campanhas(db)


@router.put("/{campanha_id}", response_model=schemas.CampanhaOut)
def atualizar_campanha(campanha_id: int, payload: schemas.CampanhaUpdate, db: Session = Depends(get_db)):
    return campanha_service.atualizar_campanha(db, campanha_id, payload)


@router.delete("/{campanha_id}", status_code=204)
def deletar_campanha(campanha_id: int, db: Session = Depends(get_db)):
    campanha_service.deletar_campanha(db, campanha_id)
