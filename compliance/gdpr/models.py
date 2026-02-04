"""
GDPR SQLAlchemy Models
ReviewSignal 5.0

Database models for GDPR compliance:
- GDPRConsent: Consent tracking
- GDPRRequest: Data subject requests
- GDPRAuditLog: Audit trail
- DataRetentionPolicy: Automatic cleanup rules
"""

from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, Text,
    ForeignKey, Index, Enum as SQLEnum, CheckConstraint, ARRAY
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional, List, Dict, Any

import sys
sys.path.insert(0, '/home/info_betsim/reviewsignal-5.0')

from modules.database_schema import Base


class ConsentTypeEnum(str, Enum):
    """Types of consent that can be granted"""
    marketing = "marketing"
    data_processing = "data_processing"
    analytics = "analytics"
    third_party_sharing = "third_party_sharing"


class ConsentStatusEnum(str, Enum):
    """Status of a consent"""
    granted = "granted"
    withdrawn = "withdrawn"
    expired = "expired"


class RequestTypeEnum(str, Enum):
    """Types of GDPR requests"""
    data_export = "data_export"
    data_erasure = "data_erasure"
    data_access = "data_access"
    data_rectification = "data_rectification"
    processing_restriction = "processing_restriction"
    data_portability = "data_portability"


class RequestStatusEnum(str, Enum):
    """Status of a GDPR request"""
    pending = "pending"
    in_progress = "in_progress"
    completed = "completed"
    rejected = "rejected"
    cancelled = "cancelled"


class AuditActionEnum(str, Enum):
    """Types of audit actions"""
    consent_granted = "consent_granted"
    consent_withdrawn = "consent_withdrawn"
    consent_expired = "consent_expired"
    data_accessed = "data_accessed"
    data_exported = "data_exported"
    data_deleted = "data_deleted"
    data_anonymized = "data_anonymized"
    request_created = "request_created"
    request_processed = "request_processed"
    request_completed = "request_completed"
    request_rejected = "request_rejected"
    retention_cleanup = "retention_cleanup"
    policy_updated = "policy_updated"
    verification_sent = "verification_sent"
    verification_completed = "verification_completed"


class RetentionActionEnum(str, Enum):
    """Actions for data retention"""
    delete = "delete"
    anonymize = "anonymize"
    archive = "archive"


class GDPRConsent(Base):
    """
    GDPR Consent tracking model.
    Tracks consent status for each subject and consent type.
    """
    __tablename__ = 'gdpr_consents'

    consent_id = Column(Integer, primary_key=True, autoincrement=True)
    subject_email = Column(String(255), nullable=False, index=True)
    consent_type = Column(
        SQLEnum(ConsentTypeEnum, name='consent_type_enum', create_type=False),
        nullable=False
    )
    status = Column(
        SQLEnum(ConsentStatusEnum, name='consent_status_enum', create_type=False),
        nullable=False,
        default=ConsentStatusEnum.granted
    )
    granted_at = Column(DateTime(timezone=True), server_default=func.now())
    withdrawn_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)
    consent_version = Column(String(20), default='1.0')
    consent_text = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index('idx_gdpr_consents_email', 'subject_email'),
        Index('idx_gdpr_consents_status', 'status'),
        Index('idx_gdpr_consents_type', 'consent_type'),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "consent_id": self.consent_id,
            "subject_email": self.subject_email,
            "consent_type": self.consent_type.value if self.consent_type else None,
            "status": self.status.value if self.status else None,
            "granted_at": self.granted_at.isoformat() if self.granted_at else None,
            "withdrawn_at": self.withdrawn_at.isoformat() if self.withdrawn_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "consent_version": self.consent_version,
        }

    def is_valid(self) -> bool:
        """Check if consent is currently valid"""
        if self.status != ConsentStatusEnum.granted:
            return False
        if self.expires_at:
            # Handle timezone-aware and naive datetimes
            expires = self.expires_at.replace(tzinfo=None) if self.expires_at.tzinfo else self.expires_at
            if expires < datetime.utcnow():
                return False
        return True


