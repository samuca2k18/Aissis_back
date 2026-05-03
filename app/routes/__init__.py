from .agenda import router as agenda
from .auditoria import router as auditoria
from .auth import router as auth
from .campanhas import router as campanhas
from .clientes import router as clientes
from .dashboard import router as dashboard
from .documentos import router as documentos
from .leads import router as leads
from .negocios import router as negocios
from . import whatsapp
from .whatsapp import router as whatsapp_router

__all__ = [
    "auth",
    "clientes",
    "leads",
    "negocios",
    "documentos",
    "campanhas",
    "agenda",
    "dashboard",
    "auditoria",
    "whatsapp",
    "whatsapp_router",
]
