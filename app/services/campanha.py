from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.campanha import Campanha
from app.schemas.campanha import CampanhaCreate, CampanhaOut, CampanhaUpdate


def _enriquecer(c: Campanha) -> CampanhaOut:
    custo_por_lead = float(c.investimento) / c.leads_gerados if c.leads_gerados and c.investimento else None
    roi = ((float(c.receita) - float(c.investimento)) / float(c.investimento)) * 100 if c.investimento else None
    out = CampanhaOut.model_validate(c)
    out.custo_por_lead = round(custo_por_lead, 2) if custo_por_lead else None
    out.roi_percentual = round(roi, 2) if roi is not None else None
    return out


def criar_campanha(db: Session, payload: CampanhaCreate) -> CampanhaOut:
    c = Campanha(**payload.model_dump())
    db.add(c)
    db.commit()
    db.refresh(c)
    return _enriquecer(c)


def listar_campanhas(db: Session) -> list[CampanhaOut]:
    campanhas = db.query(Campanha).order_by(Campanha.created_at.desc()).all()
    return [_enriquecer(c) for c in campanhas]


def atualizar_campanha(db: Session, campanha_id: int, payload: CampanhaUpdate) -> CampanhaOut:
    c = db.query(Campanha).filter(Campanha.id == campanha_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Campanha não encontrada.")
    for k, v in payload.model_dump(exclude_none=True).items():
        setattr(c, k, v)
    db.commit()
    db.refresh(c)
    return _enriquecer(c)


def deletar_campanha(db: Session, campanha_id: int):
    c = db.query(Campanha).filter(Campanha.id == campanha_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Campanha não encontrada.")
    db.delete(c)
    db.commit()
