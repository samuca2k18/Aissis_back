from app.schemas.agenda import AgendaCreate, AgendaOut
from app.schemas.audit import AuditLogOut
from app.schemas.auth import BootstrapAdminInput, LoginInput, TokenOutput
from app.schemas.campanha import CampanhaCreate, CampanhaOut, CampanhaStatus, CampanhaUpdate
from app.schemas.cliente import ClienteCreate, ClienteOut, ClienteUpdate
from app.schemas.dashboard import DashboardOut
from app.schemas.documento import (
    ContratoLocacaoCreate,
    DocTipo,
    DocumentoOut,
    ItemOrcamento,
    OrcamentoCreate,
    ReciboCreate,
)
from app.schemas.lead import LeadCreate, LeadOut, LeadStatus, LeadUpdateStatus, Temperatura
from app.schemas.negocio import NegocioCreate, NegocioOut, NegocioStatus, NegocioTipo, NegocioUpdateStatus
from app.schemas.user import UserCreate, UserOut, UserRole, UserStatusUpdate

__all__ = [
    "LoginInput",
    "BootstrapAdminInput",
    "TokenOutput",
    "UserCreate",
    "UserStatusUpdate",
    "UserOut",
    "UserRole",
    "AuditLogOut",
    "ClienteCreate",
    "ClienteUpdate",
    "ClienteOut",
    "LeadCreate",
    "LeadUpdateStatus",
    "LeadOut",
    "LeadStatus",
    "Temperatura",
    "NegocioCreate",
    "NegocioUpdateStatus",
    "NegocioOut",
    "NegocioTipo",
    "NegocioStatus",
    "ItemOrcamento",
    "OrcamentoCreate",
    "ContratoLocacaoCreate",
    "ReciboCreate",
    "DocumentoOut",
    "DocTipo",
    "CampanhaCreate",
    "CampanhaUpdate",
    "CampanhaOut",
    "CampanhaStatus",
    "AgendaCreate",
    "AgendaOut",
    "DashboardOut",
]