class GDPRRequest(Base):
    """
    GDPR Request tracking model.
    Tracks data subject requests (export, erasure, access, etc.)
    """
    __tablename__ = 'gdpr_requests'

    request_id = Column(Integer, primary_key=True, autoincrement=True)
    subject_email = Column(String(255), nullable=False, index=True)
    request_type = Column(
        SQLEnum(RequestTypeEnum, name='request_type_enum', create_type=False),
        nullable=False
    )
    status = Column(
        SQLEnum(RequestStatusEnum, name='request_status_enum', create_type=False),
        nullable=False,
        default=RequestStatusEnum.pending
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    deadline_at = Column(DateTime(timezone=True), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    processed_by = Column(String(255), nullable=True)
    result_file_url = Column(String(500), nullable=True)
    result_file_size = Column(Integer, nullable=True)
    rejection_reason = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)
    verification_token = Column(String(255), nullable=True)
    verified_at = Column(DateTime(timezone=True), nullable=True)

    # Relationship to audit logs
    audit_logs = relationship("GDPRAuditLog", back_populates="request")

    __table_args__ = (
        Index('idx_gdpr_requests_email', 'subject_email'),
        Index('idx_gdpr_requests_status', 'status'),
        Index('idx_gdpr_requests_type', 'request_type'),
        Index('idx_gdpr_requests_deadline', 'deadline_at'),
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Set deadline to 30 days from now (GDPR requirement)
        if not self.deadline_at:
            self.deadline_at = datetime.utcnow() + timedelta(days=30)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "subject_email": self.subject_email,
            "request_type": self.request_type.value if self.request_type else None,
            "status": self.status.value if self.status else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "deadline_at": self.deadline_at.isoformat() if self.deadline_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "processed_by": self.processed_by,
            "result_file_url": self.result_file_url,
            "is_overdue": self.is_overdue(),
            "days_remaining": self.days_remaining(),
        }

    def is_overdue(self) -> bool:
        """Check if request is past deadline"""
        if self.status in [RequestStatusEnum.completed, RequestStatusEnum.rejected, RequestStatusEnum.cancelled]:
            return False
        if not self.deadline_at:
            return False
        deadline = self.deadline_at.replace(tzinfo=None) if self.deadline_at.tzinfo else self.deadline_at
        return datetime.utcnow() > deadline

    def days_remaining(self) -> int:
        """Get days remaining until deadline"""
        if not self.deadline_at:
            return 0
        deadline = self.deadline_at.replace(tzinfo=None) if self.deadline_at.tzinfo else self.deadline_at
        delta = deadline - datetime.utcnow()
        return max(0, delta.days)


class GDPRAuditLog(Base):
    """
    GDPR Audit Log model.
    Immutable audit trail for GDPR compliance.
    """
    __tablename__ = 'gdpr_audit_log'

    audit_id = Column(Integer, primary_key=True, autoincrement=True)
    action = Column(
        SQLEnum(AuditActionEnum, name='audit_action_enum', create_type=False),
        nullable=False
    )
    subject_email = Column(String(255), nullable=True, index=True)
    affected_tables = Column(ARRAY(String), nullable=True)
    affected_records_count = Column(Integer, default=0)
    performed_by = Column(String(255), nullable=True)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)
    request_id = Column(Integer, ForeignKey('gdpr_requests.request_id'), nullable=True)
    details = Column(JSONB, default={})
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationship to request
    request = relationship("GDPRRequest", back_populates="audit_logs")

    __table_args__ = (
        Index('idx_gdpr_audit_email', 'subject_email'),
        Index('idx_gdpr_audit_action', 'action'),
        Index('idx_gdpr_audit_created', 'created_at'),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "audit_id": self.audit_id,
            "action": self.action.value if self.action else None,
            "subject_email": self.subject_email,
            "affected_tables": self.affected_tables,
            "affected_records_count": self.affected_records_count,
            "performed_by": self.performed_by,
            "ip_address": self.ip_address,
            "request_id": self.request_id,
            "details": self.details,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class DataRetentionPolicy(Base):
    """
    Data Retention Policy model.
    Defines automatic data cleanup rules.
    """
    __tablename__ = 'data_retention_policies'

    policy_id = Column(Integer, primary_key=True, autoincrement=True)
    table_name = Column(String(100), unique=True, nullable=False)
    retention_days = Column(Integer, nullable=False)
    action = Column(
        SQLEnum(RetentionActionEnum, name='retention_action_enum', create_type=False),
        nullable=False,
        default=RetentionActionEnum.delete
    )
    condition_column = Column(String(100), nullable=True)
    condition_value = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True)
    last_run_at = Column(DateTime(timezone=True), nullable=True)
    last_run_count = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "policy_id": self.policy_id,
            "table_name": self.table_name,
            "retention_days": self.retention_days,
            "action": self.action.value if self.action else None,
            "condition_column": self.condition_column,
            "condition_value": self.condition_value,
            "is_active": self.is_active,
            "last_run_at": self.last_run_at.isoformat() if self.last_run_at else None,
            "last_run_count": self.last_run_count,
        }
