"""
GDPR Consent Manager
ReviewSignal 5.0

Manages consent collection, storage, and withdrawal (Art. 7 GDPR).
"""

import structlog
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from sqlalchemy import and_

from .models import (
    GDPRConsent, ConsentTypeEnum, ConsentStatusEnum, AuditActionEnum
)
from .gdpr_audit import GDPRAuditLogger

logger = structlog.get_logger("gdpr.consent")


class ConsentManager:
    """
    Manages GDPR consent for data subjects.
    """

    # Default consent expiration (2 years)
    DEFAULT_CONSENT_EXPIRY_DAYS = 730

    def __init__(self, session: Session):
        """
        Initialize Consent Manager.

        Args:
            session: SQLAlchemy session
        """
        self.session = session
        self.audit_logger = GDPRAuditLogger(session)

    def grant_consent(
        self,
        email: str,
        consent_type: ConsentTypeEnum,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        expires_in_days: Optional[int] = None,
        consent_text: Optional[str] = None,
        consent_version: str = "1.0"
    ) -> Dict[str, Any]:
        """
        Grant consent for a specific type.

        Args:
            email: Subject's email
            consent_type: Type of consent
            ip_address: Client IP for audit
            user_agent: Client user agent for audit
            expires_in_days: Days until consent expires
            consent_text: Text of consent agreement
            consent_version: Version of consent form

        Returns:
            Dict with consent details
        """
        email = email.lower().strip()

        # Calculate expiration
        expires_at = None
        if expires_in_days:
            expires_at = datetime.utcnow() + timedelta(days=expires_in_days)
        elif self.DEFAULT_CONSENT_EXPIRY_DAYS:
            expires_at = datetime.utcnow() + timedelta(days=self.DEFAULT_CONSENT_EXPIRY_DAYS)

        # Check for existing consent
        existing = self.session.query(GDPRConsent).filter(
            and_(
                GDPRConsent.subject_email == email,
                GDPRConsent.consent_type == consent_type
            )
        ).first()

        if existing:
            # Update existing consent
            existing.status = ConsentStatusEnum.granted
            existing.granted_at = datetime.utcnow()
            existing.withdrawn_at = None
            existing.expires_at = expires_at
            existing.ip_address = ip_address
            existing.user_agent = user_agent
            existing.consent_text = consent_text
            existing.consent_version = consent_version
            consent = existing
        else:
            # Create new consent
            consent = GDPRConsent(
                subject_email=email,
                consent_type=consent_type,
                status=ConsentStatusEnum.granted,
                granted_at=datetime.utcnow(),
                expires_at=expires_at,
                ip_address=ip_address,
                user_agent=user_agent,
                consent_text=consent_text,
                consent_version=consent_version
            )
            self.session.add(consent)

        self.session.commit()

        # Audit log
        self.audit_logger.log_consent_granted(
            subject_email=email,
            consent_type=consent_type.value,
            ip_address=ip_address,
            user_agent=user_agent
        )

        logger.info(
            "consent_granted",
            email=email,
            consent_type=consent_type.value,
            expires_at=expires_at.isoformat() if expires_at else None
        )

        return consent.to_dict()

    def withdraw_consent(
        self,
        email: str,
        consent_type: ConsentTypeEnum,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Withdraw consent for a specific type.

        Args:
            email: Subject's email
            consent_type: Type of consent to withdraw
            ip_address: Client IP for audit
            user_agent: Client user agent for audit

        Returns:
            Dict with result
        """
        email = email.lower().strip()

        consent = self.session.query(GDPRConsent).filter(
            and_(
                GDPRConsent.subject_email == email,
                GDPRConsent.consent_type == consent_type,
                GDPRConsent.status == ConsentStatusEnum.granted
            )
        ).first()

        if not consent:
            return {
                "success": False,
                "message": f"No active consent found for {consent_type.value}"
            }

        consent.status = ConsentStatusEnum.withdrawn
        consent.withdrawn_at = datetime.utcnow()
        self.session.commit()

        # Audit log
        self.audit_logger.log_consent_withdrawn(
            subject_email=email,
            consent_type=consent_type.value,
            ip_address=ip_address,
            user_agent=user_agent
        )

        logger.info(
            "consent_withdrawn",
            email=email,
            consent_type=consent_type.value
        )

        return {
            "success": True,
            "message": f"Consent for {consent_type.value} has been withdrawn",
            "withdrawn_at": consent.withdrawn_at.isoformat()
        }

    def withdraw_all_consents(
        self,
        email: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Withdraw all consents for a subject.

        Args:
            email: Subject's email
            ip_address: Client IP for audit
            user_agent: Client user agent for audit

        Returns:
            Dict with result
        """
        email = email.lower().strip()

        consents = self.session.query(GDPRConsent).filter(
            and_(
                GDPRConsent.subject_email == email,
                GDPRConsent.status == ConsentStatusEnum.granted
            )
        ).all()

        withdrawn_count = 0
        for consent in consents:
            consent.status = ConsentStatusEnum.withdrawn
            consent.withdrawn_at = datetime.utcnow()
            withdrawn_count += 1

            # Audit log each
            self.audit_logger.log_consent_withdrawn(
                subject_email=email,
                consent_type=consent.consent_type.value,
                ip_address=ip_address,
                user_agent=user_agent
            )

        self.session.commit()

        logger.info(
            "all_consents_withdrawn",
            email=email,
            count=withdrawn_count
        )

        return {
            "success": True,
            "message": f"Withdrawn {withdrawn_count} consent(s)",
            "withdrawn_count": withdrawn_count
        }

    def check_consent(
        self,
        email: str,
        consent_type: ConsentTypeEnum
    ) -> bool:
        """
        Check if a specific consent is currently valid.

        Args:
            email: Subject's email
            consent_type: Type of consent to check

        Returns:
            True if consent is valid, False otherwise
        """
        email = email.lower().strip()

        consent = self.session.query(GDPRConsent).filter(
            and_(
                GDPRConsent.subject_email == email,
                GDPRConsent.consent_type == consent_type,
                GDPRConsent.status == ConsentStatusEnum.granted
            )
        ).first()

        if not consent:
            return False

        return consent.is_valid()

    def get_consent_status(
        self,
        email: str
    ) -> Dict[str, Any]:
        """
        Get all consent statuses for a subject.

        Args:
            email: Subject's email

        Returns:
            Dict with consent statuses for each type
        """
        email = email.lower().strip()

        consents = self.session.query(GDPRConsent).filter(
            GDPRConsent.subject_email == email
        ).all()

        status = {}
        for consent_type in ConsentTypeEnum:
            consent = next(
                (c for c in consents if c.consent_type == consent_type),
                None
            )
            if consent:
                status[consent_type.value] = {
                    "status": consent.status.value,
                    "is_valid": consent.is_valid(),
                    "granted_at": consent.granted_at.isoformat() if consent.granted_at else None,
                    "expires_at": consent.expires_at.isoformat() if consent.expires_at else None,
                    "withdrawn_at": consent.withdrawn_at.isoformat() if consent.withdrawn_at else None,
                    "version": consent.consent_version
                }
            else:
                status[consent_type.value] = {
                    "status": "not_given",
                    "is_valid": False,
                    "granted_at": None,
                    "expires_at": None,
                    "withdrawn_at": None,
                    "version": None
                }

        return {
            "email": email,
            "consents": status,
            "has_any_valid_consent": any(
                s["is_valid"] for s in status.values()
            )
        }

    def expire_old_consents(self) -> int:
        """
        Expire consents that have passed their expiration date.

        Returns:
            Number of consents expired
        """
        now = datetime.utcnow()

        expired_consents = self.session.query(GDPRConsent).filter(
            and_(
                GDPRConsent.status == ConsentStatusEnum.granted,
                GDPRConsent.expires_at.isnot(None),
                GDPRConsent.expires_at < now
            )
        ).all()

        count = 0
        for consent in expired_consents:
            consent.status = ConsentStatusEnum.expired

            # Audit log
            self.audit_logger.log(
                action=AuditActionEnum.consent_expired,
                subject_email=consent.subject_email,
                affected_tables=["gdpr_consents"],
                affected_records_count=1,
                performed_by="system",
                details={"consent_type": consent.consent_type.value}
            )
            count += 1

        self.session.commit()

        if count > 0:
            logger.info("consents_expired", count=count)

        return count

    def get_subjects_with_consent(
        self,
        consent_type: ConsentTypeEnum
    ) -> List[str]:
        """
        Get list of emails that have valid consent for a type.

        Args:
            consent_type: Type of consent

        Returns:
            List of email addresses
        """
        now = datetime.utcnow()

        consents = self.session.query(GDPRConsent.subject_email).filter(
            and_(
                GDPRConsent.consent_type == consent_type,
                GDPRConsent.status == ConsentStatusEnum.granted,
                (GDPRConsent.expires_at.is_(None) | (GDPRConsent.expires_at > now))
            )
        ).all()

        return [c.subject_email for c in consents]
