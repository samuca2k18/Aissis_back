from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, Literal

NegocioTipo = Literal["venda", "locacao", "manutencao"]
NegocioStatus = Literal["novo", "orcamento_enviado", "negociacao", "fechado", "perdido"]
DocTipo = Literal["orcamento", "contrato_locacao", "recibo", "proposta"]
LeadStatus = Literal["novo", "contatado", "orcamento", "negociacao", "convertido", "perdido"]
Temperatura = Literal["quente", "morno", "frio"]
CampanhaStatus = Literal["ativa", "pausada", "encerrada"]


# ─────────────────────────────────────────
#  CLIENTES
# ─────────────────────────────────────────
class ClienteCreate(BaseModel):
    nome: str = Field(min_length=2, max_length=200)
    telefone: str = Field(min_length=6, max_length=50)
    cidade: str = Field(min_length=2, max_length=120)
    cpf_cnpj: Optional[str] = Field(default=None, max_length=30)
    origem: Optional[str] = Field(default=None, max_length=80)
    tipo_pessoa: Literal["fisica", "juridica"] = "fisica"


class ClienteUpdate(BaseModel):
    nome: Optional[str] = None
    telefone: Optional[str] = None
    cidade: Optional[str] = None
    cpf_cnpj: Optional[str] = None
    origem: Optional[str] = None


class ClienteOut(BaseModel):
    id: int
    nome: str
    telefone: str
    cidade: str
    cpf_cnpj: Optional[str]
    origem: Optional[str]
    tipo_pessoa: str
    created_at: datetime
    model_config = {"from_attributes": True}


# ─────────────────────────────────────────
#  LEADS
# ─────────────────────────────────────────
class LeadCreate(BaseModel):
    nome: str = Field(min_length=2, max_length=200)
    telefone: Optional[str] = None
    origem: Optional[str] = None
    campanha: Optional[str] = None
    interesse: Optional[str] = None
    orcamento_estimado: Optional[float] = None
    temperatura: Temperatura = "morno"
    observacoes: Optional[str] = None
    cliente_id: Optional[int] = None


class LeadUpdateStatus(BaseModel):
    status: LeadStatus
    temperatura: Optional[Temperatura] = None


class LeadOut(BaseModel):
    id: int
    cliente_id: Optional[int]
    nome: str
    telefone: Optional[str]
    origem: Optional[str]
    campanha: Optional[str]
    interesse: Optional[str]
    orcamento_estimado: Optional[float]
    temperatura: str
    status: str
    observacoes: Optional[str]
    created_at: datetime
    model_config = {"from_attributes": True}


# ─────────────────────────────────────────
#  NEGÓCIOS
# ─────────────────────────────────────────
class NegocioCreate(BaseModel):
    cliente_id: int
    tipo: NegocioTipo
    valor: Optional[float] = None
    data_evento: Optional[datetime] = None
    data_entrega: Optional[datetime] = None
    local_evento: Optional[str] = None
    descricao_piano: Optional[str] = None
    observacoes: Optional[str] = None


class NegocioUpdateStatus(BaseModel):
    status: NegocioStatus


class NegocioOut(BaseModel):
    id: int
    cliente_id: int
    tipo: NegocioTipo
    status: NegocioStatus
    valor: Optional[float]
    data_evento: Optional[datetime]
    data_entrega: Optional[datetime]
    local_evento: Optional[str]
    descricao_piano: Optional[str]
    observacoes: Optional[str]
    created_at: datetime
    model_config = {"from_attributes": True}


# ─────────────────────────────────────────
#  DOCUMENTOS – Orçamento
# ─────────────────────────────────────────
class ItemOrcamento(BaseModel):
    descricao: str
    valor: float


class OrcamentoCreate(BaseModel):
    negocio_id: int
    cliente_nome: str
    cliente_cpf_cnpj: Optional[str] = None
    cliente_telefone: str
    cliente_cidade: str
    itens: list[ItemOrcamento] = Field(min_length=1)
    condicoes_pagamento: str = "40% na retirada e restante na entrega"
    prazo_entrega_dias: Optional[int] = None
    validade_dias: Optional[int] = 7
    data_emissao: Optional[datetime] = None
    observacoes: Optional[str] = None


# ─────────────────────────────────────────
#  DOCUMENTOS – Contrato de Locação
#  (baseado no modelo oficial da Assis Pianos)
# ─────────────────────────────────────────
class ContratoLocacaoCreate(BaseModel):
    negocio_id: int

    # Locatário
    locatario_nome: str
    locatario_endereco: str
    locatario_cpf_cnpj: Optional[str] = None

    # Objeto
    descricao_piano: str
    valor_total: float

    # Datas
    data_entrega_dia: str      # ex: "15"
    data_entrega_mes: str      # ex: "março"
    local_entrega: str

    # Pagamento (50/50 padrão)
    data_segunda_parcela_dia: str
    data_segunda_parcela_mes: str

    # Data do contrato
    data_contrato_dia: str
    data_contrato_mes: str


# ─────────────────────────────────────────
#  DOCUMENTOS – OUT
# ─────────────────────────────────────────
class DocumentoOut(BaseModel):
    id: int
    negocio_id: int
    tipo: str
    conteudo: str
    created_at: datetime
    model_config = {"from_attributes": True}


# ─────────────────────────────────────────
#  CAMPANHAS
# ─────────────────────────────────────────
class CampanhaCreate(BaseModel):
    nome: str
    plataforma: str
    investimento: float = 0.0
    leads_gerados: int = 0
    vendas: int = 0
    receita: float = 0.0
    status: CampanhaStatus = "ativa"
    data_inicio: Optional[datetime] = None
    data_fim: Optional[datetime] = None
    observacoes: Optional[str] = None


class CampanhaUpdate(BaseModel):
    investimento: Optional[float] = None
    leads_gerados: Optional[int] = None
    vendas: Optional[int] = None
    receita: Optional[float] = None
    status: Optional[CampanhaStatus] = None
    observacoes: Optional[str] = None


class CampanhaOut(BaseModel):
    id: int
    nome: str
    plataforma: str
    investimento: float
    leads_gerados: int
    vendas: int
    receita: float
    status: str
    custo_por_lead: Optional[float] = None
    roi_percentual: Optional[float] = None
    data_inicio: Optional[datetime]
    data_fim: Optional[datetime]
    observacoes: Optional[str]
    created_at: datetime
    model_config = {"from_attributes": True}


# ─────────────────────────────────────────
#  AGENDA
# ─────────────────────────────────────────
class AgendaCreate(BaseModel):
    titulo: str
    descricao: Optional[str] = None
    data_hora: datetime
    tipo: Literal["entrega", "evento", "manutencao", "afinacao", "followup", "outro"] = "outro"
    cliente_id: Optional[int] = None
    negocio_id: Optional[int] = None


class AgendaOut(BaseModel):
    id: int
    titulo: str
    descricao: Optional[str]
    data_hora: datetime
    tipo: str
    cliente_id: Optional[int]
    negocio_id: Optional[int]
    concluido: bool
    created_at: datetime
    model_config = {"from_attributes": True}


# ─────────────────────────────────────────
#  DASHBOARD
# ─────────────────────────────────────────
class DashboardOut(BaseModel):
    total_clientes: int
    total_negocios: int
    total_leads: int
    receita_fechada: float
    por_status: dict[str, int]
    leads_por_origem: dict[str, int]
    proximos_eventos: int
