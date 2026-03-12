"""RGPD service: consent management, audit logging, data export/deletion.

Functions:
  - record_consent: Track user consent for a data processing purpose
  - get_consents: List active (non-revoked) consents for user
  - write_audit_log: Log all user actions for compliance audit trail
  - export_user_data: Generate portable JSON of all user data (Article 20)
  - erase_user_data: Anonymize user (Article 17 right to erasure)
"""

from sqlalchemy.orm import Session
from datetime import datetime, timezone
import logging

from backend.api.auth.models import User, RefreshToken
from backend.api.rgpd.models import Consent, AuditLog

logger = logging.getLogger(__name__)

# RGPD Article 5: Explicit documented purposes for data processing
VALID_PURPOSES = {
    "data_analysis",     # Phase 1: CSV analysis via EDA engines
    "rag_indexing",      # Phase 2: PDF indexing via RAG
    "agent_query",       # Phase 3: Master agent queries
    "code_execution",    # Phase 4: Code sandbox execution
}


def record_consent(user_id, purpose: str, granted: bool,
                   ip_address: str, db: Session) -> Consent:
    """Record user consent for a data processing purpose (RGPD Article 7).
    
    Ensures explicit, documented consent. If user already consented to this purpose,
    revokes previous consent before recording new one (consent history preserved).
    
    Args:
        user_id: User UUID
        purpose: Processing purpose (must be in VALID_PURPOSES)
        granted: True if user consents, False if declined
        ip_address: Client IP for audit trail
        db: Database session
    
    Returns: Created Consent record
    
    Raises: ValueError if purpose not in VALID_PURPOSES
    """
    if purpose not in VALID_PURPOSES:
        raise ValueError(f"Finalité invalide: {purpose}. "
                         f"Finalités autorisées: {', '.join(VALID_PURPOSES)}")

    # Revoke existing consent for same purpose (soft-delete: set revoked_at)
    existing = db.query(Consent).filter(
        Consent.user_id == user_id,
        Consent.purpose == purpose,
        Consent.revoked_at == None,
    ).first()

    if existing:
        existing.revoked_at = datetime.now(timezone.utc)
        db.commit()

    consent = Consent(
        user_id=user_id,
        purpose=purpose,
        granted=granted,
        ip_address=ip_address,
    )
    db.add(consent)
    db.commit()
    db.refresh(consent)

    logger.info(f"Consent recorded: user={user_id} purpose={purpose} granted={granted}")
    return consent


def get_consents(user_id, db: Session) -> list:
    """Get active consents for user (RGPD Article 7, 21).
    
    Returns only non-revoked consents (revoked_at = NULL).
    Used to check if user has granted consent before processing their data.
    
    Args:
        user_id: User UUID
        db: Database session
    
    Returns: List of active Consent records
    """
    return db.query(Consent).filter(
        Consent.user_id == user_id,
        Consent.revoked_at == None,
    ).all()


def write_audit_log(user_id, action: str, resource: str,
                    details: dict, ip_address: str, db: Session) -> AuditLog:
    """Log user action to immutable audit trail (CNIL requirement).
    
    Records every significant action for compliance investigation and data export.
    Audit logs support right to erasure (user deleted) but persist themselves
    for compliance (SET NULL, not CASCADE delete).
    
    Args:
        user_id: User UUID (nullable if user deleted)
        action: Action type (agent_query, file_upload, data_export, consent_revoke)
        resource: Affected resource ID (file:uuid, task:task_id)
        details: JSON context (query, result summary, file size, etc.)
        ip_address: Client IP for security investigation
        db: Database session
    
    Returns: Created AuditLog record
    """
    log = AuditLog(
        user_id=user_id,
        action=action,
        resource=resource,
        details=details,
        ip_address=ip_address,
    )
    db.add(log)
    db.commit()
    return log


def export_user_data(user_id, db: Session) -> dict:
    """Export all user data as portable JSON (RGPD Article 15, 20).
    
    Implements right to access (Article 15) and right to portability (Article 20).
    Returns user profile, all consent records, and complete action audit trail.
    Suitable for download or transfer to another service.
    
    Args:
        user_id: User UUID
        db: Database session
    
    Returns: Dict with user profile, consents, and audit logs
    
    Raises: ValueError if user not found
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise ValueError("Utilisateur introuvable")

    consents = db.query(Consent).filter(Consent.user_id == user_id).all()
    logs = db.query(AuditLog).filter(AuditLog.user_id == user_id).all()

    logger.info(f"Data export requested: user={user_id}")

    return {
        "user_id": str(user.id),
        "email": user.email,
        "full_name": user.full_name,
        "preferred_language": user.preferred_language,
        "created_at": user.created_at,
        "consents": consents,
        "audit_logs": logs,
    }


def erase_user_data(user_id, db: Session) -> datetime:
    """Anonymize user account (RGPD Article 17 - Right to Erasure).
    
    Implements right to be forgotten. Instead of hard delete (which would break
    audit trail integrity), anonymizes user:
    - Email masked as deleted_{user_id}@anonymised.rgpd
    - Password erased, account deactivated
    - All refresh tokens revoked
    - Audit logs preserved (SET NULL foreign key) for compliance
    
    Args:
        user_id: User UUID
        db: Database session
    
    Returns: Timestamp of deletion (UTC)
    
    Raises: ValueError if user not found
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise ValueError("Utilisateur introuvable")

    # Anonymize instead of hard delete to preserve audit trail integrity
    user.email = f"deleted_{user_id}@anonymised.rgpd"
    user.full_name = None
    user.hashed_password = "ERASED"
    user.is_active = False

    # Revoke all refresh tokens (forces re-authentication)
    db.query(RefreshToken).filter(RefreshToken.user_id == user_id).delete()

    deleted_at = datetime.now(timezone.utc)
    db.commit()

    logger.info(f"User data erased: user={user_id}")
    return deleted_at