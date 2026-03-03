from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from .. import models, schemas

router = APIRouter(prefix="/campanhas", tags=["marketing"])


@router.post("", response_model=schemas.CampanhaOut, status_code=201)
def criar_campanha(payload: schemas.CampanhaCreate, db: Session = Depends(get_db)):
    c = models.Campanha(**payload.model_dump())
    db.add(c)
    db.commit()
    db.refresh(c)
    return _enriquecer(c)


@router.get("", response_model=list[schemas.CampanhaOut])
def listar_campanhas(db: Session = Depends(get_db)):
    campanhas = db.query(models.Campanha).order_by(models.Campanha.created_at.desc()).all()
    return [_enriquecer(c) for c in campanhas]


@router.put("/{campanha_id}", response_model=schemas.CampanhaOut)
def atualizar_campanha(campanha_id: int, payload: schemas.CampanhaUpdate, db: Session = Depends(get_db)):
    c = db.query(models.Campanha).filter(models.Campanha.id == campanha_id).first()
    if not c:
        raise HTTPException(404, "Campanha não encontrada.")
    for k, v in payload.model_dump(exclude_none=True).items():
        setattr(c, k, v)
    db.commit()
    db.refresh(c)
    return _enriquecer(c)


@router.delete("/{campanha_id}", status_code=204)
def deletar_campanha(campanha_id: int, db: Session = Depends(get_db)):
    c = db.query(models.Campanha).filter(models.Campanha.id == campanha_id).first()
    if not c:
        raise HTTPException(404, "Campanha não encontrada.")
    db.delete(c)
    db.commit()


def _enriquecer(c: models.Campanha) -> schemas.CampanhaOut:
    """Calcula métricas derivadas."""
    custo_por_lead = (
        float(c.investimento) / c.leads_gerados if c.leads_gerados and c.investimento else None
    )
    roi = (
        ((float(c.receita) - float(c.investimento)) / float(c.investimento)) * 100
        if c.investimento
        else None
    )
    out = schemas.CampanhaOut.model_validate(c)
    out.custo_por_lead = round(custo_por_lead, 2) if custo_por_lead else None
    out.roi_percentual = round(roi, 2) if roi is not None else None
    return out
