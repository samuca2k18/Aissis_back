import base64
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session
from ..database import get_db
from .. import models, schemas
from ..settings import settings
from ..services.pdf_generator import (
    gerar_orcamento_pdf,
    gerar_contrato_locacao_pdf,
    texto_orcamento,
    texto_contrato_locacao,
)

router = APIRouter(prefix="/documentos", tags=["documentos"])


# ─────────────────────────────────────────
#  ORÇAMENTO
# ─────────────────────────────────────────
@router.post("/orcamento", response_model=schemas.DocumentoOut, status_code=201)
def gerar_orcamento(payload: schemas.OrcamentoCreate, db: Session = Depends(get_db)):
    negocio = db.query(models.Negocio).filter(models.Negocio.id == payload.negocio_id).first()
    if not negocio:
        raise HTTPException(404, "Negócio não encontrado.")

    itens = [{"descricao": i.descricao, "valor": i.valor} for i in payload.itens]
    valor_total = sum(i["valor"] for i in itens)

    # Gerar PDF
    pdf_bytes = gerar_orcamento_pdf(
        cliente_nome=payload.cliente_nome,
        cliente_cpf_cnpj=payload.cliente_cpf_cnpj,
        cliente_telefone=payload.cliente_telefone,
        cliente_cidade=payload.cliente_cidade,
        itens=itens,
        valor_total=valor_total,
        condicoes_pagamento=payload.condicoes_pagamento,
        prazo_entrega_dias=payload.prazo_entrega_dias,
        data_emissao=payload.data_emissao,
        observacoes=payload.observacoes,
    )

    # Texto para armazenamento / consulta rápida
    conteudo = texto_orcamento(
        cliente_nome=payload.cliente_nome,
        itens=itens,
        valor_total=valor_total,
        condicoes_pagamento=payload.condicoes_pagamento,
        prazo_entrega_dias=payload.prazo_entrega_dias,
        data_emissao=payload.data_emissao,
    )

    doc = models.Documento(
        negocio_id=negocio.id,
        tipo="orcamento",
        conteudo=conteudo,
        pdf_bytes=pdf_bytes,
    )
    db.add(doc)

    # Atualiza funil e valor automaticamente
    negocio.status = "orcamento_enviado"
    negocio.valor = valor_total

    db.commit()
    db.refresh(doc)
    return doc


@router.get("/orcamento/{doc_id}/pdf")
def download_orcamento_pdf(doc_id: int, db: Session = Depends(get_db)):
    """Retorna o PDF como arquivo para download."""
    doc = db.query(models.Documento).filter(
        models.Documento.id == doc_id,
        models.Documento.tipo == "orcamento",
    ).first()
    if not doc or not doc.pdf_bytes:
        raise HTTPException(404, "PDF não encontrado.")
    return Response(
        content=doc.pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=orcamento_{doc_id}.pdf"},
    )


# ─────────────────────────────────────────
#  CONTRATO DE LOCAÇÃO
# ─────────────────────────────────────────
@router.post("/contrato-locacao", response_model=schemas.DocumentoOut, status_code=201)
def gerar_contrato_locacao(payload: schemas.ContratoLocacaoCreate, db: Session = Depends(get_db)):
    negocio = db.query(models.Negocio).filter(models.Negocio.id == payload.negocio_id).first()
    if not negocio:
        raise HTTPException(404, "Negócio não encontrado.")
    if negocio.tipo != "locacao":
        raise HTTPException(400, "Este endpoint é exclusivo para negócios do tipo 'locacao'.")

    # Gerar PDF
    pdf_bytes = gerar_contrato_locacao_pdf(
        locatario_nome=payload.locatario_nome,
        locatario_endereco=payload.locatario_endereco,
        locatario_cpf_cnpj=payload.locatario_cpf_cnpj,
        descricao_piano=payload.descricao_piano,
        valor_total=payload.valor_total,
        data_entrega_dia=payload.data_entrega_dia,
        data_entrega_mes=payload.data_entrega_mes,
        local_entrega=payload.local_entrega,
        data_segunda_parcela_dia=payload.data_segunda_parcela_dia,
        data_segunda_parcela_mes=payload.data_segunda_parcela_mes,
        data_contrato_dia=payload.data_contrato_dia,
        data_contrato_mes=payload.data_contrato_mes,
    )

    conteudo = texto_contrato_locacao(
        locatario_nome=payload.locatario_nome,
        locatario_endereco=payload.locatario_endereco,
        descricao_piano=payload.descricao_piano,
        valor_total=payload.valor_total,
        data_entrega_dia=payload.data_entrega_dia,
        data_entrega_mes=payload.data_entrega_mes,
        local_entrega=payload.local_entrega,
        data_segunda_parcela_dia=payload.data_segunda_parcela_dia,
        data_segunda_parcela_mes=payload.data_segunda_parcela_mes,
        data_contrato_dia=payload.data_contrato_dia,
        data_contrato_mes=payload.data_contrato_mes,
    )

    doc = models.Documento(
        negocio_id=negocio.id,
        tipo="contrato_locacao",
        conteudo=conteudo,
        pdf_bytes=pdf_bytes,
    )
    db.add(doc)

    # Atualiza valor e status no funil
    negocio.valor = payload.valor_total
    negocio.status = "negociacao"

    db.commit()
    db.refresh(doc)
    return doc


@router.get("/contrato-locacao/{doc_id}/pdf")
def download_contrato_pdf(doc_id: int, db: Session = Depends(get_db)):
    doc = db.query(models.Documento).filter(
        models.Documento.id == doc_id,
        models.Documento.tipo == "contrato_locacao",
    ).first()
    if not doc or not doc.pdf_bytes:
        raise HTTPException(404, "PDF não encontrado.")
    return Response(
        content=doc.pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=contrato_locacao_{doc_id}.pdf"},
    )


# ─────────────────────────────────────────
#  LISTAGENS GERAIS
# ─────────────────────────────────────────
@router.get("", response_model=list[schemas.DocumentoOut])
def listar_documentos(db: Session = Depends(get_db)):
    return db.query(models.Documento).order_by(models.Documento.created_at.desc()).all()


@router.get("/negocio/{negocio_id}", response_model=list[schemas.DocumentoOut])
def listar_por_negocio(negocio_id: int, db: Session = Depends(get_db)):
    return (
        db.query(models.Documento)
        .filter(models.Documento.negocio_id == negocio_id)
        .order_by(models.Documento.created_at.desc())
        .all()
    )
