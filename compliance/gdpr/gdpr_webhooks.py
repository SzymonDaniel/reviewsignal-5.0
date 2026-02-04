"""
GDPR Webhook Dispatcher
ReviewSignal 5.0

Webhook support for GDPR events:
- Consent changes (granted, withdrawn, expired)
- Request lifecycle (created, processing, completed, rejected)
- Data operations (export, erasure, rectification)
"""

import structlog
import httpx
import hashlib
import hmac
import json
from datetime import datetime
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text
from sqlalchemy.dialects.postgresql import JSONB, ARRAY
from sqlalchemy.sql import func
from enum import Enum
import asyncio

import sys
sys.path.insert(0, '/home/info_betsim/reviewsignal-5.0')

from modules.database_schema import Base

logger = structlog.get_logger("gdpr.webhooks")


class WebhookEventType(str, Enum):
    """Types of GDPR webhook events"""
    # Consent events
    consent_granted = "consent.granted"
    consent_withdrawn = "consent.withdrawn"
    consent_expired = "consent.expired"

    # Request events
    request_created = "request.created"
    request_processing = "request.processing"
    request_completed = "request.completed"
    request_rejected = "request.rejected"

    # Data events
    data_exported = "data.exported"
    data_erased = "data.erased"
    data_rectified = "data.rectified"
    data_restricted = "data.restricted"

    # Compliance events
    overdue_alert = "compliance.overdue_alert"
    retention_cleanup = "compliance.retention_cleanup"


