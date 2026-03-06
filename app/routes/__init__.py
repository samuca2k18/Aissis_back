from .agenda import router as agenda
from .campanhas import router as campanhas
from .clientes import router as clientes
from .dashboard import router as dashboard
from .documentos import router as documentos
from .leads import router as leads
from .negocios import router as negocios

__all__ = ["clientes", "leads", "negocios", "documentos", "campanhas", "agenda", "dashboard"]
