"""
Gerador de PDF com os templates oficiais da Assis Pianos.
Documentos: Orçamento, Contrato de Locação e Recibo.
"""

import io
from datetime import datetime, timezone
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    HRFlowable,
    Image,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from ..settings import settings

# ─────────────────────────────────────────
#  ASSETS
# ─────────────────────────────────────────
_ASSETS = Path(__file__).parent.parent / "assets"


def _find_asset(name: str) -> Path | None:
    """Procura o asset com extensão png, jpg ou jpeg (nessa ordem)."""
    for ext in ("png", "jpg", "jpeg"):
        p = _ASSETS / f"{name}.{ext}"
        if p.exists():
            return p
    return None


def _logo_path() -> Path | None:
    return _find_asset("logo")


def _logo_recibo_path() -> Path | None:
    """Logo específica do recibo (logo_recibo) com fallback pra logo genérica."""
    p = _find_asset("logo_recibo")
    return p if p else _logo_path()


def _assinatura_path() -> Path | None:
    return _find_asset("assinatura")


# ─────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────
_MESES_PT = [
    "", "janeiro", "fevereiro", "março", "abril", "maio", "junho",
    "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
]


def _data_pt(dt: datetime) -> str:
    """Formata data em português: '11 de março de 2026'."""
    return f"{dt.day} de {_MESES_PT[dt.month]} de {dt.year}"


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

    return {
        "title": ParagraphStyle(
            "titulo", parent=normal, fontSize=16, fontName="Helvetica-Bold",
            alignment=TA_CENTER, spaceAfter=6,
        ),
        "header_company": ParagraphStyle(
            "header_company", parent=normal, fontSize=9, fontName="Helvetica-Bold",
            alignment=TA_CENTER, spaceAfter=2,
        ),
        "header_info": ParagraphStyle(
            "header_info", parent=normal, fontSize=8, fontName="Helvetica",
            alignment=TA_CENTER, spaceAfter=2,
        ),
        "section_title": ParagraphStyle(
            "section_title", parent=normal, fontSize=13, fontName="Helvetica-Bold",
            alignment=TA_CENTER, spaceAfter=4,
        ),
        "client_label": ParagraphStyle(
            "client_label", parent=normal, fontSize=12, fontName="Helvetica-Bold",
            spaceAfter=2,
        ),
        "body": ParagraphStyle(
            "body", parent=normal, fontSize=10, fontName="Helvetica",
            spaceAfter=4, leading=14,
        ),
        "body_bold": ParagraphStyle(
            "body_bold", parent=normal, fontSize=10, fontName="Helvetica-Bold",
            spaceAfter=4,
        ),
        "body_center": ParagraphStyle(
            "body_center", parent=normal, fontSize=10, fontName="Helvetica",
            alignment=TA_CENTER, spaceAfter=4, leading=14,
        ),
        "small": ParagraphStyle(
            "small", parent=normal, fontSize=9, fontName="Helvetica",
            alignment=TA_CENTER,
        ),
        "clause": ParagraphStyle(
            "clause", parent=normal, fontSize=10, fontName="Helvetica",
            spaceAfter=10, leading=15,
        ),
        "recibo_valor": ParagraphStyle(
            "recibo_valor", parent=normal, fontSize=18, fontName="Helvetica-Bold",
            alignment=TA_CENTER, spaceAfter=0,
        ),
        "recibo_texto": ParagraphStyle(
            "recibo_texto", parent=normal, fontSize=11, fontName="Helvetica-Bold",
            alignment=TA_JUSTIFY, spaceAfter=6, leading=18,
        ),
    }


def _company_header_full(s: dict) -> list:
    """Cabeçalho completo: logo centralizado + razão social + CNPJ + endereço + fone + e-mail."""
    elems = []
    if (_lp := _logo_path()) is not None:
        logo = Image(str(_lp), width=35 * mm, height=29 * mm)
        logo.hAlign = "CENTER"
        elems.append(logo)
        elems.append(Spacer(1, 2 * mm))
    elems.append(Paragraph(f"<b><u>{settings.COMPANY_NAME}</u></b>", s["header_company"]))
    elems.append(Paragraph(f"C.N.P.J: {settings.COMPANY_CNPJ}", s["header_info"]))
    elems.append(Paragraph(settings.COMPANY_ADDRESS, s["header_info"]))
    elems.append(Paragraph(f"Fone: {settings.COMPANY_PHONE}", s["header_info"]))
    elems.append(Paragraph(f"e-mail: {settings.COMPANY_EMAIL}", s["header_info"]))
    elems.append(Spacer(1, 8 * mm))
    return elems


