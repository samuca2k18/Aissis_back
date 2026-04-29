from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import schemas
from app.database import get_db
from app.models.audit_log import AuditLog
from app.security import require_role

router = APIRouter(
    prefix="/auditoria",
    tags=["auditoria"],
    dependencies=[Depends(require_role("admin"))],
)


@router.get("", response_model=list[schemas.AuditLogOut])
def list_auditoria(limit: int = 100, db: Session = Depends(get_db)):
    safe_limit = max(1, min(limit, 500))
    return (
        db.query(AuditLog)
        .order_by(AuditLog.created_at.desc())
        .limit(safe_limit)
        .all()
    )