class GDPRWebhookSubscription(Base):
    """
    Webhook subscription model.
    Stores registered webhook endpoints.
    """
    __tablename__ = 'gdpr_webhook_subscriptions'

    subscription_id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    url = Column(String(500), nullable=False)
    secret = Column(String(255), nullable=False)  # For HMAC signature
    events = Column(ARRAY(String), nullable=False)  # List of event types
    is_active = Column(Boolean, default=True)
    headers = Column(JSONB, default={})  # Custom headers
    retry_count = Column(Integer, default=3)
    timeout_seconds = Column(Integer, default=30)
    last_triggered_at = Column(DateTime(timezone=True), nullable=True)
    last_status_code = Column(Integer, nullable=True)
    failure_count = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "subscription_id": self.subscription_id,
            "name": self.name,
            "url": self.url,
            "events": self.events,
            "is_active": self.is_active,
            "retry_count": self.retry_count,
            "timeout_seconds": self.timeout_seconds,
            "last_triggered_at": self.last_triggered_at.isoformat() if self.last_triggered_at else None,
            "last_status_code": self.last_status_code,
            "failure_count": self.failure_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class GDPRWebhookLog(Base):
    """
    Webhook delivery log model.
    Tracks all webhook deliveries for debugging.
    """
    __tablename__ = 'gdpr_webhook_logs'

    log_id = Column(Integer, primary_key=True, autoincrement=True)
    subscription_id = Column(Integer, nullable=False)
    event_type = Column(String(50), nullable=False)
    payload = Column(JSONB, nullable=False)
    response_status = Column(Integer, nullable=True)
    response_body = Column(Text, nullable=True)
    attempt_number = Column(Integer, default=1)
    success = Column(Boolean, default=False)
    error_message = Column(Text, nullable=True)
    duration_ms = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "log_id": self.log_id,
            "subscription_id": self.subscription_id,
            "event_type": self.event_type,
            "response_status": self.response_status,
            "success": self.success,
            "error_message": self.error_message,
            "duration_ms": self.duration_ms,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class GDPRWebhookDispatcher:
    """
    Dispatches webhooks for GDPR events.
    """

    def __init__(self, session: Session):
        """
        Initialize webhook dispatcher.

        Args:
            session: SQLAlchemy session
        """
        self.session = session

    def _generate_signature(self, payload: str, secret: str) -> str:
        """
        Generate HMAC-SHA256 signature for webhook payload.

        Args:
            payload: JSON payload string
            secret: Webhook secret

        Returns:
            Hex-encoded signature
        """
        return hmac.new(
            secret.encode('utf-8'),
            payload.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

    def subscribe(
        self,
        name: str,
        url: str,
        secret: str,
        events: List[str],
        headers: Optional[Dict[str, str]] = None,
        retry_count: int = 3,
        timeout_seconds: int = 30
    ) -> Dict[str, Any]:
        """
        Subscribe to GDPR webhook events.

        Args:
            name: Subscription name
            url: Webhook endpoint URL
            secret: Secret for HMAC signature
            events: List of event types to subscribe to
            headers: Custom headers to include
            retry_count: Number of retry attempts
            timeout_seconds: Request timeout

        Returns:
            Subscription details
        """
        # Validate events
        valid_events = [e.value for e in WebhookEventType]
        for event in events:
            if event not in valid_events and event != "*":
                return {"error": f"Invalid event type: {event}. Valid types: {valid_events}"}

        subscription = GDPRWebhookSubscription(
            name=name,
            url=url,
            secret=secret,
            events=events,
            headers=headers or {},
            retry_count=retry_count,
            timeout_seconds=timeout_seconds
        )

        self.session.add(subscription)
        self.session.commit()

        logger.info(
            "webhook_subscribed",
            subscription_id=subscription.subscription_id,
            name=name,
            url=url,
            events=events
        )

        return subscription.to_dict()

    def unsubscribe(self, subscription_id: int) -> Dict[str, Any]:
        """
        Unsubscribe from webhooks.

        Args:
            subscription_id: Subscription ID to remove

        Returns:
            Result
        """
        subscription = self.session.query(GDPRWebhookSubscription).filter(
            GDPRWebhookSubscription.subscription_id == subscription_id
        ).first()

        if not subscription:
            return {"error": f"Subscription not found: {subscription_id}"}

        self.session.delete(subscription)
        self.session.commit()

        logger.info("webhook_unsubscribed", subscription_id=subscription_id)

        return {"success": True, "message": f"Subscription {subscription_id} removed"}

    def update_subscription(
        self,
        subscription_id: int,
        is_active: Optional[bool] = None,
        events: Optional[List[str]] = None,
        url: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Update webhook subscription.

        Args:
            subscription_id: Subscription ID
            is_active: Enable/disable subscription
            events: New event list
            url: New URL

        Returns:
            Updated subscription
        """
        subscription = self.session.query(GDPRWebhookSubscription).filter(
            GDPRWebhookSubscription.subscription_id == subscription_id
        ).first()

        if not subscription:
            return {"error": f"Subscription not found: {subscription_id}"}

        if is_active is not None:
            subscription.is_active = is_active
        if events is not None:
            subscription.events = events
        if url is not None:
            subscription.url = url

        self.session.commit()

        return subscription.to_dict()

    def list_subscriptions(self) -> List[Dict[str, Any]]:
        """
        List all webhook subscriptions.

        Returns:
            List of subscriptions
        """
        subscriptions = self.session.query(GDPRWebhookSubscription).all()
        return [s.to_dict() for s in subscriptions]

    def _get_subscriptions_for_event(self, event_type: str) -> List[GDPRWebhookSubscription]:
        """
        Get active subscriptions for an event type.

        Args:
            event_type: Event type string

        Returns:
            List of matching subscriptions
        """
        subscriptions = self.session.query(GDPRWebhookSubscription).filter(
            GDPRWebhookSubscription.is_active == True
        ).all()

        # Filter by event type (support wildcard *)
        return [
            s for s in subscriptions
            if "*" in s.events or event_type in s.events
        ]

    async def _deliver_webhook(
        self,
        subscription: GDPRWebhookSubscription,
        event_type: str,
        payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Deliver webhook to endpoint with retry.

        Args:
            subscription: Webhook subscription
            event_type: Event type
            payload: Event payload

        Returns:
            Delivery result
        """
        payload_with_meta = {
            "event": event_type,
            "timestamp": datetime.utcnow().isoformat(),
            "data": payload
        }
        payload_json = json.dumps(payload_with_meta, default=str)

        # Generate signature
        signature = self._generate_signature(payload_json, subscription.secret)

        headers = {
            "Content-Type": "application/json",
            "X-Webhook-Event": event_type,
            "X-Webhook-Signature": f"sha256={signature}",
            "X-Webhook-Timestamp": datetime.utcnow().isoformat(),
            **subscription.headers
        }

        last_error = None
        for attempt in range(1, subscription.retry_count + 1):
            start_time = datetime.utcnow()

            try:
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        subscription.url,
                        content=payload_json,
                        headers=headers,
                        timeout=subscription.timeout_seconds
                    )

                duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
                success = 200 <= response.status_code < 300

                # Log delivery
                log = GDPRWebhookLog(
                    subscription_id=subscription.subscription_id,
                    event_type=event_type,
                    payload=payload_with_meta,
                    response_status=response.status_code,
                    response_body=response.text[:1000] if response.text else None,
                    attempt_number=attempt,
                    success=success,
                    duration_ms=duration_ms
                )
                self.session.add(log)

                # Update subscription stats
                subscription.last_triggered_at = datetime.utcnow()
                subscription.last_status_code = response.status_code
                if success:
                    subscription.failure_count = 0
                else:
                    subscription.failure_count += 1

                self.session.commit()

                if success:
                    logger.info(
                        "webhook_delivered",
                        subscription_id=subscription.subscription_id,
                        event=event_type,
                        status=response.status_code,
                        attempt=attempt
                    )
                    return {"success": True, "status_code": response.status_code}

                last_error = f"HTTP {response.status_code}"

            except Exception as e:
                last_error = str(e)
                duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)

                # Log failed delivery
                log = GDPRWebhookLog(
                    subscription_id=subscription.subscription_id,
                    event_type=event_type,
                    payload=payload_with_meta,
                    attempt_number=attempt,
                    success=False,
                    error_message=str(e),
                    duration_ms=duration_ms
                )
                self.session.add(log)
                subscription.failure_count += 1
                self.session.commit()

                logger.warning(
                    "webhook_delivery_failed",
                    subscription_id=subscription.subscription_id,
                    event=event_type,
                    attempt=attempt,
                    error=str(e)
                )

            # Wait before retry (exponential backoff)
            if attempt < subscription.retry_count:
                await asyncio.sleep(2 ** attempt)

        return {"success": False, "error": last_error}

    def dispatch(
        self,
        event_type: WebhookEventType,
        payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Dispatch webhook event to all subscribers (sync wrapper).

        Args:
            event_type: Event type
            payload: Event data

        Returns:
            Dispatch summary
        """
        subscriptions = self._get_subscriptions_for_event(event_type.value)

        if not subscriptions:
            return {"dispatched": 0, "message": "No active subscriptions for event"}

        # Run async delivery
        results = []
        for sub in subscriptions:
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            result = loop.run_until_complete(
                self._deliver_webhook(sub, event_type.value, payload)
            )
            results.append({
                "subscription_id": sub.subscription_id,
                "name": sub.name,
                **result
            })

        success_count = sum(1 for r in results if r.get("success"))

        logger.info(
            "webhook_dispatch_complete",
            event=event_type.value,
            total=len(results),
            success=success_count
        )

        return {
            "event": event_type.value,
            "dispatched": len(results),
            "success_count": success_count,
            "results": results
        }

    async def dispatch_async(
        self,
        event_type: WebhookEventType,
        payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Dispatch webhook event asynchronously.

        Args:
            event_type: Event type
            payload: Event data

        Returns:
            Dispatch summary
        """
        subscriptions = self._get_subscriptions_for_event(event_type.value)

        if not subscriptions:
            return {"dispatched": 0, "message": "No active subscriptions for event"}

        # Deliver to all subscriptions concurrently
        tasks = [
            self._deliver_webhook(sub, event_type.value, payload)
            for sub in subscriptions
        ]
        results_raw = await asyncio.gather(*tasks, return_exceptions=True)

        results = []
        for sub, result in zip(subscriptions, results_raw):
            if isinstance(result, Exception):
                results.append({
                    "subscription_id": sub.subscription_id,
                    "name": sub.name,
                    "success": False,
                    "error": str(result)
                })
            else:
                results.append({
                    "subscription_id": sub.subscription_id,
                    "name": sub.name,
                    **result
                })

        success_count = sum(1 for r in results if r.get("success"))

        return {
            "event": event_type.value,
            "dispatched": len(results),
            "success_count": success_count,
            "results": results
        }

    def get_delivery_logs(
        self,
        subscription_id: Optional[int] = None,
        event_type: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get webhook delivery logs.

        Args:
            subscription_id: Filter by subscription
            event_type: Filter by event type
            limit: Max results

        Returns:
            List of log entries
        """
        query = self.session.query(GDPRWebhookLog)

        if subscription_id:
            query = query.filter(GDPRWebhookLog.subscription_id == subscription_id)
        if event_type:
            query = query.filter(GDPRWebhookLog.event_type == event_type)

        logs = query.order_by(GDPRWebhookLog.created_at.desc()).limit(limit).all()
        return [log.to_dict() for log in logs]


# Convenience functions for dispatching common events
def dispatch_consent_event(
    session: Session,
    event_type: WebhookEventType,
    email: str,
    consent_type: str,
    details: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Dispatch a consent-related webhook event."""
    dispatcher = GDPRWebhookDispatcher(session)
    payload = {
        "subject_email": email,
        "consent_type": consent_type,
        **(details or {})
    }
    return dispatcher.dispatch(event_type, payload)


def dispatch_request_event(
    session: Session,
    event_type: WebhookEventType,
    request_id: int,
    email: str,
    request_type: str,
    details: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Dispatch a request-related webhook event."""
    dispatcher = GDPRWebhookDispatcher(session)
    payload = {
        "request_id": request_id,
        "subject_email": email,
        "request_type": request_type,
        **(details or {})
    }
    return dispatcher.dispatch(event_type, payload)


def dispatch_data_event(
    session: Session,
    event_type: WebhookEventType,
    email: str,
    operation: str,
    details: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Dispatch a data operation webhook event."""
    dispatcher = GDPRWebhookDispatcher(session)
    payload = {
        "subject_email": email,
        "operation": operation,
        **(details or {})
    }
    return dispatcher.dispatch(event_type, payload)