def _company_header_recibo(s: dict) -> list:
    """Cabeçalho simplificado do recibo: logo + endereço + fone (sem CNPJ)."""
    elems = []
    lp = _logo_recibo_path()
    if lp is not None:
        logo = Image(str(lp), width=40 * mm, height=33 * mm)
        logo.hAlign = "CENTER"
        elems.append(logo)
        elems.append(Spacer(1, 2 * mm))
    elems.append(Paragraph(settings.COMPANY_ADDRESS, s["header_info"]))
    elems.append(Paragraph(f"Fone: {settings.COMPANY_PHONE}", s["header_info"]))
    elems.append(Spacer(1, 8 * mm))
    return elems


# Keep alias for contrato (unchanged)
_company_header_text = _company_header_full


def _assinatura_block(s: dict, nome: str = None) -> list:
    """Bloco de assinatura com imagem (se disponível) + linha + nome."""
    elems = []
    elems.append(Spacer(1, 14 * mm))
    if (_ap := _assinatura_path()) is not None:
        img = Image(str(_ap), width=80 * mm, height=12 * mm)
        img.hAlign = "CENTER"
        elems.append(img)
    # Sempre mostra a linha horizontal abaixo (com ou sem imagem)
    elems.append(HRFlowable(width="50%", thickness=0.5, color=colors.black, hAlign="CENTER"))
    responsavel = nome or settings.COMPANY_RESPONSAVEL
    elems.append(Paragraph(responsavel, s["small"]))
    return elems


# ─────────────────────────────────────────
#  ORÇAMENTO
# ─────────────────────────────────────────
def gerar_orcamento_pdf(
    cliente_nome: str,
    cliente_cpf_cnpj: str | None,
    cliente_telefone: str,
    cliente_cidade: str,
    itens: list[dict],
    valor_total: float,
    condicoes_pagamento: str,
    prazo_entrega_dias: int | None,
    descricao_piano: str | None = None,
    data_emissao: datetime | None = None,
    observacoes: str | None = None,
) -> bytes:
    if data_emissao is None:
        data_emissao = datetime.now(timezone.utc)
    data_str = _data_pt(data_emissao)

    buffer = io.BytesIO()
    doc = _base_doc(buffer)
    s = _styles()
    story = []

    # Cabeçalho empresa
    story += _company_header_text(s)

    # Título
    story.append(Paragraph("<u>O R Ç A M E N T O</u>", s["section_title"]))
    story.append(Spacer(1, 4 * mm))

    # Modelo do piano (se informado)
    if descricao_piano:
        story.append(Paragraph(f"<b>Piano {descricao_piano}</b>", s["client_label"]))

    # Nome do cliente
    story.append(Paragraph(f"<b>Cliente {cliente_nome}</b>", s["client_label"]))
    story.append(Spacer(1, 4 * mm))

    # Tabela de serviços
    table_data = [["SERVIÇO", "VALOR"]]
    for item in itens:
        table_data.append([item["descricao"], fmt_brl(item["valor"])])
    table_data.append(["TOTAL", fmt_brl(valor_total)])

    col_widths = [115 * mm, 45 * mm]
    table = Table(table_data, colWidths=col_widths, repeatRows=1)
    table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 10),
            ("BOX", (0, 0), (-1, 0), 0.5, colors.black),
            ("FONTNAME", (0, 1), (-1, -2), "Helvetica"),
            ("FONTSIZE", (0, 1), (-1, -2), 10),
            ("BOX", (0, 1), (-1, -2), 0.3, colors.black),
            ("GRID", (0, 1), (-1, -2), 0.3, colors.black),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
            ("FONTSIZE", (0, -1), (-1, -1), 10),
            ("BOX", (0, -1), (-1, -1), 0.5, colors.black),
        ])
    )
    story.append(table)
    story.append(Spacer(1, 5 * mm))

    # Prazo e pagamento
    if prazo_entrega_dias:
        story.append(Paragraph(f"prazo de entrega {prazo_entrega_dias} dias úteis", s["body"]))
    story.append(Spacer(1, 2 * mm))
    story.append(Paragraph(f"Forma de pagamento {condicoes_pagamento}", s["body"]))

    if observacoes:
        story.append(Spacer(1, 3 * mm))
        story.append(Paragraph(f"Observações: {observacoes}", s["body"]))

    # Assinatura com imagem
    story += _assinatura_block(s)
    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph(f"Fortaleza, {data_str}", s["small"]))

    doc.build(story)
    return buffer.getvalue()


