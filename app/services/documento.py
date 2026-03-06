from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.documento import Documento
from app.models.negocio import Negocio
from app.schemas.documento import ContratoLocacaoCreate, OrcamentoCreate
from app.services.pdf_generator import (
    gerar_contrato_locacao_pdf,
    gerar_orcamento_pdf,
    texto_contrato_locacao,
    texto_orcamento,
)


def gerar_orcamento(db: Session, payload: OrcamentoCreate) -> Documento:
    negocio = db.query(Negocio).filter(Negocio.id == payload.negocio_id).first()
    if not negocio:
        raise HTTPException(status_code=404, detail="Negócio não encontrado.")

    itens = [{"descricao": i.descricao, "valor": i.valor} for i in payload.itens]
    valor_total = sum(i.valor for i in payload.itens)

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

    conteudo = texto_orcamento(
        cliente_nome=payload.cliente_nome,
        itens=itens,
        valor_total=valor_total,
        condicoes_pagamento=payload.condicoes_pagamento,
        prazo_entrega_dias=payload.prazo_entrega_dias,
        data_emissao=payload.data_emissao,
    )

    doc = Documento(
        negocio_id=negocio.id,
        tipo="orcamento",
        conteudo=conteudo,
        pdf_bytes=pdf_bytes,
    )
    db.add(doc)

    negocio.status = "orcamento_enviado"
    negocio.valor = valor_total

    db.commit()
    db.refresh(doc)
    return doc


def obter_pdf_documento(db: Session, doc_id: int, tipo: str) -> bytes:
    doc = (
        db.query(Documento)
        .filter(
            Documento.id == doc_id,
            Documento.tipo == tipo,
        )
        .first()
    )
    if not doc or not doc.pdf_bytes:
        raise HTTPException(status_code=404, detail="PDF não encontrado.")
    return doc.pdf_bytes


def gerar_contrato_locacao(db: Session, payload: ContratoLocacaoCreate) -> Documento:
    negocio = db.query(Negocio).filter(Negocio.id == payload.negocio_id).first()
    if not negocio:
        raise HTTPException(status_code=404, detail="Negócio não encontrado.")
    if negocio.tipo != "locacao":
        raise HTTPException(status_code=400, detail="Este endpoint é exclusivo para negócios do tipo 'locacao'.")

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

    doc = Documento(
        negocio_id=negocio.id,
        tipo="contrato_locacao",
        conteudo=conteudo,
        pdf_bytes=pdf_bytes,
    )
    db.add(doc)

    negocio.valor = payload.valor_total
    negocio.status = "negociacao"

    db.commit()
    db.refresh(doc)
    return doc


def listar_documentos(db: Session) -> list[Documento]:
    return db.query(Documento).order_by(Documento.created_at.desc()).all()


def listar_por_negocio(db: Session, negocio_id: int) -> list[Documento]:
    return db.query(Documento).filter(Documento.negocio_id == negocio_id).order_by(Documento.created_at.desc()).all()
