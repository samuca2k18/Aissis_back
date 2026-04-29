import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog


@dataclass
class AuditEvent:
    action: str
    method: str
    path: str
    status_code: int
    request_id: str | None
    ip_address: str | None
    user_agent: str | None
    user_id: int | None = None
    role: str | None = None
    details: dict[str, Any] | None = None


def register_audit_event(db: Session, event: AuditEvent) -> AuditLog:
    row = AuditLog(
        user_id=event.user_id,
        role=event.role,
        action=event.action,
        method=event.method,
        path=event.path,
        status_code=event.status_code,
        request_id=event.request_id,
        ip_address=event.ip_address,
        user_agent=event.user_agent,
        details_json=json.dumps(event.details, ensure_ascii=False) if event.details else None,
        created_at=datetime.now(UTC),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row
