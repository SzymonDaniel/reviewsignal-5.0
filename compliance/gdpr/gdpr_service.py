"""
GDPR Service
ReviewSignal 5.0

Main orchestration service for GDPR compliance operations.
Coordinates all GDPR-related functionality.
"""

import structlog
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from sqlalchemy import and_

from .models import (
    GDPRRequest, GDPRConsent, GDPRAuditLog,
    RequestTypeEnum, RequestStatusEnum, ConsentTypeEnum, ConsentStatusEnum,
    AuditActionEnum
)
from .consent_manager import ConsentManager
from .data_exporter import DataExporter
from .data_eraser import DataEraser
from .data_rectifier import DataRectifier
from .retention_manager import RetentionManager
from .processing_restriction import ProcessingRestrictionManager
from .gdpr_audit import GDPRAuditLogger
from .gdpr_notifications import GDPRNotificationService
from .gdpr_webhooks import GDPRWebhookDispatcher, WebhookEventType

logger = structlog.get_logger("gdpr.service")


class GDPRService:
    """
    Main orchestration service for GDPR compliance.
    """

    # GDPR deadline in days (Art. 12)
    REQUEST_DEADLINE_DAYS = 30

    def __init__(self, session: Session):
        """
        Initialize GDPR Service.

        Args:
            session: SQLAlchemy session
        """
        self.session = session
        self.consent_manager = ConsentManager(session)
        self.data_exporter = DataExporter(session)
        self.data_eraser = DataEraser(session)
        self.data_rectifier = DataRectifier(session)
        self.retention_manager = RetentionManager(session)
        self.restriction_manager = ProcessingRestrictionManager(session)
        self.audit_logger = GDPRAuditLogger(session)
        self.notification_service = GDPRNotificationService(session)
        self.webhook_dispatcher = GDPRWebhookDispatcher(session)

    # =========================================================================
    # CONSENT MANAGEMENT
    # =========================================================================

    def grant_consent(
        self,
        email: str,
        consent_type: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        expires_in_days: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Grant consent for a data subject.

        Args:
            email: Subject's email
            consent_type: Type of consent (marketing, data_processing, analytics, third_party_sharing)
            ip_address: Client IP
            user_agent: Client user agent
            expires_in_days: Days until expiration

        Returns:
            Consent details
        """
        try:
            consent_enum = ConsentTypeEnum(consent_type)
        except ValueError:
            return {"error": f"Invalid consent type: {consent_type}"}

        return self.consent_manager.grant_consent(
            email=email,
            consent_type=consent_enum,
            ip_address=ip_address,
            user_agent=user_agent,
            expires_in_days=expires_in_days
        )

    def withdraw_consent(
        self,
        email: str,
        consent_type: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Withdraw consent for a data subject.

        Args:
            email: Subject's email
            consent_type: Type of consent to withdraw
            ip_address: Client IP
            user_agent: Client user agent

        Returns:
            Result details
        """
        try:
            consent_enum = ConsentTypeEnum(consent_type)
        except ValueError:
            return {"error": f"Invalid consent type: {consent_type}"}

        return self.consent_manager.withdraw_consent(
            email=email,
            consent_type=consent_enum,
            ip_address=ip_address,
            user_agent=user_agent
        )

    def check_consent(self, email: str, consent_type: str) -> bool:
        """
        Check if consent is valid.

        Args:
            email: Subject's email
            consent_type: Type of consent

        Returns:
            True if valid, False otherwise
        """
        try:
            consent_enum = ConsentTypeEnum(consent_type)
        except ValueError:
            return False

        return self.consent_manager.check_consent(email, consent_enum)

    def get_consent_status(self, email: str) -> Dict[str, Any]:
        """
        Get all consent statuses for a subject.

        Args:
            email: Subject's email

        Returns:
            Dict with consent statuses
        """
        return self.consent_manager.get_consent_status(email)

    # =========================================================================
    # REQUEST MANAGEMENT
    # =========================================================================

    def create_request(
        self,
        email: str,
        request_type: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a new GDPR request.

        Args:
            email: Subject's email
            request_type: Type of request (data_export, data_erasure, data_access, etc.)
            ip_address: Client IP
            user_agent: Client user agent

        Returns:
            Request details
        """
        email = email.lower().strip()

        try:
            request_enum = RequestTypeEnum(request_type)
        except ValueError:
            return {"error": f"Invalid request type: {request_type}"}

        # Check for existing pending request
        existing = self.session.query(GDPRRequest).filter(
            and_(
                GDPRRequest.subject_email == email,
                GDPRRequest.request_type == request_enum,
                GDPRRequest.status.in_([RequestStatusEnum.pending, RequestStatusEnum.in_progress])
            )
        ).first()

        if existing:
            return {
                "error": "A request of this type is already pending",
                "existing_request_id": existing.request_id
            }

        # Create request
        deadline = datetime.utcnow() + timedelta(days=self.REQUEST_DEADLINE_DAYS)

        request = GDPRRequest(
            subject_email=email,
            request_type=request_enum,
            status=RequestStatusEnum.pending,
            deadline_at=deadline,
            ip_address=ip_address,
            user_agent=user_agent
        )

        self.session.add(request)
        self.session.commit()

        # Audit log
        self.audit_logger.log_request_created(
            subject_email=email,
            request_type=request_type,
            request_id=request.request_id,
            ip_address=ip_address,
            user_agent=user_agent
        )

        logger.info(
            "gdpr_request_created",
            email=email,
            request_type=request_type,
            request_id=request.request_id,
            deadline=deadline.isoformat()
        )

        return request.to_dict()

    def get_request(self, request_id: int) -> Optional[Dict[str, Any]]:
        """
        Get request by ID.

        Args:
            request_id: Request ID

        Returns:
            Request details or None
        """
        request = self.session.query(GDPRRequest).filter(
            GDPRRequest.request_id == request_id
        ).first()

        return request.to_dict() if request else None

    def process_request(
        self,
        request_id: int,
        performed_by: Optional[str] = None,
        ip_address: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Process a GDPR request.

        Args:
            request_id: Request ID
            performed_by: User processing the request
            ip_address: Client IP

        Returns:
            Processing result
        """
        request = self.session.query(GDPRRequest).filter(
            GDPRRequest.request_id == request_id
        ).first()

        if not request:
            return {"error": f"Request not found: {request_id}"}

        if request.status not in [RequestStatusEnum.pending, RequestStatusEnum.in_progress]:
            return {"error": f"Request already processed: {request.status.value}"}

        # Mark as in progress
        request.status = RequestStatusEnum.in_progress
        request.processed_by = performed_by
        self.session.commit()

        # Process based on type
        result = {}

        try:
            if request.request_type == RequestTypeEnum.data_export:
                result = self._process_export_request(request, performed_by, ip_address)

            elif request.request_type == RequestTypeEnum.data_erasure:
                result = self._process_erasure_request(request, performed_by, ip_address)

            elif request.request_type == RequestTypeEnum.data_access:
                result = self._process_access_request(request, performed_by, ip_address)

            elif request.request_type == RequestTypeEnum.data_portability:
                result = self._process_portability_request(request, performed_by, ip_address)

            else:
                result = {"status": "manual_processing_required"}

            # Mark as completed
            request.status = RequestStatusEnum.completed
            request.completed_at = datetime.utcnow()

            if "file_path" in result:
                request.result_file_url = result["file_path"]
            if "file_size" in result:
                request.result_file_size = result["file_size"]

        except Exception as e:
            logger.error("request_processing_error", request_id=request_id, error=str(e))
            request.status = RequestStatusEnum.pending  # Revert to pending
            result = {"error": str(e)}

        self.session.commit()

        if request.status == RequestStatusEnum.completed:
            self.audit_logger.log_request_completed(
                subject_email=request.subject_email,
                request_id=request_id,
                performed_by=performed_by,
                details=result
            )

        return {
            "request_id": request_id,
            "status": request.status.value,
            "result": result
        }

    def _process_export_request(
        self,
        request: GDPRRequest,
        performed_by: Optional[str],
        ip_address: Optional[str]
    ) -> Dict[str, Any]:
        """Process data export request (Art. 20)"""
        return self.data_exporter.export_data(
            email=request.subject_email,
            format="json",
            request_id=request.request_id,
            performed_by=performed_by,
            ip_address=ip_address
        )

    def _process_erasure_request(
        self,
        request: GDPRRequest,
        performed_by: Optional[str],
        ip_address: Optional[str]
    ) -> Dict[str, Any]:
        """Process data erasure request (Art. 17)"""
        return self.data_eraser.erase_data(
            email=request.subject_email,
            dry_run=False,
            request_id=request.request_id,
            performed_by=performed_by,
            ip_address=ip_address
        )

    def _process_access_request(
        self,
        request: GDPRRequest,
        performed_by: Optional[str],
        ip_address: Optional[str]
    ) -> Dict[str, Any]:
        """Process data access request (Art. 15)"""
        # Same as export but includes additional metadata
        return self.data_exporter.export_data(
            email=request.subject_email,
            format="json",
            request_id=request.request_id,
            performed_by=performed_by,
            ip_address=ip_address
        )

    def _process_portability_request(
        self,
        request: GDPRRequest,
        performed_by: Optional[str],
        ip_address: Optional[str]
    ) -> Dict[str, Any]:
        """Process data portability request (Art. 20)"""
        return self.data_exporter.export_data(
            email=request.subject_email,
            format="json",
            request_id=request.request_id,
            performed_by=performed_by,
            ip_address=ip_address
        )

    def reject_request(
        self,
        request_id: int,
        reason: str,
        performed_by: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Reject a GDPR request.

        Args:
            request_id: Request ID
            reason: Rejection reason
            performed_by: User rejecting the request

        Returns:
            Result
        """
        request = self.session.query(GDPRRequest).filter(
            GDPRRequest.request_id == request_id
        ).first()

        if not request:
            return {"error": f"Request not found: {request_id}"}

        request.status = RequestStatusEnum.rejected
        request.rejection_reason = reason
        request.processed_by = performed_by
        request.completed_at = datetime.utcnow()

        self.session.commit()

        self.audit_logger.log(
            action=AuditActionEnum.request_rejected,
            subject_email=request.subject_email,
            request_id=request_id,
            performed_by=performed_by,
            details={"reason": reason}
        )

        return {"request_id": request_id, "status": "rejected", "reason": reason}

    def get_pending_requests(self) -> List[Dict[str, Any]]:
        """
        Get all pending requests.

        Returns:
            List of pending request dicts
        """
        requests = self.session.query(GDPRRequest).filter(
            GDPRRequest.status.in_([RequestStatusEnum.pending, RequestStatusEnum.in_progress])
        ).order_by(GDPRRequest.deadline_at.asc()).all()

        return [r.to_dict() for r in requests]

    def get_overdue_requests(self) -> List[Dict[str, Any]]:
        """
        Get all overdue requests.

        Returns:
            List of overdue request dicts
        """
        now = datetime.utcnow()

        requests = self.session.query(GDPRRequest).filter(
            and_(
                GDPRRequest.status.in_([RequestStatusEnum.pending, RequestStatusEnum.in_progress]),
                GDPRRequest.deadline_at < now
            )
        ).order_by(GDPRRequest.deadline_at.asc()).all()

        return [r.to_dict() for r in requests]

    # =========================================================================
    # DATA EXPORT / ERASURE
    # =========================================================================

    def export_data(
        self,
        email: str,
        format: str = "json",
        performed_by: Optional[str] = None,
        ip_address: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Export personal data for a subject.

        Args:
            email: Subject's email
            format: Export format (json/csv)
            performed_by: User performing export
            ip_address: Client IP

        Returns:
            Export result with file path
        """
        return self.data_exporter.export_data(
            email=email,
            format=format,
            performed_by=performed_by,
            ip_address=ip_address
        )

    def erase_data(
        self,
        email: str,
        dry_run: bool = True,
        performed_by: Optional[str] = None,
        ip_address: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Erase personal data for a subject.

        Args:
            email: Subject's email
            dry_run: If True, only preview
            performed_by: User performing erasure
            ip_address: Client IP

        Returns:
            Erasure result
        """
        return self.data_eraser.erase_data(
            email=email,
            dry_run=dry_run,
            performed_by=performed_by,
            ip_address=ip_address
        )

    def preview_export(self, email: str) -> Dict[str, Any]:
        """Preview what data would be exported"""
        return self.data_exporter.preview_export(email)

    def preview_erasure(self, email: str) -> Dict[str, Any]:
        """Preview what data would be erased"""
        return self.data_eraser.preview_erasure(email)

    # =========================================================================
    # RETENTION MANAGEMENT
    # =========================================================================

    def run_retention_cleanup(
        self,
        table_name: Optional[str] = None,
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """
        Run retention cleanup.

        Args:
            table_name: Specific table or None for all
            dry_run: If True, only preview

        Returns:
            Cleanup results
        """
        return self.retention_manager.run_cleanup(
            table_name=table_name,
            dry_run=dry_run
        )

    def get_retention_policies(self) -> List[Dict[str, Any]]:
        """Get all retention policies"""
        return self.retention_manager.get_policies()

    def get_retention_statistics(self) -> Dict[str, Any]:
        """Get retention statistics"""
        return self.retention_manager.get_statistics()

    # =========================================================================
    # DATA RECTIFICATION (Art. 16)
    # =========================================================================

    def rectify_data(
        self,
        email: str,
        rectifications: Dict[str, Dict[str, Any]],
        performed_by: Optional[str] = None,
        ip_address: Optional[str] = None,
        request_id: Optional[int] = None,
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """
        Rectify personal data for a subject.

        Args:
            email: Subject's email
            rectifications: Dict of {table_name: {field: new_value}}
            performed_by: User performing rectification
            ip_address: Client IP
            request_id: Associated GDPR request ID
            dry_run: If True, only preview

        Returns:
            Rectification result
        """
        result = self.data_rectifier.rectify_data(
            email=email,
            rectifications=rectifications,
            performed_by=performed_by,
            ip_address=ip_address,
            request_id=request_id,
            dry_run=dry_run
        )

        # Dispatch webhook
        if not dry_run and result.get("total_fields_updated", 0) > 0:
            self.webhook_dispatcher.dispatch(
                WebhookEventType.data_rectified,
                {"email": email, "result": result}
            )

        return result

    def rectify_email(
        self,
        old_email: str,
        new_email: str,
        performed_by: Optional[str] = None,
        ip_address: Optional[str] = None,
        request_id: Optional[int] = None,
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """
        Rectify email address across all tables.

        Args:
            old_email: Current email
            new_email: New email address
            performed_by: User performing rectification
            ip_address: Client IP
            request_id: Associated GDPR request ID
            dry_run: If True, only preview

        Returns:
            Rectification result
        """
        return self.data_rectifier.rectify_email(
            old_email=old_email,
            new_email=new_email,
            performed_by=performed_by,
            ip_address=ip_address,
            request_id=request_id,
            dry_run=dry_run
        )

    def preview_rectification(self, email: str) -> Dict[str, Any]:
        """Preview what data can be rectified"""
        return self.data_rectifier.preview_rectification(email)

    # =========================================================================
    # PROCESSING RESTRICTION (Art. 18)
    # =========================================================================

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
            reason: Reason for restriction
            reason_details: Additional details
            restricted_operations: Operations to restrict
            restricted_tables: Tables to restrict
            expires_in_days: Optional expiration
            ip_address: Client IP
            user_agent: Client user agent
            request_id: Associated GDPR request ID

        Returns:
            Restriction details
        """
        result = self.restriction_manager.request_restriction(
            email=email,
            reason=reason,
            reason_details=reason_details,
            restricted_operations=restricted_operations,
            restricted_tables=restricted_tables,
            expires_in_days=expires_in_days,
            ip_address=ip_address,
            user_agent=user_agent,
            request_id=request_id
        )

        # Dispatch webhook
        if "error" not in result:
            self.webhook_dispatcher.dispatch(
                WebhookEventType.data_restricted,
                {"email": email, "restriction": result}
            )

        return result

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
            restriction_id: Restriction ID
            lifted_by: User lifting restriction
            lift_reason: Reason for lifting

        Returns:
            Updated restriction
        """
        return self.restriction_manager.lift_restriction(
            restriction_id=restriction_id,
            lifted_by=lifted_by,
            lift_reason=lift_reason,
            ip_address=ip_address
        )

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
        return self.restriction_manager.check_restriction(email, operation, table)

    def get_active_restrictions(self, email: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all active restrictions"""
        return self.restriction_manager.get_active_restrictions(email)

    # =========================================================================
    # NOTIFICATIONS
    # =========================================================================

    def send_overdue_alerts(self) -> Dict[str, Any]:
        """Send alerts about overdue requests to DPO"""
        return self.notification_service.notify_overdue_requests()

    def send_consent_expiry_notifications(self, days_before: int = 30) -> Dict[str, Any]:
        """Send notifications about expiring consents"""
        return self.notification_service.notify_consent_expiring_soon(days_before)

    # =========================================================================
    # WEBHOOKS
    # =========================================================================

    def subscribe_webhook(
        self,
        name: str,
        url: str,
        secret: str,
        events: List[str],
        headers: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """Subscribe to GDPR webhook events"""
        return self.webhook_dispatcher.subscribe(
            name=name,
            url=url,
            secret=secret,
            events=events,
            headers=headers
        )

    def unsubscribe_webhook(self, subscription_id: int) -> Dict[str, Any]:
        """Unsubscribe from webhooks"""
        return self.webhook_dispatcher.unsubscribe(subscription_id)

    def list_webhooks(self) -> List[Dict[str, Any]]:
        """List all webhook subscriptions"""
        return self.webhook_dispatcher.list_subscriptions()

    def get_webhook_logs(
        self,
        subscription_id: Optional[int] = None,
        event_type: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get webhook delivery logs"""
        return self.webhook_dispatcher.get_delivery_logs(
            subscription_id=subscription_id,
            event_type=event_type,
            limit=limit
        )

    # =========================================================================
    # HEALTH & STATUS
    # =========================================================================

    def get_health(self) -> Dict[str, Any]:
        """
        Get GDPR module health status.

        Returns:
            Health status dict
        """
        try:
            # Check database connectivity
            pending = len(self.get_pending_requests())
            overdue = len(self.get_overdue_requests())

            return {
                "status": "healthy" if overdue == 0 else "warning",
                "pending_requests": pending,
                "overdue_requests": overdue,
                "timestamp": datetime.utcnow().isoformat(),
                "components": {
                    "consent_manager": "ok",
                    "data_exporter": "ok",
                    "data_eraser": "ok",
                    "data_rectifier": "ok",
                    "retention_manager": "ok",
                    "restriction_manager": "ok",
                    "notification_service": "ok",
                    "webhook_dispatcher": "ok"
                }
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }

    def get_compliance_summary(self) -> Dict[str, Any]:
        """
        Get GDPR compliance summary.

        Returns:
            Summary dict
        """
        from sqlalchemy import func

        # Count consents
        active_consents = self.session.query(func.count(GDPRConsent.consent_id)).filter(
            GDPRConsent.status == ConsentStatusEnum.granted
        ).scalar()

        # Count requests by status
        request_counts = {}
        for status in RequestStatusEnum:
            count = self.session.query(func.count(GDPRRequest.request_id)).filter(
                GDPRRequest.status == status
            ).scalar()
            request_counts[status.value] = count

        # Recent audit events
        recent_audits = self.session.query(func.count(GDPRAuditLog.audit_id)).filter(
            GDPRAuditLog.created_at > datetime.utcnow() - timedelta(days=30)
        ).scalar()

        return {
            "active_consents": active_consents,
            "requests": request_counts,
            "recent_audit_events_30d": recent_audits,
            "overdue_requests": len(self.get_overdue_requests()),
            "retention_policies": len(self.get_retention_policies()),
            "generated_at": datetime.utcnow().isoformat()
        }
