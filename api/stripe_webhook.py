#!/usr/bin/env python3
"""
Stripe Webhook API - Handles Stripe payment webhooks
Receives payment events from Stripe and updates subscription status

Run: uvicorn stripe_webhook:app --host 0.0.0.0 --port 8002
Or integrate into main FastAPI app

Author: ReviewSignal Team
Version: 1.0
Date: 2026-01-31
"""

from fastapi import FastAPI, HTTPException, Request, BackgroundTasks
from pydantic import BaseModel
from typing import Optional, Dict, Any
from psycopg2.extras import RealDictCursor
import os
from datetime import datetime
import structlog
import json

from modules.payment_processor import StripePaymentProcessor, WebhookEvent, SubscriptionTier
from modules.db import get_connection, return_connection
from modules.email_sender import EmailSender
from modules.payment_processor import SubscriptionTier

logger = structlog.get_logger()

app = FastAPI(title="ReviewSignal Stripe Webhook", version="1.0")

# Stripe config
STRIPE_API_KEY = os.getenv("STRIPE_API_KEY", "")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")

# Initialize Stripe processor
stripe_processor = None
if STRIPE_API_KEY and STRIPE_WEBHOOK_SECRET:
    try:
        stripe_processor = StripePaymentProcessor(
            api_key=STRIPE_API_KEY,
            webhook_secret=STRIPE_WEBHOOK_SECRET
        )
        logger.info("stripe_processor_initialized")
    except Exception as e:
        logger.error("stripe_init_error", error=str(e))

# Initialize email sender (lazy - won't fail if no API key)
_email_sender = None

def get_email_sender() -> EmailSender:
    """Get or create email sender instance."""
    global _email_sender
    if _email_sender is None:
        try:
            _email_sender = EmailSender()
        except Exception as e:
            logger.warning("email_sender_init_failed", error=str(e))
    return _email_sender


def _get_customer_info(customer_id: str) -> dict:
    """Fetch customer name and email from Stripe or database."""
    # Try Stripe first
    if stripe_processor:
        try:
            customer = stripe_processor.get_customer(customer_id)
            if customer:
                return {"email": customer.email, "name": customer.name or "Valued Customer"}
        except Exception:
            pass
    # Fallback: query database
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT email, name FROM users WHERE stripe_customer_id = %s", (customer_id,))
            row = cur.fetchone()
            if row:
                return {"email": row[0], "name": row[1] or "Valued Customer"}
    except Exception:
        pass
    finally:
        return_connection(conn)
    return {}


def _send_subscription_welcome(customer_id: str, subscription_data: dict):
    """Send welcome email for new subscription. Called as background task."""
    sender = get_email_sender()
    if not sender:
        return
    info = _get_customer_info(customer_id)
    if not info.get("email"):
        logger.warning("welcome_email_skipped_no_email", customer_id=customer_id)
        return
    tier_name = subscription_data.get("tier", "pro").capitalize()
    # Look up features from pricing tiers
    tier_enum = None
    for t in SubscriptionTier:
        if t.value == subscription_data.get("tier", "pro"):
            tier_enum = t
            break
    features = []
    if tier_enum and tier_enum in StripePaymentProcessor.PRICING_TIERS:
        features = StripePaymentProcessor.PRICING_TIERS[tier_enum].features
    else:
        features = ["Access to ReviewSignal platform", "Sentiment analysis reports", "API access"]
    try:
        result = sender.send_welcome_email(
            customer_email=info["email"],
            customer_name=info["name"],
            tier_name=tier_name,
            features=features
        )
        logger.info("welcome_email_sent", customer_id=customer_id, success=result.get("success"))
    except Exception as e:
        logger.error("welcome_email_failed", customer_id=customer_id, error=str(e))


