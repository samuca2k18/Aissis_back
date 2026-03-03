"""
Gerador de PDF com os templates oficiais da Assis Pianos.
Baseado nos documentos reais: Orçamento e Contrato de Locação.
"""
import io
from datetime import datetime, timezone
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, KeepTogether
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from ..settings import settings


# ─────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────
def fmt_brl(value: float) -> str:
    s = f"{value:,.2f}"
    return "R$ " + s.replace(",", "X").replace(".", ",").replace("X", ".")


def _base_doc(buffer: io.BytesIO) -> SimpleDocTemplate:
    return SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=20 * mm,
        leftMargin=20 * mm,
        topMargin=15 * mm,
        bottomMargin=20 * mm,
    )


def _styles():
    base = getSampleStyleSheet()
    normal = base["Normal"]

    title = ParagraphStyle(
        "titulo",
        parent=normal,
        fontSize=16,
        fontName="Helvetica-Bold",
        alignment=TA_CENTER,
        spaceAfter=6,
        underline=True,
    )
    header_company = ParagraphStyle(
        "header_company",
        parent=normal,
        fontSize=9,
        fontName="Helvetica-Bold",
        alignment=TA_CENTER,
        spaceAfter=2,
    )
    header_info = ParagraphStyle(
        "header_info",
        parent=normal,
        fontSize=8,
        fontName="Helvetica",
        alignment=TA_CENTER,
        spaceAfter=2,
    )
    section_title = ParagraphStyle(
        "section_title",
        parent=normal,
        fontSize=13,
        fontName="Helvetica-Bold",
        alignment=TA_CENTER,
        spaceAfter=4,
        underline=True,
    )
    client_label = ParagraphStyle(
        "client_label",
        parent=normal,
        fontSize=12,
        fontName="Helvetica-Bold",
        spaceAfter=2,
    )
    body = ParagraphStyle(
        "body",
        parent=normal,
        fontSize=10,
        fontName="Helvetica",
        spaceAfter=4,
        leading=14,
    )
    body_bold = ParagraphStyle(
        "body_bold",
        parent=normal,
        fontSize=10,
        fontName="Helvetica-Bold",
        spaceAfter=4,
    )
    small = ParagraphStyle(
        "small",
        parent=normal,
        fontSize=9,
        fontName="Helvetica",
        alignment=TA_CENTER,
    )
    clause = ParagraphStyle(
        "clause",
        parent=normal,
        fontSize=10,
        fontName="Helvetica",
        spaceAfter=10,
        leading=15,
    )

    return {
        "title": title,
        "header_company": header_company,
        "header_info": header_info,
        "section_title": section_title,
        "client_label": client_label,
        "body": body,
        "body_bold": body_bold,
        "small": small,
        "clause": clause,
    }


def _company_header(s: dict) -> list:
    """Cabeçalho padrão da Assis Pianos."""
    elems = []
    elems.append(Paragraph(f"<b><u>{settings.COMPANY_NAME}</u></b>", s["header_company"]))
    elems.append(Paragraph(f"C.N.P.J: {settings.COMPANY_CNPJ}", s["header_info"]))
    elems.append(Paragraph(settings.COMPANY_ADDRESS, s["header_info"]))
    elems.append(Paragraph(f"Fone: {settings.COMPANY_PHONE}", s["header_info"]))
    elems.append(Paragraph(f"e-mail: {settings.COMPANY_EMAIL}", s["header_info"]))
    elems.append(Spacer(1, 8 * mm))
    return elems


