from pydantic import BaseModel


class DashboardOut(BaseModel):
    total_clientes: int
    total_negocios: int
    total_leads: int
    receita_fechada: float
    por_status: dict[str, int]
    leads_por_origem: dict[str, int]
    proximos_eventos: int
