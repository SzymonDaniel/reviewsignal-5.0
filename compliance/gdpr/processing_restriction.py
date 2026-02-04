"""
GDPR Processing Restriction Manager
ReviewSignal 5.0

Processing restriction support (Art. 18 GDPR).
Allows data subjects to restrict processing of their personal data.
"""

import structlog
from datetime import datetime
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from enum import Enum

import sys
sys.path.insert(0, '/home/info_betsim/reviewsignal-5.0')

from modules.database_schema import Base
from .models import AuditActionEnum
from .gdpr_audit import GDPRAuditLogger

logger = structlog.get_logger("gdpr.restriction")


class RestrictionReasonEnum(str, Enum):
    """Reasons for processing restriction per Art. 18"""
    accuracy_contested = "accuracy_contested"  # Subject contests accuracy
    unlawful_processing = "unlawful_processing"  # Processing is unlawful
    no_longer_needed = "no_longer_needed"  # Controller doesn't need data
    objection_pending = "objection_pending"  # Objection verification pending


class ProcessingRestriction(Base):
    """
    Processing restriction model.
    Tracks active restrictions on data processing.
    """
    __tablename__ = 'gdpr_processing_restrictions'

    restriction_id = Column(Integer, primary_key=True, autoincrement=True)
    subject_email = Column(String(255), nullable=False, index=True)
    reason = Column(String(50), nullable=False)
    reason_details = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    restricted_operations = Column(JSONB, default=["all"])  # ["all"] or specific ops
    restricted_tables = Column(JSONB, default=["all"])  # ["all"] or specific tables
    requested_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=True)
    lifted_at = Column(DateTime(timezone=True), nullable=True)
    lifted_by = Column(String(255), nullable=True)
    lift_reason = Column(Text, nullable=True)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)
    request_id = Column(Integer, nullable=True)  # Link to GDPR request
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "restriction_id": self.restriction_id,
            "subject_email": self.subject_email,
            "reason": self.reason,
            "reason_details": self.reason_details,
            "is_active": self.is_active,
            "restricted_operations": self.restricted_operations,
            "restricted_tables": self.restricted_tables,
            "requested_at": self.requested_at.isoformat() if self.requested_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "lifted_at": self.lifted_at.isoformat() if self.lifted_at else None,
            "lifted_by": self.lifted_by,
            "lift_reason": self.lift_reason,
        }

    def is_currently_active(self) -> bool:
        """Check if restriction is currently in effect"""
        if not self.is_active:
            return False
        if self.expires_at:
            expires = self.expires_at.replace(tzinfo=None) if self.expires_at.tzinfo else self.expires_at
            if expires < datetime.utcnow():
                return False
        return True