# ─────────────────────────────────────────
#  ORÇAMENTO
# ─────────────────────────────────────────
def gerar_orcamento_pdf(
    cliente_nome: str,
    cliente_cpf_cnpj: str | None,
    cliente_telefone: str,
    cliente_cidade: str,
    itens: list[dict],       # [{"descricao": str, "valor": float}]
    valor_total: float,
    condicoes_pagamento: str,
    prazo_entrega_dias: int | None,
    data_emissao: datetime | None = None,
    observacoes: str | None = None,
) -> bytes:
    if data_emissao is None:
        data_emissao = datetime.now(timezone.utc)
    data_str = data_emissao.strftime("%d de %B de %Y")

    buffer = io.BytesIO()
    doc = _base_doc(buffer)
    s = _styles()
    story = []

    # Cabeçalho empresa
    story += _company_header(s)

    # Título
    story.append(Paragraph("<u>O R Ç A M E N T O</u>", s["section_title"]))
    story.append(Spacer(1, 6 * mm))

    # Nome do cliente em destaque
    story.append(Paragraph(f"<b>SR. {cliente_nome.upper()}</b>", s["client_label"]))
    story.append(Spacer(1, 4 * mm))

    # Tabela de serviços
    table_data = [["SERVIÇO", "VALOR"]]
    for item in itens:
        table_data.append([item["descricao"], fmt_brl(item["valor"])])
    table_data.append(["TOTAL", fmt_brl(valor_total)])

    col_widths = [120 * mm, 40 * mm]
    table = Table(table_data, colWidths=col_widths, repeatRows=1)
    table.setStyle(TableStyle([
        # Cabeçalho da tabela
        ("BACKGROUND", (0, 0), (-1, 0), colors.white),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 10),
        ("BOX", (0, 0), (-1, 0), 0.5, colors.black),
        # Linhas dos itens
        ("FONTNAME", (0, 1), (-1, -2), "Helvetica"),
        ("FONTSIZE", (0, 1), (-1, -2), 10),
        ("BOX", (0, 1), (-1, -2), 0.3, colors.black),
        ("GRID", (0, 1), (-1, -2), 0.3, colors.black),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        # Linha TOTAL
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, -1), (-1, -1), 10),
        ("BOX", (0, -1), (-1, -1), 0.5, colors.black),
    ]))
    story.append(table)
    story.append(Spacer(1, 5 * mm))

    # Prazo e pagamento
    if prazo_entrega_dias:
        story.append(Paragraph(f"PRAZO DE ENTREGA {prazo_entrega_dias} DIAS.", s["body_bold"]))
    story.append(Spacer(1, 2 * mm))
    story.append(Paragraph(f"Forma de pagamento: {condicoes_pagamento}.", s["body"]))

    if observacoes:
        story.append(Spacer(1, 3 * mm))
        story.append(Paragraph(f"Observações: {observacoes}", s["body"]))

    # Assinatura
    story.append(Spacer(1, 18 * mm))
    story.append(HRFlowable(width="80%", thickness=0.5, color=colors.black, hAlign="CENTER"))
    story.append(Paragraph(settings.COMPANY_RESPONSAVEL, s["small"]))
    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph(f"Fortaleza, {data_str}", s["small"]))

    doc.build(story)
    return buffer.getvalue()


