from datetime import datetime

from pydantic import BaseModel


class AuditLogOut(BaseModel):
    id: int
    user_id: int | None
    role: str | None
    action: str
    method: str
    path: str
    status_code: int
    request_id: str | None
    ip_address: str | None
    user_agent: str | None
    details_json: str | None
    created_at: datetime
    model_config = {"from_attributes": True}