def _send_payment_failed(event_data: dict):
    """Send payment failed email. Called as background task."""
    sender = get_email_sender()
    if not sender:
        return
    customer_id = event_data.get("customer")
    if not customer_id:
        return
    info = _get_customer_info(customer_id)
    if not info.get("email"):
        logger.warning("payment_failed_email_skipped_no_email", customer_id=customer_id)
        return
    amount_cents = event_data.get("amount_due", 0) or event_data.get("amount", 0) or 0
    amount_eur = amount_cents / 100 if amount_cents > 100 else amount_cents  # Handle if already in EUR
    next_attempt = event_data.get("next_payment_attempt", "within 3-5 business days")
    if isinstance(next_attempt, (int, float)):
        from datetime import datetime as dt
        next_attempt = dt.fromtimestamp(next_attempt).strftime("%Y-%m-%d")
    try:
        result = sender.send_payment_failed_email(
            customer_email=info["email"],
            customer_name=info["name"],
            amount=amount_eur,
            retry_date=str(next_attempt)
        )
        logger.info("payment_failed_email_sent", customer_id=customer_id, success=result.get("success"))
    except Exception as e:
        logger.error("payment_failed_email_error", customer_id=customer_id, error=str(e))


def _send_invoice_paid(event_data: dict):
    """Send invoice receipt email. Called as background task."""
    sender = get_email_sender()
    if not sender:
        return
    customer_id = event_data.get("customer")
    if not customer_id:
        return
    info = _get_customer_info(customer_id)
    if not info.get("email"):
        logger.warning("invoice_email_skipped_no_email", customer_id=customer_id)
        return
    amount_cents = event_data.get("amount_paid", 0) or 0
    amount_eur = amount_cents / 100 if amount_cents > 100 else amount_cents
    invoice_data = {
        "invoice_number": event_data.get("invoice_id", event_data.get("number", "N/A")),
        "date": datetime.now().strftime("%Y-%m-%d"),
        "amount": amount_eur,
        "currency": "EUR",
        "tier": "Pro",
        "period": "Monthly",
        "payment_method": "Card on file",
        "invoice_pdf_url": event_data.get("invoice_pdf", "")
    }
    try:
        result = sender.send_invoice_email(
            customer_email=info["email"],
            customer_name=info["name"],
            invoice_data=invoice_data
        )
        logger.info("invoice_email_sent", customer_id=customer_id, success=result.get("success"))
    except Exception as e:
        logger.error("invoice_email_error", customer_id=customer_id, error=str(e))


class WebhookEventLog(BaseModel):
    """Model for webhook event logging"""
    event_id: str
    event_type: str
    customer_id: Optional[str] = None
    subscription_id: Optional[str] = None
    payment_id: Optional[str] = None
    amount: Optional[int] = None
    status: str
    data: Dict[str, Any]


def get_db_connection():
    """Get PostgreSQL connection from shared pool."""
    return get_connection()


def log_webhook_event(event_log: WebhookEventLog) -> bool:
    """
    Log webhook event to database.
    Creates webhook_events table if it doesn't exist.
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # Create table if not exists
            cur.execute("""
                CREATE TABLE IF NOT EXISTS webhook_events (
                    id SERIAL PRIMARY KEY,
                    event_id VARCHAR(255) UNIQUE NOT NULL,
                    event_type VARCHAR(100) NOT NULL,
                    customer_id VARCHAR(255),
                    subscription_id VARCHAR(255),
                    payment_id VARCHAR(255),
                    amount INTEGER,
                    status VARCHAR(50),
                    data JSONB,
                    created_at TIMESTAMP DEFAULT NOW(),
                    processed_at TIMESTAMP DEFAULT NOW()
                );

                CREATE INDEX IF NOT EXISTS idx_webhook_events_type ON webhook_events(event_type);
                CREATE INDEX IF NOT EXISTS idx_webhook_events_customer ON webhook_events(customer_id);
                CREATE INDEX IF NOT EXISTS idx_webhook_events_created ON webhook_events(created_at);
            """)

            # Insert event
            cur.execute("""
                INSERT INTO webhook_events
                (event_id, event_type, customer_id, subscription_id, payment_id, amount, status, data)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (event_id) DO UPDATE SET
                    status = EXCLUDED.status,
                    processed_at = NOW()
            """, (
                event_log.event_id,
                event_log.event_type,
                event_log.customer_id,
                event_log.subscription_id,
                event_log.payment_id,
                event_log.amount,
                event_log.status,
                json.dumps(event_log.data)
            ))

            conn.commit()
            return True

    except Exception as e:
        logger.error("webhook_log_error", error=str(e))
        conn.rollback()
        return False
    finally:
        return_connection(conn)


def update_user_subscription(customer_id: str, subscription_data: Dict) -> bool:
    """
    Update user subscription status in database based on Stripe event.
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # Update user subscription tier and status
            cur.execute("""
                UPDATE users
                SET
                    subscription_tier = %s,
                    stripe_customer_id = %s,
                    updated_at = NOW()
                WHERE stripe_customer_id = %s
            """, (
                subscription_data.get('tier', 'trial'),
                customer_id,
                customer_id
            ))

            # Also update or create subscription record
            cur.execute("""
                INSERT INTO subscriptions
                (subscription_id, user_id, stripe_subscription_id, tier, status, amount, currency, interval, current_period_start, current_period_end, created_at)
                SELECT
                    %s,
                    user_id,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    NOW()
                FROM users
                WHERE stripe_customer_id = %s
                ON CONFLICT (stripe_subscription_id) DO UPDATE SET
                    status = EXCLUDED.status,
                    current_period_start = EXCLUDED.current_period_start,
                    current_period_end = EXCLUDED.current_period_end,
                    cancel_at_period_end = false
            """, (
                subscription_data.get('subscription_id'),
                subscription_data.get('subscription_id'),
                subscription_data.get('tier', 'trial'),
                subscription_data.get('status', 'active'),
                subscription_data.get('amount', 0),
                subscription_data.get('currency', 'eur'),
                subscription_data.get('interval', 'month'),
                subscription_data.get('current_period_start'),
                subscription_data.get('current_period_end'),
                customer_id
            ))

            conn.commit()
            logger.info("subscription_updated", customer_id=customer_id, status=subscription_data.get('status'))
            return True

    except Exception as e:
        logger.error("subscription_update_error", error=str(e), customer_id=customer_id)
        conn.rollback()
        return False
    finally:
        return_connection(conn)