# ─────────────────────────────────────────
#  CONTRATO DE LOCAÇÃO
# ─────────────────────────────────────────
def gerar_contrato_locacao_pdf(
    locatario_nome: str,
    locatario_endereco: str,
    locatario_cpf_cnpj: str | None,
    descricao_piano: str,
    valor_total: float,
    data_entrega_dia: str,
    data_entrega_mes: str,
    local_entrega: str,
    data_segunda_parcela_dia: str,
    data_segunda_parcela_mes: str,
    data_contrato_dia: str,
    data_contrato_mes: str,
) -> bytes:
    valor_extenso = _valor_por_extenso_simples(valor_total)

    buffer = io.BytesIO()
    doc = _base_doc(buffer)
    s = _styles()
    story = []

    # Cabeçalho empresa
    story += _company_header(s)

    # Título
    story.append(Paragraph("<b><u>CONTRATO DE LOCAÇÃO</u></b>", s["section_title"]))
    story.append(Spacer(1, 8 * mm))

    # Preâmbulo
    preambulo = (
        f"&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Os abaixo assinados, de um lado <b>JR. NASCIMENTO V.C.I.M. LTDA</b>, "
        f"<b>CNPJ {settings.COMPANY_CNPJ_CONTRATO}</b> e CPF {settings.COMPANY_CPF_SOCIO} "
        f"estabelecida nesta cidade de <b>FORTALEZA</b>, na <b>{settings.COMPANY_ADDRESS}</b> "
        f"e de outro lado <b>{locatario_nome}</b>"
        + (f", CPF/CNPJ: {locatario_cpf_cnpj}" if locatario_cpf_cnpj else "")
        + f", estabelecido na <b>{locatario_endereco}</b>, têm justo e contratado, na melhor forma de direito "
        f"o seguinte, que mutuamente outorgam e aceitam, a saber:"
    )
    story.append(Paragraph(preambulo, s["clause"]))
    story.append(Spacer(1, 4 * mm))

    # Cláusulas
    clausulas = [
        (
            "CLÁUSULA 1ª",
            f'O primeiro nomeado aqui chamado "LOCADOR", aluga ao segundo nomeado, aqui chamado '
            f'"LOCATÁRIO", pelo preço certo ajustado o total de <b>{fmt_brl(valor_total)}</b> '
            f'(<b>{valor_extenso}</b>) um <b>{descricao_piano}</b>.'
        ),
        (
            "CLÁUSULA 2ª",
            f"O LOCADOR compromete-se a entregar o piano na data de <b>{data_entrega_dia}</b> de "
            f"<b>{data_entrega_mes}</b> de 2026 no <b>{local_entrega}</b>."
        ),
        (
            "CLÁUSULA 3ª",
            f"O LOCATÁRIO compromete-se a pagar o bem descrito na cláusula 1ª no ato desse contrato "
            f"<b>50 por cento</b> para reserva do Piano e <b>50 por cento</b> no dia "
            f"<b>{data_segunda_parcela_dia}</b> de <b>{data_segunda_parcela_mes}</b> de 2026."
        ),
        (
            "CLÁUSULA 4ª",
            "O LOCATÁRIO deverá manter o piano em perfeitas e em igual condições de uso até a devolução do mesmo."
        ),
        (
            "CLÁUSULA 5ª",
            "Havendo algum dano ao bem descrito em posse ainda do LOCATÁRIO este se responsabilizará "
            "pelo ressarcimento dos eventuais danos."
        ),
    ]

    for num, texto in clausulas:
        story.append(Paragraph(f"<b>{num}</b> – {texto}", s["clause"]))

    story.append(Spacer(1, 6 * mm))
    story.append(Paragraph(
        f"Fortaleza, {data_contrato_dia} de {data_contrato_mes} de 2026.",
        s["body"]
    ))

    # Assinaturas
    story.append(Spacer(1, 16 * mm))

    assinatura_data = [
        [
            Paragraph(settings.COMPANY_RESPONSAVEL, s["small"]),
            Paragraph(locatario_nome, s["small"]),
        ],
        [
            Paragraph("<b>LOCADOR</b>", s["small"]),
            Paragraph("<b>LOCATÁRIO</b>", s["small"]),
        ]
    ]
    sig_table = Table(assinatura_data, colWidths=[80 * mm, 80 * mm])
    sig_table.setStyle(TableStyle([
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("LINEABOVE", (0, 0), (-1, 0), 0.5, colors.black),
    ]))
    story.append(sig_table)

    doc.build(story)
    return buffer.getvalue()


