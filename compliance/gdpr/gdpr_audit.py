"""
GDPR Audit Logger
ReviewSignal 5.0

Dedicated audit logging for GDPR compliance.
Creates immutable audit trail for all GDPR-related operations.
"""

import structlog
from datetime import datetime
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session

from .models import GDPRAuditLog, AuditActionEnum

logger = structlog.get_logger("gdpr.audit")


class GDPRAuditLogger:
    """
    GDPR-specific audit logger.
    Creates immutable audit trail entries for GDPR compliance.
    """

    def __init__(self, session: Session):
        """
        Initialize GDPR Audit Logger.

        Args:
            session: SQLAlchemy session for database operations
        """
        self.session = session

    def log(
        self,
        action: AuditActionEnum,
        subject_email: Optional[str] = None,
        affected_tables: Optional[List[str]] = None,
        affected_records_count: int = 0,
        performed_by: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        request_id: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> GDPRAuditLog:
        """
        Log a GDPR audit event.

        Args:
            action: Type of action performed
            subject_email: Email of data subject
            affected_tables: List of tables affected
            affected_records_count: Number of records affected
            performed_by: User/system that performed the action
            ip_address: Client IP address
            user_agent: Client user agent
            request_id: Related GDPR request ID
            details: Additional details as JSON

        Returns:
            Created GDPRAuditLog entry
        """
        audit_entry = GDPRAuditLog(
            action=action,
            subject_email=subject_email,
            affected_tables=affected_tables or [],
            affected_records_count=affected_records_count,
            performed_by=performed_by or "system",
            ip_address=ip_address,
            user_agent=user_agent,
            request_id=request_id,
            details=details or {}
        )

        self.session.add(audit_entry)
        self.session.commit()

        # Also log to structured logs
        logger.info(
            "gdpr_audit_event",
            action=action.value,
            subject_email=subject_email,
            affected_tables=affected_tables,
            affected_records_count=affected_records_count,
            performed_by=performed_by,
            request_id=request_id,
            details=details
        )

        return audit_entry

    def log_consent_granted(
        self,
        subject_email: str,
        consent_type: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> GDPRAuditLog:
        """Log consent granted event"""
        return self.log(
            action=AuditActionEnum.consent_granted,
            subject_email=subject_email,
            affected_tables=["gdpr_consents"],
            affected_records_count=1,
            ip_address=ip_address,
            user_agent=user_agent,
            details={"consent_type": consent_type}
        )

    def log_consent_withdrawn(
        self,
        subject_email: str,
        consent_type: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> GDPRAuditLog:
        """Log consent withdrawn event"""
        return self.log(
            action=AuditActionEnum.consent_withdrawn,
            subject_email=subject_email,
            affected_tables=["gdpr_consents"],
            affected_records_count=1,
            ip_address=ip_address,
            user_agent=user_agent,
            details={"consent_type": consent_type}
        )

    def log_data_exported(
        self,
        subject_email: str,
        tables: List[str],
        record_count: int,
        file_url: Optional[str] = None,
        request_id: Optional[int] = None,
        performed_by: Optional[str] = None,
        ip_address: Optional[str] = None
    ) -> GDPRAuditLog:
        """Log data export event"""
        return self.log(
            action=AuditActionEnum.data_exported,
            subject_email=subject_email,
            affected_tables=tables,
            affected_records_count=record_count,
            performed_by=performed_by,
            ip_address=ip_address,
            request_id=request_id,
            details={"file_url": file_url}
        )

    def log_data_deleted(
        self,
        subject_email: str,
        tables: List[str],
        record_count: int,
        request_id: Optional[int] = None,
        performed_by: Optional[str] = None,
        ip_address: Optional[str] = None,
        dry_run: bool = False
    ) -> GDPRAuditLog:
        """Log data deletion event"""
        return self.log(
            action=AuditActionEnum.data_deleted,
            subject_email=subject_email,
            affected_tables=tables,
            affected_records_count=record_count,
            performed_by=performed_by,
            ip_address=ip_address,
            request_id=request_id,
            details={"dry_run": dry_run}
        )

    def log_data_anonymized(
        self,
        subject_email: str,
        tables: List[str],
        record_count: int,
        request_id: Optional[int] = None,
        performed_by: Optional[str] = None
    ) -> GDPRAuditLog:
        """Log data anonymization event"""
        return self.log(
            action=AuditActionEnum.data_anonymized,
            subject_email=subject_email,
            affected_tables=tables,
            affected_records_count=record_count,
            performed_by=performed_by,
            request_id=request_id
        )

    def log_request_created(
        self,
        subject_email: str,
        request_type: str,
        request_id: int,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> GDPRAuditLog:
        """Log GDPR request creation"""
        return self.log(
            action=AuditActionEnum.request_created,
            subject_email=subject_email,
            affected_tables=["gdpr_requests"],
            affected_records_count=1,
            ip_address=ip_address,
            user_agent=user_agent,
            request_id=request_id,
            details={"request_type": request_type}
        )

    def log_request_completed(
        self,
        subject_email: str,
        request_id: int,
        performed_by: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> GDPRAuditLog:
        """Log GDPR request completion"""
        return self.log(
            action=AuditActionEnum.request_completed,
            subject_email=subject_email,
            affected_tables=["gdpr_requests"],
            affected_records_count=1,
            performed_by=performed_by,
            request_id=request_id,
            details=details or {}
        )

    def log_retention_cleanup(
        self,
        table_name: str,
        record_count: int,
        action: str,
        performed_by: str = "system"
    ) -> GDPRAuditLog:
        """Log retention policy cleanup"""
        return self.log(
            action=AuditActionEnum.retention_cleanup,
            affected_tables=[table_name],
            affected_records_count=record_count,
            performed_by=performed_by,
            details={"retention_action": action}
        )


def log_gdpr_action(
    session: Session,
    action: AuditActionEnum,
    subject_email: Optional[str] = None,
    affected_tables: Optional[List[str]] = None,
    affected_records_count: int = 0,
    performed_by: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    request_id: Optional[int] = None,
    details: Optional[Dict[str, Any]] = None
) -> GDPRAuditLog:
    """
    Convenience function to log a GDPR action.

    Args:
        session: SQLAlchemy session
        action: Type of action
        subject_email: Email of data subject
        affected_tables: Tables affected
        affected_records_count: Records affected
        performed_by: Actor
        ip_address: Client IP
        user_agent: Client user agent
        request_id: Related request ID
        details: Additional details

    Returns:
        Created audit log entry
    """
    audit_logger = GDPRAuditLogger(session)
    return audit_logger.log(
        action=action,
        subject_email=subject_email,
        affected_tables=affected_tables,
        affected_records_count=affected_records_count,
        performed_by=performed_by,
        ip_address=ip_address,
        user_agent=user_agent,
        request_id=request_id,
        details=details
    )
