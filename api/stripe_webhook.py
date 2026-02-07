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

from modules.payment_processor import StripePaymentProcessor, WebhookEvent
from modules.db import get_connection, return_connection

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
        subscription_data = {
            'subscription_id': event_data.get('subscription_id'),
            'tier': 'pro',  # Default, should be determined by price_id
            'status': event_data.get('status'),
            'amount': 500000,  # €5000 in cents
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