def process_payment_success(payment_data: Dict) -> bool:
    """Process successful payment event"""
    customer_id = payment_data.get('customer')
    amount = payment_data.get('amount', 0)

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # Record payment
            cur.execute("""
                INSERT INTO payments
                (payment_id, user_id, stripe_payment_id, amount, currency, status, description, created_at, processed_at)
                SELECT
                    %s,
                    user_id,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    NOW(),
                    NOW()
                FROM users
                WHERE stripe_customer_id = %s
            """, (
                payment_data.get('payment_intent'),
                payment_data.get('payment_intent'),
                amount,
                'eur',
                'succeeded',
                'Payment received via Stripe',
                customer_id
            ))

            conn.commit()
            logger.info("payment_recorded", customer_id=customer_id, amount=amount)
            return True

    except Exception as e:
        logger.error("payment_record_error", error=str(e))
        conn.rollback()
        return False
    finally:
        return_connection(conn)


@app.post("/webhook/stripe")
async def stripe_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    Stripe webhook endpoint.
    Receives webhook events from Stripe and processes them.

    Expected headers:
    - Stripe-Signature: Webhook signature for verification

    Supported events:
    - payment_intent.succeeded: Payment completed successfully
    - payment_intent.payment_failed: Payment failed
    - customer.subscription.created: New subscription created
    - customer.subscription.updated: Subscription changed
    - customer.subscription.deleted: Subscription cancelled
    - invoice.paid: Invoice paid
    - invoice.payment_failed: Invoice payment failed
    """
    if not stripe_processor:
        raise HTTPException(
            status_code=503,
            detail="Stripe webhook handler not configured. Set STRIPE_API_KEY and STRIPE_WEBHOOK_SECRET."
        )

    # Get raw body and signature
    payload = await request.body()
    signature = request.headers.get("Stripe-Signature")

    if not signature:
        raise HTTPException(status_code=400, detail="Missing Stripe signature")

    # Process webhook using payment processor
    result = stripe_processor.handle_webhook(payload, signature)

    if "error" in result:
        logger.error("webhook_processing_error", error=result["error"])
        raise HTTPException(status_code=400, detail=result["error"])

    # Extract event data
    event_type = result.get("event_type")
    event_id = result.get("event_id")
    event_data = result.get("data", {})

    logger.info("webhook_received", event_type=event_type, event_id=event_id)

    # Log event to database
    webhook_log = WebhookEventLog(
        event_id=event_id,
        event_type=event_type,
        customer_id=event_data.get("customer"),
        subscription_id=event_data.get("subscription_id") or event_data.get("subscription"),
        payment_id=event_data.get("payment_intent"),
        amount=event_data.get("amount") or event_data.get("amount_paid"),
        status="processed",
        data=event_data
    )

    log_webhook_event(webhook_log)

    # Process specific event types
    if event_type == WebhookEvent.PAYMENT_SUCCESS.value:
        background_tasks.add_task(process_payment_success, event_data)

    elif event_type == WebhookEvent.SUBSCRIPTION_CREATED.value:
        # Determine tier from the subscription's price_id
        price_id = event_data.get('price_id', '')
        matched_tier = StripePaymentProcessor.get_tier_by_price_id(price_id)
        if matched_tier:
            tier_name = matched_tier.value
            pricing = StripePaymentProcessor.PRICING_TIERS[matched_tier]
            amount = pricing.amount_cents
        else:
            logger.warning("webhook_unknown_price_id", price_id=price_id)
            tier_name = 'starter'
            amount = 250000  # fallback to starter

        subscription_data = {
            'subscription_id': event_data.get('subscription_id'),
            'tier': tier_name,
            'status': event_data.get('status'),
            'amount': amount,
            'currency': 'eur',
            'interval': 'month'
        }
        background_tasks.add_task(update_user_subscription, event_data.get('customer'), subscription_data)

    elif event_type == WebhookEvent.SUBSCRIPTION_UPDATED.value:
        # Handle subscription updates
        subscription_data = {
            'subscription_id': event_data.get('subscription_id'),
            'status': event_data.get('status')
        }
        background_tasks.add_task(update_user_subscription, event_data.get('customer'), subscription_data)

    elif event_type == WebhookEvent.SUBSCRIPTION_CANCELLED.value:
        # Mark subscription as cancelled
        subscription_data = {
            'subscription_id': event_data.get('subscription_id'),
            'status': 'cancelled'
        }
        background_tasks.add_task(update_user_subscription, event_data.get('customer'), subscription_data)

    elif event_type == WebhookEvent.INVOICE_PAID.value:
        # Record invoice payment
        payment_data = {
            'payment_intent': event_data.get('invoice_id'),
            'customer': event_data.get('customer'),
            'amount': event_data.get('amount_paid'),
            'subscription': event_data.get('subscription')
        }
        background_tasks.add_task(process_payment_success, payment_data)
        # Send invoice receipt email (non-blocking)
        background_tasks.add_task(_send_invoice_paid, event_data)

    elif event_type == WebhookEvent.INVOICE_FAILED.value:
        # Send payment failed email (non-blocking)
        background_tasks.add_task(_send_payment_failed, event_data)

    return {
        "success": True,
        "event_type": event_type,
        "event_id": event_id,
        "message": "Webhook processed successfully"
    }


@app.get("/webhook/events")
async def get_webhook_events(limit: int = 50, event_type: Optional[str] = None):
    """
    Get recent webhook events from database.
    Useful for debugging and monitoring.
    """
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            if event_type:
                cur.execute("""
                    SELECT event_id, event_type, customer_id, subscription_id, amount, status, created_at
                    FROM webhook_events
                    WHERE event_type = %s
                    ORDER BY created_at DESC
                    LIMIT %s
                """, (event_type, limit))
            else:
                cur.execute("""
                    SELECT event_id, event_type, customer_id, subscription_id, amount, status, created_at
                    FROM webhook_events
                    ORDER BY created_at DESC
                    LIMIT %s
                """, (limit,))

            events = cur.fetchall()
            return {
                "events": events,
                "count": len(events)
            }
    finally:
        return_connection(conn)


@app.get("/webhook/stats")
async def webhook_stats():
    """Get webhook statistics"""
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT
                    event_type,
                    COUNT(*) as count,
                    MAX(created_at) as last_event
                FROM webhook_events
                WHERE created_at > NOW() - INTERVAL '30 days'
                GROUP BY event_type
                ORDER BY count DESC
            """)

            stats = cur.fetchall()
            return {
                "stats": stats,
                "total_events": sum(s['count'] for s in stats)
            }
    finally:
        return_connection(conn)


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "ok",
        "service": "stripe_webhook",
        "stripe_configured": bool(stripe_processor)
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
