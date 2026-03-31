from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy.orm import Session

from .. import schemas
from ..database import get_db
from ..security import require_api_key
from ..services import documento as documento_service

router = APIRouter(prefix="/documentos", tags=["documentos"], dependencies=[Depends(require_api_key)])


# ── Orçamento ────────────────────────────────────────────────────────────────

@router.post("/orcamento", response_model=schemas.DocumentoOut, status_code=201)
def gerar_orcamento(payload: schemas.OrcamentoCreate, db: Session = Depends(get_db)):
    return documento_service.gerar_orcamento(db, payload)


@router.get("/orcamento/{doc_id}/pdf")
def download_orcamento_pdf(doc_id: int, db: Session = Depends(get_db)):
    pdf_bytes = documento_service.obter_pdf_documento(db, doc_id, "orcamento")
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=orcamento_{doc_id}.pdf"},
    )


# ── Recibo ────────────────────────────────────────────────────────────────────

@router.post("/recibo", response_model=schemas.DocumentoOut, status_code=201)
def gerar_recibo(payload: schemas.ReciboCreate, db: Session = Depends(get_db)):
    return documento_service.gerar_recibo(db, payload)


@router.get("/recibo/{doc_id}/pdf")
def download_recibo_pdf(doc_id: int, db: Session = Depends(get_db)):
    pdf_bytes = documento_service.obter_pdf_documento(db, doc_id, "recibo")
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=recibo_{doc_id}.pdf"},
    )


# ── Contrato de Locação ───────────────────────────────────────────────────────

@router.post("/contrato-locacao", response_model=schemas.DocumentoOut, status_code=201)
def gerar_contrato_locacao(payload: schemas.ContratoLocacaoCreate, db: Session = Depends(get_db)):
    return documento_service.gerar_contrato_locacao(db, payload)


@router.get("/contrato-locacao/{doc_id}/pdf")
def download_contrato_pdf(doc_id: int, db: Session = Depends(get_db)):
    pdf_bytes = documento_service.obter_pdf_documento(db, doc_id, "contrato_locacao")
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=contrato_locacao_{doc_id}.pdf"},
    )


# ── Listagens ─────────────────────────────────────────────────────────────────

@router.get("", response_model=list[schemas.DocumentoOut])
def listar_documentos(db: Session = Depends(get_db)):
    return documento_service.listar_documentos(db)


@router.get("/negocio/{negocio_id}", response_model=list[schemas.DocumentoOut])
def listar_por_negocio(negocio_id: int, db: Session = Depends(get_db)):
    return documento_service.listar_por_negocio(db, negocio_id)
