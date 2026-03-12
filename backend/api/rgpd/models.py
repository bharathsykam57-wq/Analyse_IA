"""RGPD compliance models: consent tracking and audit logging.

Design:
  - Soft-delete pattern: records archived via timestamp fields, never deleted
  - User can revoke consent anytime (revoked_at tracks withdrawal)
  - Complete audit trail required by CNIL for compliance investigation
  - IP address recorded when consent given/revoked for security

Compliance:
  - RGPD Article 7: Explicit informed consent required
  - RGPD Article 15-17: Right to access, rectify, erase data
  - CNIL: Immutable audit trail for investigation (never delete)
"""

from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Text, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from backend.api.auth.models import Base
from datetime import datetime, timezone
import uuid


class Consent(Base):
    """User consent for data processing purposes (RGPD Article 7).
    
    Each data processing purpose requires explicit user consent.
    Users can revoke at any time. Revocation tracked via revoked_at (not deleted).
    
    Fields:
        purpose: Data processing purpose (e.g., data_analysis, rag_indexing)
        granted: True if user consents, False if declined
        granted_at: Timestamp when consent given
        revoked_at: Timestamp when revoked (None = still active)
        ip_address: Client IP when consent recorded
    
    Current Consent: granted=True AND revoked_at=NULL
    """
    __tablename__ = "consents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"),
                     nullable=False, index=True)
    purpose = Column(String(100), nullable=False)  # e.g. "data_analysis", "rag_indexing"
    granted = Column(Boolean, nullable=False)
    granted_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    ip_address = Column(String(45), nullable=True)  # IPv4 or IPv6

    user = relationship("User", backref="consents")


class AuditLog(Base):
    """Immutable audit trail of all user actions (CNIL requirement).
    
    Records every significant user action for security investigation and compliance.
    Records NEVER deleted (immutable trail). User deletion does NOT cascade
    (SET NULL) to preserve audit history per CNIL guidelines.
    
    Fields:
        action: Action type (e.g., agent_query, file_upload, data_export)
        resource: Affected resource identifier (e.g., file:uuid, task:task_id)
        details: JSON context (query text, file size, result summary, etc.)
        ip_address: Client IP address at time of action
    
    Design: Immutable (append-only), survives user deletion, indexed for export
    """
    __tablename__ = "audit_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"),
                     nullable=True, index=True)
    action = Column(String(100), nullable=False)
    resource = Column(String(100), nullable=True)
    details = Column(JSON, nullable=True)
    ip_address = Column(String(45), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    user = relationship("User", backref="audit_logs")