from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

DocTipo = Literal["orcamento", "contrato_locacao", "recibo", "proposta"]


class ItemOrcamento(BaseModel):
    descricao: str
    valor: float


class OrcamentoCreate(BaseModel):
    negocio_id: int
    cliente_nome: str
    cliente_cpf_cnpj: str | None = None
    cliente_telefone: str
    cliente_cidade: str
    itens: list[ItemOrcamento] = Field(min_length=1)
    condicoes_pagamento: str = "40% na retirada e restante na entrega"
    prazo_entrega_dias: int | None = None
    validade_dias: int | None = 7
    data_emissao: datetime | None = None
    observacoes: str | None = None


class ContratoLocacaoCreate(BaseModel):
    negocio_id: int

    # Locatário
    locatario_nome: str
    locatario_endereco: str
    locatario_cpf_cnpj: str | None = None

    # Objeto
    descricao_piano: str
    valor_total: float

    # Datas
    data_entrega_dia: str  # ex: "15"
    data_entrega_mes: str  # ex: "março"
    local_entrega: str

    # Pagamento (50/50 padrão)
    data_segunda_parcela_dia: str
    data_segunda_parcela_mes: str

    # Data do contrato
    data_contrato_dia: str
    data_contrato_mes: str


class DocumentoOut(BaseModel):
    id: int
    negocio_id: int
    tipo: str
    conteudo: str
    created_at: datetime
    model_config = {"from_attributes": True}