class ProcessingRestrictionManager:
    """
    Manages processing restrictions per GDPR Art. 18.
    """

    # Operations that can be restricted
    RESTRICTABLE_OPERATIONS = [
        "read",       # Reading/accessing data
        "update",     # Modifying data
        "delete",     # Deleting data (except for erasure request)
        "export",     # Exporting data
        "share",      # Sharing with third parties
        "process",    # General processing (analytics, ML, etc.)
        "marketing",  # Marketing communications
    ]

    # Tables containing personal data
    PERSONAL_DATA_TABLES = [
        "leads",
        "users",
        "gdpr_consents",
        "gdpr_requests",
        "outreach_log",
        "user_sessions"
    ]

    def __init__(self, session: Session):
        """
        Initialize Processing Restriction Manager.

        Args:
            session: SQLAlchemy session
        """
        self.session = session
        self.audit_logger = GDPRAuditLogger(session)

    def request_restriction(
        self,
        email: str,
        reason: str,
        reason_details: Optional[str] = None,
        restricted_operations: Optional[List[str]] = None,
        restricted_tables: Optional[List[str]] = None,
        expires_in_days: Optional[int] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        request_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Request processing restriction.

        Args:
            email: Subject's email
            reason: Reason for restriction (from RestrictionReasonEnum)
            reason_details: Additional details
            restricted_operations: List of operations to restrict (default: all)
            restricted_tables: List of tables to restrict (default: all)
            expires_in_days: Optional expiration
            ip_address: Client IP for audit
            user_agent: Client user agent
            request_id: Associated GDPR request ID

        Returns:
            Restriction details
        """
        email = email.lower().strip()

        # Validate reason
        try:
            reason_enum = RestrictionReasonEnum(reason)
        except ValueError:
            valid_reasons = [r.value for r in RestrictionReasonEnum]
            return {"error": f"Invalid reason. Valid reasons: {valid_reasons}"}

        # Validate operations
        if restricted_operations:
            invalid_ops = [op for op in restricted_operations if op not in self.RESTRICTABLE_OPERATIONS and op != "all"]
            if invalid_ops:
                return {"error": f"Invalid operations: {invalid_ops}. Valid: {self.RESTRICTABLE_OPERATIONS}"}
        else:
            restricted_operations = ["all"]

        # Validate tables
        if restricted_tables:
            invalid_tables = [t for t in restricted_tables if t not in self.PERSONAL_DATA_TABLES and t != "all"]
            if invalid_tables:
                return {"error": f"Invalid tables: {invalid_tables}. Valid: {self.PERSONAL_DATA_TABLES}"}
        else:
            restricted_tables = ["all"]

        # Check for existing active restriction
        existing = self.session.query(ProcessingRestriction).filter(
            ProcessingRestriction.subject_email == email,
            ProcessingRestriction.is_active == True
        ).first()

        if existing and existing.is_currently_active():
            return {
                "error": "Active restriction already exists",
                "existing_restriction_id": existing.restriction_id
            }

        # Calculate expiration
        expires_at = None
        if expires_in_days:
            from datetime import timedelta
            expires_at = datetime.utcnow() + timedelta(days=expires_in_days)

        # Create restriction
        restriction = ProcessingRestriction(
            subject_email=email,
            reason=reason,
            reason_details=reason_details,
            is_active=True,
            restricted_operations=restricted_operations,
            restricted_tables=restricted_tables,
            expires_at=expires_at,
            ip_address=ip_address,
            user_agent=user_agent,
            request_id=request_id
        )

        self.session.add(restriction)
        self.session.commit()

        # Audit log
        self.audit_logger.log(
            action=AuditActionEnum.policy_updated,
            subject_email=email,
            affected_tables=restricted_tables if restricted_tables != ["all"] else self.PERSONAL_DATA_TABLES,
            performed_by="subject_request",
            ip_address=ip_address,
            request_id=request_id,
            details={
                "operation": "processing_restriction_requested",
                "restriction_id": restriction.restriction_id,
                "reason": reason,
                "restricted_operations": restricted_operations,
                "restricted_tables": restricted_tables
            }
        )

        logger.info(
            "processing_restriction_requested",
            email=email,
            restriction_id=restriction.restriction_id,
            reason=reason
        )

        return restriction.to_dict()

    def lift_restriction(
        self,
        restriction_id: int,
        lifted_by: str,
        lift_reason: str,
        ip_address: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Lift a processing restriction.

        Args:
            restriction_id: Restriction ID to lift
            lifted_by: User lifting the restriction
            lift_reason: Reason for lifting

        Returns:
            Updated restriction
        """
        restriction = self.session.query(ProcessingRestriction).filter(
            ProcessingRestriction.restriction_id == restriction_id
        ).first()

        if not restriction:
            return {"error": f"Restriction not found: {restriction_id}"}

        if not restriction.is_active:
            return {"error": "Restriction is already inactive"}

        restriction.is_active = False
        restriction.lifted_at = datetime.utcnow()
        restriction.lifted_by = lifted_by
        restriction.lift_reason = lift_reason

        self.session.commit()

        # Audit log
        self.audit_logger.log(
            action=AuditActionEnum.policy_updated,
            subject_email=restriction.subject_email,
            performed_by=lifted_by,
            ip_address=ip_address,
            request_id=restriction.request_id,
            details={
                "operation": "processing_restriction_lifted",
                "restriction_id": restriction_id,
                "lift_reason": lift_reason
            }
        )

        logger.info(
            "processing_restriction_lifted",
            restriction_id=restriction_id,
            email=restriction.subject_email,
            lifted_by=lifted_by
        )

        return restriction.to_dict()

    def check_restriction(
        self,
        email: str,
        operation: Optional[str] = None,
        table: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Check if processing is restricted for a subject.

        Args:
            email: Subject's email
            operation: Specific operation to check
            table: Specific table to check

        Returns:
            Restriction status
        """
        email = email.lower().strip()

        restriction = self.session.query(ProcessingRestriction).filter(
            ProcessingRestriction.subject_email == email,
            ProcessingRestriction.is_active == True
        ).first()

        if not restriction or not restriction.is_currently_active():
            return {
                "email": email,
                "is_restricted": False,
                "restriction": None
            }

        # Check if specific operation/table is restricted
        is_operation_restricted = True
        is_table_restricted = True

        if operation:
            ops = restriction.restricted_operations
            is_operation_restricted = "all" in ops or operation in ops

        if table:
            tables = restriction.restricted_tables
            is_table_restricted = "all" in tables or table in tables

        return {
            "email": email,
            "is_restricted": is_operation_restricted and is_table_restricted,
            "restriction": restriction.to_dict() if restriction else None,
            "operation_check": {
                "operation": operation,
                "is_restricted": is_operation_restricted
            } if operation else None,
            "table_check": {
                "table": table,
                "is_restricted": is_table_restricted
            } if table else None
        }

    def get_active_restrictions(self, email: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get all active restrictions.

        Args:
            email: Optional filter by email

        Returns:
            List of active restrictions
        """
        query = self.session.query(ProcessingRestriction).filter(
            ProcessingRestriction.is_active == True
        )

        if email:
            query = query.filter(ProcessingRestriction.subject_email == email.lower().strip())

        restrictions = query.all()

        # Filter out expired ones
        active = [r for r in restrictions if r.is_currently_active()]

        return [r.to_dict() for r in active]

    def get_restriction_history(
        self,
        email: str,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Get restriction history for a subject.

        Args:
            email: Subject's email
            limit: Max results

        Returns:
            List of restrictions (active and lifted)
        """
        email = email.lower().strip()

        restrictions = self.session.query(ProcessingRestriction).filter(
            ProcessingRestriction.subject_email == email
        ).order_by(ProcessingRestriction.created_at.desc()).limit(limit).all()

        return [r.to_dict() for r in restrictions]

    def expire_old_restrictions(self) -> int:
        """
        Deactivate expired restrictions.

        Returns:
            Number of restrictions expired
        """
        now = datetime.utcnow()

        expired = self.session.query(ProcessingRestriction).filter(
            ProcessingRestriction.is_active == True,
            ProcessingRestriction.expires_at.isnot(None),
            ProcessingRestriction.expires_at < now
        ).all()

        count = 0
        for restriction in expired:
            restriction.is_active = False
            restriction.lifted_at = now
            restriction.lifted_by = "system"
            restriction.lift_reason = "Automatic expiration"

            self.audit_logger.log(
                action=AuditActionEnum.policy_updated,
                subject_email=restriction.subject_email,
                performed_by="system",
                details={
                    "operation": "processing_restriction_expired",
                    "restriction_id": restriction.restriction_id
                }
            )
            count += 1

        self.session.commit()

        if count > 0:
            logger.info("restrictions_expired", count=count)

        return count


def is_processing_allowed(
    session: Session,
    email: str,
    operation: str,
    table: Optional[str] = None
) -> bool:
    """
    Helper function to check if processing is allowed for a subject.

    Args:
        session: SQLAlchemy session
        email: Subject's email
        operation: Operation to perform
        table: Table to access

    Returns:
        True if allowed, False if restricted
    """
    manager = ProcessingRestrictionManager(session)
    result = manager.check_restriction(email, operation, table)
    return not result.get("is_restricted", False)
