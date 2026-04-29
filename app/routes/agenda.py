from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import schemas
from ..database import get_db
from ..security import require_permission
from ..services import agenda as agenda_service

router = APIRouter(prefix="/agenda", tags=["agenda"], dependencies=[Depends(require_permission("agenda", "read"))])


@router.post("", response_model=schemas.AgendaOut, status_code=201, dependencies=[Depends(require_permission("agenda", "write"))])
def criar_evento(payload: schemas.AgendaCreate, db: Session = Depends(get_db)):
    return agenda_service.criar_evento(db, payload)


@router.get("", response_model=list[schemas.AgendaOut])
def listar_eventos(
    apenas_pendentes: bool = False,
    tipo: str | None = None,
    db: Session = Depends(get_db),
):
    return agenda_service.listar_eventos(db, apenas_pendentes, tipo)


@router.put("/{evento_id}/concluir", response_model=schemas.AgendaOut, dependencies=[Depends(require_permission("agenda", "write"))])
def concluir_evento(evento_id: int, db: Session = Depends(get_db)):
    return agenda_service.concluir_evento(db, evento_id)


@router.delete("/{evento_id}", status_code=204, dependencies=[Depends(require_permission("agenda", "write"))])
def deletar_evento(evento_id: int, db: Session = Depends(get_db)):
    agenda_service.deletar_evento(db, evento_id)