# ─────────────────────────────────────────
#  RECIBO
# ─────────────────────────────────────────
def gerar_recibo_pdf(
    pagador_nome: str,
    valor: float,
    descricao: str,
    data_recibo: datetime | None = None,
) -> bytes:
    """
    Gera recibo no modelo oficial da Assis Pianos:
    logo + endereço + fone → R E C I B O → caixa valor (direita) → texto descritivo → assinatura
    """
    if data_recibo is None:
        data_recibo = datetime.now(timezone.utc)
    data_str = _data_pt(data_recibo)
    valor_extenso = _valor_por_extenso_simples(valor).upper()

    buffer = io.BytesIO()
    doc = _base_doc(buffer)
    s = _styles()
    story = []

    # ── Cabeçalho simplificado do recibo (logo + endereço + fone, SEM CNPJ)
    story += _company_header_recibo(s)

    # ── Título
    story.append(Paragraph("<b>R E C I B O</b>", s["title"]))
    story.append(Spacer(1, 6 * mm))

    # ── Caixa com valor destacado alinhada à DIREITA (igual ao modelo)
    page_w = A4[0] - 20 * mm - 20 * mm  # largura útil
    box_w = 60 * mm
    spacer_w = page_w - box_w

    valor_table = Table(
        [[Paragraph("", s["body"]), Paragraph(fmt_brl(valor), s["recibo_valor"])]],
        colWidths=[spacer_w, box_w],
    )
    valor_table.setStyle(TableStyle([
        ("BOX", (1, 0), (1, 0), 1.2, colors.black),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("ALIGN", (1, 0), (1, 0), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(valor_table)
    story.append(Spacer(1, 8 * mm))

    # ── Texto descritivo em negrito, maiúsculo, justificado
    pagador_upper = pagador_nome.upper()
    descricao_upper = descricao.upper()
    texto = (
        f" RECEBI DO SENHOR {pagador_upper} O VALOR {fmt_brl(valor)} "
        f"({valor_extenso}) REFERENTE A {descricao_upper}"
    )
    story.append(Paragraph(texto, s["recibo_texto"]))

    # ── Assinatura com imagem + linha
    story += _assinatura_block(s)
    story.append(Paragraph("Assinatura", s["small"]))
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

    story += _company_header_text(s)

    story.append(Paragraph("<b><u>CONTRATO DE LOCAÇÃO</u></b>", s["section_title"]))
    story.append(Spacer(1, 8 * mm))

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

    clausulas = [
        (
            "CLÁUSULA 1ª",
            f'O primeiro nomeado aqui chamado "LOCADOR", aluga ao segundo nomeado, aqui chamado '
            f'"LOCATÁRIO", pelo preço certo ajustado o total de <b>{fmt_brl(valor_total)}</b> '
            f"(<b>{valor_extenso}</b>) um <b>{descricao_piano}</b>.",
        ),
        (
            "CLÁUSULA 2ª",
            f"O LOCADOR compromete-se a entregar o piano na data de <b>{data_entrega_dia}</b> de "
            f"<b>{data_entrega_mes}</b> de 2026 no <b>{local_entrega}</b>.",
        ),
        (
            "CLÁUSULA 3ª",
            f"O LOCATÁRIO compromete-se a pagar o bem descrito na cláusula 1ª no ato desse contrato "
            f"<b>50 por cento</b> para reserva do Piano e <b>50 por cento</b> no dia "
            f"<b>{data_segunda_parcela_dia}</b> de <b>{data_segunda_parcela_mes}</b> de 2026.",
        ),
        (
            "CLÁUSULA 4ª",
            "O LOCATÁRIO deverá manter o piano em perfeitas e em igual condições de uso até a devolução do mesmo.",
        ),
        (
            "CLÁUSULA 5ª",
            "Havendo algum dano ao bem descrito em posse ainda do LOCATÁRIO este se responsabilizará "
            "pelo ressarcimento dos eventuais danos.",
        ),
    ]

    for num, texto in clausulas:
        story.append(Paragraph(f"<b>{num}</b> – {texto}", s["clause"]))

    story.append(Spacer(1, 6 * mm))
    story.append(Paragraph(f"Fortaleza, {data_contrato_dia} de {data_contrato_mes} de 2026.", s["body"]))

    story.append(Spacer(1, 16 * mm))
    assinatura_data = [
        [Paragraph(settings.COMPANY_RESPONSAVEL, s["small"]), Paragraph(locatario_nome, s["small"])],
        [Paragraph("<b>LOCADOR</b>", s["small"]), Paragraph("<b>LOCATÁRIO</b>", s["small"])],
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
    """Converte valores em extenso (BRL). Cobre 0–999.999,99."""
    unidades = [
        "", "um", "dois", "três", "quatro", "cinco", "seis", "sete", "oito", "nove",
        "dez", "onze", "doze", "treze", "quatorze", "quinze", "dezesseis",
        "dezessete", "dezoito", "dezenove",
    ]
    dezenas = ["", "", "vinte", "trinta", "quarenta", "cinquenta", "sessenta", "setenta", "oitenta", "noventa"]
    centenas = [
        "", "cento", "duzentos", "trezentos", "quatrocentos", "quinhentos",
        "seiscentos", "setecentos", "oitocentos", "novecentos",
    ]

    def _centenas(n: int) -> str:
        """Converte número de 0-999 em extenso."""
        if n == 0:
            return ""
        if n == 100:
            return "cem"
        parts = []
        c = n // 100
        resto = n % 100
        if c:
            parts.append(centenas[c])
        if 0 < resto < 20:
            parts.append(unidades[resto])
        elif resto >= 20:
            d = resto // 10
            u = resto % 10
            parts.append(dezenas[d] + (" e " + unidades[u] if u else ""))
        return " e ".join(parts)

    def _inteiro_extenso(n: int) -> str:
        if n == 0:
            return "zero"
        partes = []
        milhares = n // 1000
        resto = n % 1000
        if milhares:
            if milhares == 1:
                partes.append("mil")
            else:
                partes.append(_centenas(milhares) + " mil")
        if resto:
            partes.append(_centenas(resto))
        return " e ".join(partes)

    inteiro = int(valor)
    centavos = round((valor - inteiro) * 100)

    reais_str = _inteiro_extenso(inteiro)
    sufixo_reais = "real" if inteiro == 1 else "reais"

    if centavos:
        cent_str = _centenas(centavos)
        sufixo_cent = "centavo" if centavos == 1 else "centavos"
        return f"{reais_str} {sufixo_reais} e {cent_str} {sufixo_cent}"
    return f"{reais_str} {sufixo_reais}"


# ─────────────────────────────────────────
#  TEXTO PLANO (fallback / armazenamento)
# ─────────────────────────────────────────
def texto_orcamento(
    cliente_nome: str,
    itens: list[dict],
    valor_total: float,
    condicoes_pagamento: str,
    prazo_entrega_dias: int | None,
    descricao_piano: str | None = None,
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
    ]
    if descricao_piano:
        linhas.append(f"Piano: {descricao_piano}")
    linhas += [
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
    linhas.append(f"Fortaleza, {data_emissao.strftime("%d/%m/%Y")}")
    return "\n".join(linhas)


def texto_recibo(
    pagador_nome: str,
    valor: float,
    descricao: str,
    data_recibo: datetime | None = None,
) -> str:
    if data_recibo is None:
        data_recibo = datetime.now(timezone.utc)
    valor_extenso = _valor_por_extenso_simples(valor).upper()
    return (
        f"RECIBO – ASSIS PIANOS\n\n"
        f"RECEBI DO SENHOR {pagador_nome.upper()} O VALOR {fmt_brl(valor)} "
        f"({valor_extenso}) REFERENTE A {descricao.upper()}\n\n"
        f"Fortaleza, {data_recibo.strftime("%d/%m/%Y")}\n"
        f"ASSIS PIANOS – {settings.COMPANY_RESPONSAVEL}\n"
    )


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
    return (
        f"CONTRATO DE LOCAÇÃO – ASSIS PIANOS\n\n"
        f"LOCATÁRIO: {locatario_nome}\n"
        f"ENDEREÇO: {locatario_endereco}\n"
        f"BEM LOCADO: {descricao_piano}\n"
        f"VALOR: {fmt_brl(valor_total)} ({valor_extenso})\n"
        f"ENTREGA: {data_entrega_dia} de {data_entrega_mes} de 2026 – {local_entrega}\n"
        f"2ª PARCELA: {data_segunda_parcela_dia} de {data_segunda_parcela_mes} de 2026\n"
        f"CONTRATO: {data_contrato_dia} de {data_contrato_mes} de 2026\n\n"
        f"Fortaleza, {data_contrato_dia} de {data_contrato_mes} de 2026.\n"
        f"LOCADOR: {settings.COMPANY_RESPONSAVEL}\n"
    )