# ─────────────────────────────────────────
#  HELPER – valor por extenso (simplificado)
# ─────────────────────────────────────────
def _valor_por_extenso_simples(valor: float) -> str:
    """Converte valores comuns em extenso (BRL). Cobre 0–999.999."""
    unidades = ["", "um", "dois", "três", "quatro", "cinco", "seis", "sete", "oito", "nove",
                "dez", "onze", "doze", "treze", "quatorze", "quinze", "dezesseis", "dezessete",
                "dezoito", "dezenove"]
    dezenas = ["", "", "vinte", "trinta", "quarenta", "cinquenta", "sessenta", "setenta",
               "oitenta", "noventa"]
    centenas = ["", "cem", "duzentos", "trezentos", "quatrocentos", "quinhentos",
                "seiscentos", "setecentos", "oitocentos", "novecentos"]

    def _partes(n: int) -> str:
        if n == 0:
            return "zero"
        if n == 100:
            return "cem"
        parts = []
        c = n // 100
        resto = n % 100
        if c:
            # ajusta "cem" apenas quando exato
            parts.append(centenas[c] if resto else ("cem" if c == 1 else centenas[c]))
        if resto < 20:
            if resto:
                parts.append(unidades[resto])
        else:
            d = resto // 10
            u = resto % 10
            parts.append(dezenas[d] + (" e " + unidades[u] if u else ""))
        return " e ".join(parts)

    inteiro = int(valor)
    centavos = round((valor - inteiro) * 100)

    reais = _partes(inteiro)
    sufixo_reais = "reais" if inteiro != 1 else "real"

    if centavos:
        cent_str = _partes(centavos)
        sufixo_cent = "centavos" if centavos != 1 else "centavo"
        return f"{reais} {sufixo_reais} e {cent_str} {sufixo_cent}"
    return f"{reais} {sufixo_reais}"


# ─────────────────────────────────────────
#  TEXTO PLANO (fallback / armazenamento)
# ─────────────────────────────────────────
def texto_orcamento(
    cliente_nome: str,
    itens: list[dict],
    valor_total: float,
    condicoes_pagamento: str,
    prazo_entrega_dias: int | None,
    data_emissao: datetime | None = None,
) -> str:
    if data_emissao is None:
        data_emissao = datetime.now(timezone.utc)
    linhas = [
        settings.COMPANY_NAME,
        f"CNPJ: {settings.COMPANY_CNPJ}",
        settings.COMPANY_ADDRESS,
        f"Fone: {settings.COMPANY_PHONE}",
        f"E-mail: {settings.COMPANY_EMAIL}",
        "",
        "ORÇAMENTO",
        f"Cliente: {cliente_nome}",
        "",
        "SERVIÇO | VALOR",
    ]
    for item in itens:
        linhas.append(f"- {item['descricao']}: {fmt_brl(item['valor'])}")
    linhas += [
        "",
        f"TOTAL: {fmt_brl(valor_total)}",
        "",
        f"Forma de pagamento: {condicoes_pagamento}",
    ]
    if prazo_entrega_dias:
        linhas.append(f"Prazo de entrega: {prazo_entrega_dias} dias")
    linhas.append(f"Fortaleza, {data_emissao.strftime('%d/%m/%Y')}")
    return "\n".join(linhas)


def texto_contrato_locacao(
    locatario_nome: str,
    locatario_endereco: str,
    descricao_piano: str,
    valor_total: float,
    data_entrega_dia: str,
    data_entrega_mes: str,
    local_entrega: str,
    data_segunda_parcela_dia: str,
    data_segunda_parcela_mes: str,
    data_contrato_dia: str,
    data_contrato_mes: str,
) -> str:
    valor_extenso = _valor_por_extenso_simples(valor_total)
    return f"""CONTRATO DE LOCAÇÃO – ASSIS PIANOS

LOCATÁRIO: {locatario_nome}
ENDEREÇO: {locatario_endereco}
BEM LOCADO: {descricao_piano}
VALOR: {fmt_brl(valor_total)} ({valor_extenso})
ENTREGA: {data_entrega_dia} de {data_entrega_mes} de 2026 – {local_entrega}
2ª PARCELA: {data_segunda_parcela_dia} de {data_segunda_parcela_mes} de 2026
CONTRATO: {data_contrato_dia} de {data_contrato_mes} de 2026

Fortaleza, {data_contrato_dia} de {data_contrato_mes} de 2026.
LOCADOR: {settings.COMPANY_RESPONSAVEL}
"""
