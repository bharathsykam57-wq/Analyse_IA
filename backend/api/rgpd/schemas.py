
"""RGPD schemas for consent and audit logging endpoints."""

from pydantic import BaseModel
from datetime import datetime
from uuid import UUID
from typing import Optional, List


class ConsentRequest(BaseModel):
    """Request to grant or revoke consent for data processing.
    
    Used by: POST /rgpd/consent - User grants/revokes consent for a purpose
    Example: {"purpose": "data_analysis", "granted": true}
    """
    purpose: str
    granted: bool


class ConsentResponse(BaseModel):
    """Consent record with grant/revoke history.
    
    Used by: GET /rgpd/consents - List user's consent records
    granted=True & revoked_at=NULL: Currently active
    granted=False | revoked_at!=NULL: Withdrawn or declined
    """
    id: UUID
    purpose: str
    granted: bool
    granted_at: datetime
    revoked_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class AuditLogResponse(BaseModel):
    """Single audit log entry (immutable action record).
    
    Used by: GET /rgpd/audit - List user's action history
    Actions: agent_query, file_upload, data_export, consent_revoke, etc.
    Details: Contextual JSON (query text, file size, result summary)
    """
    id: UUID
    action: str
    resource: Optional[str]
    details: Optional[dict]
    created_at: datetime

    model_config = {"from_attributes": True}


class ExportResponse(BaseModel):
    """Complete user data export (RGPD Article 15 - Right to Access).
    
    Used by: POST /rgpd/export - User downloads all their data
    Format: JSON with profile, consents, and complete action history
    Suitable for portability to another service
    """
    user_id: str
    email: str
    full_name: Optional[str]
    preferred_language: str
    created_at: datetime
    consents: List[ConsentResponse]
    audit_logs: List[AuditLogResponse]


class ErasureResponse(BaseModel):
    """Confirmation of user deletion (RGPD Article 17 - Right to be Forgotten).
    
    Used by: POST /rgpd/delete - User requests complete account deletion
    Result: Hard delete user profile and files, soft-delete audit logs (keep for compliance)
    Message: Confirmation text for user
    """
    message: str
    user_id: str
    deleted_at: datetime