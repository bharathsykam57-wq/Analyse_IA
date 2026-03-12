"""RGPD compliance endpoints: consent management, data export/deletion.

Endpoints:
  POST /rgpd/consent - Record consent for data processing (RGPD Article 7)
  GET /rgpd/consent - List active consents for user
  GET /rgpd/export - Export all personal data (RGPD Articles 15, 20)
  DELETE /rgpd/erasure - Anonymize user account (RGPD Article 17)
  GET /rgpd/audit - View action audit trail for current user

All endpoints require JWT authentication (get_current_active_user).
All data access logged to immutable audit trail.
"""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from backend.api.dependencies import get_db
from backend.api.auth.router import get_current_active_user
from backend.api.auth.models import User
from backend.api.rgpd.schemas import (
    ConsentRequest, ConsentResponse,
    AuditLogResponse, ExportResponse, ErasureResponse,
)
from backend.api.rgpd.service import (
    record_consent, get_consents,
    export_user_data, erase_user_data, write_audit_log,
)
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/rgpd", tags=["rgpd"])


@router.post("/consent", response_model=ConsentResponse, status_code=status.HTTP_201_CREATED)
async def consent(
    request: Request,
    body: ConsentRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Record user consent for a data processing purpose (RGPD Article 7).
    
    Requires explicit user consent for each processing purpose.
    If user already consented to this purpose, previous consent revoked.
    All consent records preserved (soft-delete via revocation).
    
    Request: {"purpose": "data_analysis", "granted": true}
    Response: Consent record with id, purpose, timestamps, revocation status
    
    Raises:
        400 Bad Request: Invalid purpose (not in VALID_PURPOSES)
    """
    try:
        ip = request.client.host if request.client else None
        result = record_consent(
            user_id=current_user.id,
            purpose=body.purpose,
            granted=body.granted,
            ip_address=ip,
            db=db,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/consent", response_model=list[ConsentResponse])
async def list_consents(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """List active (non-revoked) consents for current user (RGPD Article 21).
    
    Returns only currently active consents (granted=True, revoked_at=NULL).
    Useful for user to review their consent status and revoke anytime.
    
    Response: Array of ConsentResponse objects (may be empty)
    """
    return get_consents(current_user.id, db)


@router.get("/export", response_model=ExportResponse)
async def export(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Export all personal data as JSON (RGPD Articles 15, 20).
    
    Right to Access (Article 15): User can see all data we hold.
    Right to Portability (Article 20): User can export data in portable format.
    Returns user profile, all consent records, complete action audit trail.
    Action logged to audit trail for compliance.
    
    Response: JSON with user, consents, audit_logs (max 1000 logs)
    
    Raises:
        404 Not Found: User not found
    """
    try:
        data = export_user_data(current_user.id, db)
        write_audit_log(
            user_id=current_user.id,
            action="data_export",
            resource=f"user:{current_user.id}",
            details={"email": current_user.email},
            ip_address=None,
            db=db,
        )
        return data
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.delete("/erasure", response_model=ErasureResponse, status_code=status.HTTP_200_OK)
async def erasure(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Anonymize user account (RGPD Article 17 - Right to Erasure).
    
    Implements right to be forgotten. Anonymizes user instead of hard delete
    to preserve audit trail integrity required by CNIL.
    - Email masked as deleted_{user_id}@anonymised.rgpd
    - Account deactivated, password erased
    - All sessions revoked (refresh tokens deleted)
    - Audit logs preserved (SET NULL, not deleted)
    
    Response: Confirmation with timestamp of deletion
    
    Raises:
        404 Not Found: User not found
    """
    try:
        deleted_at = erase_user_data(current_user.id, db)
        return ErasureResponse(
            message="Vos données ont été anonymisées conformément au RGPD Article 17.",
            user_id=str(current_user.id),
            deleted_at=deleted_at,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/audit", response_model=list[AuditLogResponse])
async def audit_log(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """View action audit trail for current user (CNIL requirement, Article 32).
    
    Returns complete history of user actions (queries, uploads, exports, etc.)
    for compliance audit and user transparency.
    Records sorted newest first, limited to 100 most recent.
    
    Response: Array of AuditLogResponse (action, resource, timestamp, IP)
    """
    from backend.api.rgpd.models import AuditLog
    logs = db.query(AuditLog).filter(
        AuditLog.user_id == current_user.id
    ).order_by(AuditLog.created_at.desc()).limit(100).all()
    return logs