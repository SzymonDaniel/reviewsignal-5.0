#!/usr/bin/env python3
"""
Audit Logger Module
Tracks all data access and API calls for compliance and security
"""

import structlog
from datetime import datetime
from typing import Optional, Dict, Any, List
from enum import Enum
import json


class AuditEventType(Enum):
    """Types of audit events"""
    DATA_ACCESS = "data_access"
    DATA_EXPORT = "data_export"
    API_CALL = "api_call"
    USER_LOGIN = "user_login"
    USER_LOGOUT = "user_logout"
    PERMISSION_CHANGE = "permission_change"
    DATA_SCRAPE = "data_scrape"
    RATE_LIMIT_HIT = "rate_limit_hit"
    ERROR = "error"
    # GDPR-specific event types
    GDPR_CONSENT_GRANTED = "gdpr_consent_granted"
    GDPR_CONSENT_WITHDRAWN = "gdpr_consent_withdrawn"
    GDPR_CONSENT_EXPIRED = "gdpr_consent_expired"
    GDPR_DATA_EXPORTED = "gdpr_data_exported"
    GDPR_DATA_DELETED = "gdpr_data_deleted"
    GDPR_DATA_ANONYMIZED = "gdpr_data_anonymized"
    GDPR_REQUEST_CREATED = "gdpr_request_created"
    GDPR_REQUEST_PROCESSED = "gdpr_request_processed"
    GDPR_REQUEST_COMPLETED = "gdpr_request_completed"
    GDPR_REQUEST_REJECTED = "gdpr_request_rejected"
    GDPR_RETENTION_CLEANUP = "gdpr_retention_cleanup"
    GDPR_POLICY_UPDATED = "gdpr_policy_updated"


class AuditLogger:
    """
    Centralized audit logging for compliance
    Logs all data access, API calls, and security events
    """

    def __init__(self, log_to_db: bool = False):
        """
        Initialize audit logger

        Args:
            log_to_db: If True, also log to database (not just files)
        """
        self.logger = structlog.get_logger("audit")
        self.log_to_db = log_to_db

    def log_event(
        self,
        event_type: AuditEventType,
        user_id: Optional[str] = None,
        endpoint: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_ids: Optional[List[str]] = None,
        action: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        status_code: Optional[int] = None,
        error_message: Optional[str] = None,
        additional_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Log an audit event

        Args:
            event_type: Type of event
            user_id: User who performed action (if authenticated)
            endpoint: API endpoint accessed
            resource_type: Type of resource (location, review, lead, etc.)
            resource_ids: IDs of resources accessed
            action: Action performed (read, write, delete, etc.)
            ip_address: Client IP address
            user_agent: Client user agent
            status_code: HTTP status code
            error_message: Error message if applicable
            additional_data: Any additional context

        Returns:
            The logged audit event
        """
        event = {
            "event_type": event_type.value,
            "timestamp": datetime.utcnow().isoformat(),
            "user_id": user_id or "anonymous",
            "endpoint": endpoint,
            "resource_type": resource_type,
            "resource_ids": resource_ids or [],
            "action": action,
            "ip_address": ip_address,
            "user_agent": user_agent,
            "status_code": status_code,
            "error_message": error_message,
        }

        if additional_data:
            event["additional_data"] = additional_data

        # Log to structured logs
        self.logger.info(
            "audit_event",
            **event
        )

        # TODO: If log_to_db, also save to audit_log table in PostgreSQL
        # This allows querying audit logs from API/dashboard

        return event

    def log_api_call(
        self,
        endpoint: str,
        method: str,
        user_id: Optional[str] = None,
        status_code: Optional[int] = None,
        duration_ms: Optional[float] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        request_body: Optional[Dict] = None,
        response_size: Optional[int] = None
    ):
        """Log API call"""
        return self.log_event(
            event_type=AuditEventType.API_CALL,
            user_id=user_id,
            endpoint=endpoint,
            action=method,
            ip_address=ip_address,
            user_agent=user_agent,
            status_code=status_code,
            additional_data={
                "duration_ms": duration_ms,
                "request_body": request_body,
                "response_size": response_size,
            }
        )

    def log_data_access(
        self,
        user_id: str,
        resource_type: str,
        resource_ids: List[str],
        action: str = "read",
        endpoint: Optional[str] = None,
        ip_address: Optional[str] = None
    ):
        """Log data access (locations, reviews, leads, etc.)"""
        return self.log_event(
            event_type=AuditEventType.DATA_ACCESS,
            user_id=user_id,
            endpoint=endpoint,
            resource_type=resource_type,
            resource_ids=resource_ids,
            action=action,
            ip_address=ip_address
        )

    def log_data_export(
        self,
        user_id: str,
        resource_type: str,
        record_count: int,
        export_format: str = "json",
        ip_address: Optional[str] = None
    ):
        """Log data export (CSV, JSON, etc.)"""
        return self.log_event(
            event_type=AuditEventType.DATA_EXPORT,
            user_id=user_id,
            resource_type=resource_type,
            action="export",
            ip_address=ip_address,
            additional_data={
                "record_count": record_count,
                "export_format": export_format,
            }
        )

    def log_scrape_event(
        self,
        source: str,
        resource_type: str,
        record_count: int,
        success: bool = True,
        error_message: Optional[str] = None
    ):
        """Log data scraping event"""
        return self.log_event(
            event_type=AuditEventType.DATA_SCRAPE,
            resource_type=resource_type,
            action="scrape",
            status_code=200 if success else 500,
            error_message=error_message,
            additional_data={
                "source": source,
                "record_count": record_count,
                "success": success,
            }
        )

    def log_rate_limit_hit(
        self,
        user_id: Optional[str],
        endpoint: str,
        limit_type: str = "requests_per_second",
        ip_address: Optional[str] = None
    ):
        """Log rate limit violations"""
        return self.log_event(
            event_type=AuditEventType.RATE_LIMIT_HIT,
            user_id=user_id,
            endpoint=endpoint,
            action="rate_limit_exceeded",
            ip_address=ip_address,
            status_code=429,
            additional_data={
                "limit_type": limit_type,
            }
        )


# Global audit logger instance
audit_logger = AuditLogger()


# Convenience functions
def log_api_call(endpoint: str, method: str, user_id: Optional[str] = None, **kwargs):
    """Quick helper to log API call"""
    return audit_logger.log_api_call(endpoint, method, user_id, **kwargs)


def log_data_access(user_id: str, resource_type: str, resource_ids: List[str], **kwargs):
    """Quick helper to log data access"""
    return audit_logger.log_data_access(user_id, resource_type, resource_ids, **kwargs)


def log_data_export(user_id: str, resource_type: str, record_count: int, **kwargs):
    """Quick helper to log data export"""
    return audit_logger.log_data_export(user_id, resource_type, record_count, **kwargs)
