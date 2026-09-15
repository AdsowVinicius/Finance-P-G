from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, require_admin
from app.database import get_db
from app.models.log_auditoria import LogAuditoria
from app.schemas.auditoria import LogAuditoriaRead

router = APIRouter(
    prefix="/auditoria", tags=["auditoria"], dependencies=[Depends(get_current_user), Depends(require_admin)]
)


@router.get("", response_model=list[LogAuditoriaRead])
def listar_logs(entidade: str | None = None, db: Session = Depends(get_db)) -> list[LogAuditoria]:
    query = db.query(LogAuditoria)
    if entidade is not None:
        query = query.filter(LogAuditoria.entidade == entidade)
    return query.order_by(LogAuditoria.created_at.desc()).limit(500).all()
