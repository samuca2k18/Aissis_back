from .clientes import router as clientes
from .leads import router as leads
from .negocios import router as negocios
from .documentos import router as documentos
from .campanhas import router as campanhas
from .agenda import router as agenda
from .dashboard import router as dashboard

__all__ = ["clientes", "leads", "negocios", "documentos", "campanhas", "agenda", "dashboard"]
