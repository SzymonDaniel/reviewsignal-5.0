#!/usr/bin/env python3
"""
Lead Receiver API - Accepts leads from Apollo via n8n
Saves directly to PostgreSQL and can sync to Instantly

Run: uvicorn lead_receiver:app --host 0.0.0.0 --port 8001
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel, EmailStr
from typing import Optional
from psycopg2.extras import RealDictCursor
import os
import httpx
from datetime import datetime
import structlog
import time

from modules.db import get_connection, return_connection
from modules.data_validator import LeadValidator

logger = structlog.get_logger()

app = FastAPI(title="ReviewSignal Lead Receiver", version="2.1")

# Import metrics
try:
    from api.metrics_helper import (
        metrics_endpoint,
        track_lead_collected, track_lead_processed, track_lead_failed,
        track_instantly_sync, set_database_connections, track_database_query
    )
    METRICS_ENABLED = True
except ImportError:
    METRICS_ENABLED = False
    logger.warning("metrics_helper_not_available")

# Instantly config (optional)
INSTANTLY_API_KEY = os.getenv("INSTANTLY_API_KEY", "")
INSTANTLY_CAMPAIGN_ID = os.getenv("INSTANTLY_CAMPAIGN_ID", "")


class LeadInput(BaseModel):
    """Lead data from Apollo enrichment"""
    email: EmailStr
    first_name: str
    last_name: str
    title: Optional[str] = None
    company: Optional[str] = None
    company_domain: Optional[str] = None
    industry: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    linkedin_url: Optional[str] = None
    phone: Optional[str] = None
    lead_score: Optional[int] = 50
    intent_score: Optional[int] = 0
    intent_level: Optional[str] = "none"
    priority: Optional[str] = "medium"
    personalized_angle: Optional[str] = None
    company_size: Optional[str] = None
    source: Optional[str] = "apollo"


# Campaign mapping by segment
CAMPAIGN_MAPPING = {
    "portfolio_manager": os.getenv("INSTANTLY_CAMPAIGN_PM", ""),
    "quant_analyst": os.getenv("INSTANTLY_CAMPAIGN_QUANT", ""),
    "head_alt_data": os.getenv("INSTANTLY_CAMPAIGN_ALTDATA", ""),
    "cio": os.getenv("INSTANTLY_CAMPAIGN_CIO", ""),
    "high_intent": os.getenv("INSTANTLY_CAMPAIGN_INTENT", ""),
    "default": os.getenv("INSTANTLY_CAMPAIGN_ID", "")
}


def determine_segment(title: str, intent_level: str = "none") -> str:
    """
    Determine lead segment based on title and intent.
    Returns segment name for campaign routing.
    """
    if not title:
        return "default"

    title_lower = title.lower()

    # High intent leads go to dedicated campaign
    if intent_level in ["high", "medium"]:
        return "high_intent"

    # CIO / C-Level
    if any(k in title_lower for k in ['chief investment officer', 'cio', 'managing director', 'partner']):
        return "cio"

    # Head of Alternative Data
    if any(k in title_lower for k in ['alternative data', 'alt data', 'head of data']):
        return "head_alt_data"

    # Portfolio Manager
    if any(k in title_lower for k in ['portfolio manager', 'pm']):
        return "portfolio_manager"

    # Quant Analyst
    if any(k in title_lower for k in ['quant', 'quantitative', 'data scientist', 'researcher']):
        return "quant_analyst"

    return "default"


class LeadResponse(BaseModel):
    success: bool
    lead_id: Optional[int] = None
    message: str
    instantly_synced: bool = False


def get_db_connection():
    """Get PostgreSQL connection from shared pool."""
    return get_connection()


def return_db_connection(conn) -> None:
    """Return connection to shared pool."""
    return_connection(conn)


def check_opted_out(email: str) -> bool:
    """Check if a lead has opted out. Returns True if opted out."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT opted_out FROM leads WHERE email = %s",
                (email,)
            )
            row = cur.fetchone()
            if row and row[0]:
                return True
            return False
    finally:
        return_db_connection(conn)


def save_lead_to_db(lead: LeadInput) -> Optional[int]:
    """Save lead to PostgreSQL, returns lead ID"""
    start_time = time.time()
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO leads (email, name, title, company, company_domain, industry, linkedin_url, phone, lead_score, priority, personalized_angle, company_size, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (email) DO UPDATE SET
                    name = EXCLUDED.name,
                    title = EXCLUDED.title,
                    company = EXCLUDED.company,
                    company_domain = COALESCE(EXCLUDED.company_domain, leads.company_domain),
                    industry = COALESCE(EXCLUDED.industry, leads.industry),
                    linkedin_url = EXCLUDED.linkedin_url,
                    phone = COALESCE(EXCLUDED.phone, leads.phone),
                    lead_score = EXCLUDED.lead_score,
                    priority = EXCLUDED.priority
                RETURNING id
            """, (
                lead.email,
                f"{lead.first_name} {lead.last_name}",
                lead.title,
                lead.company,
                lead.company_domain,
                lead.industry,
                lead.linkedin_url,
                lead.phone,
                lead.lead_score or 50,
                lead.priority or "high",
                lead.personalized_angle,
                lead.company_size,
                datetime.utcnow()
            ))
            result = cur.fetchone()
            conn.commit()

            # Track database query duration
            if METRICS_ENABLED:
                duration = time.time() - start_time
                track_database_query('save_lead', duration)

            return result[0] if result else None
    except Exception as e:
        logger.error("db_save_error", error=str(e), email=lead.email)
        conn.rollback()
        return None
    finally:
        return_db_connection(conn)


async def sync_to_instantly(lead: LeadInput, segment: str = None) -> bool:
    """
    Sync lead to Instantly campaign (API v2).
    Routes to appropriate campaign based on segment.
    Skips leads that have opted out.
    """
    if not INSTANTLY_API_KEY:
        logger.warning("instantly_not_configured")
        return False

    # Check if lead has opted out before syncing
    if check_opted_out(lead.email):
        logger.info("instantly_sync_skipped_opted_out", email=lead.email)
        return False

    # Determine segment if not provided
    if not segment:
        segment = determine_segment(lead.title, lead.intent_level or "none")

    # Get campaign ID for segment
    campaign_id = CAMPAIGN_MAPPING.get(segment) or CAMPAIGN_MAPPING.get("default")

    if not campaign_id:
        logger.warning("no_campaign_for_segment", segment=segment)
        return False

    try:
        async with httpx.AsyncClient() as client:
            # Build custom variables based on segment
            custom_vars = {
                "title": lead.title or "",
                "company_name": lead.company or "",
                "city": lead.city or "",
                "country": lead.country or "",
                "linkedin": lead.linkedin_url or "",
                "segment": segment,
                "intent_level": lead.intent_level or "none",
                "lead_score": str(lead.lead_score or 50)
            }

            # Add personalized angle if available
            if lead.personalized_angle:
                custom_vars["personalized_angle"] = lead.personalized_angle

            response = await client.post(
                "https://api.instantly.ai/api/v2/leads",
                headers={
                    "Authorization": f"Bearer {INSTANTLY_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "campaign_id": campaign_id,
                    "email": lead.email,
                    "first_name": lead.first_name,
                    "last_name": lead.last_name,
                    "company_name": lead.company or "",
                    "personalization": lead.personalized_angle or lead.title or "",
                    "custom_variables": custom_vars
                }
            )
            if response.status_code in [200, 201]:
                logger.info(
                    "instantly_sync_success",
                    email=lead.email,
                    segment=segment,
                    campaign_id=campaign_id,
                    instantly_id=response.json().get("id")
                )
                if METRICS_ENABLED:
                    track_instantly_sync('success')
                return True
            else:
                logger.error(
                    "instantly_sync_error",
                    status=response.status_code,
                    response=response.text,
                    segment=segment
                )
                if METRICS_ENABLED:
                    track_instantly_sync('error')
                return False
    except Exception as e:
        logger.error("instantly_sync_exception", error=str(e))
        return False


@app.post("/api/lead", response_model=LeadResponse)
async def receive_lead(lead: LeadInput, background_tasks: BackgroundTasks):
    """
    Receive lead from n8n/Apollo and save to database.
    Automatically segments lead and routes to appropriate Instantly campaign.
    """
    # --- VALIDATION GATE ---
    lead_dict = {
        "email": lead.email,
        "first_name": lead.first_name,
        "last_name": lead.last_name,
        "name": f"{lead.first_name} {lead.last_name}",
        "company": lead.company,
        "title": lead.title,
    }
    valid, issues = LeadValidator.validate(lead_dict)
    if not valid:
        logger.warning("lead_validation_rejected", email=lead.email, issues=issues)
        if METRICS_ENABLED:
            track_lead_failed()
        raise HTTPException(status_code=422, detail=f"Lead validation failed: {'; '.join(issues)}")

    # Determine segment for routing
    segment = determine_segment(lead.title, lead.intent_level or "none")

    # Save to PostgreSQL
    lead_id = save_lead_to_db(lead)

    if not lead_id:
        if METRICS_ENABLED:
            track_lead_failed()
        raise HTTPException(status_code=500, detail="Failed to save lead to database")

    # Track metrics
    if METRICS_ENABLED:
        track_lead_collected(lead.source or 'apollo')
        track_lead_processed()

    # Sync to Instantly in background (non-blocking)
    instantly_synced = False
    if INSTANTLY_API_KEY:
        background_tasks.add_task(sync_to_instantly, lead, segment)
        instantly_synced = True  # Will be synced

    logger.info(
        "lead_received",
        email=lead.email,
        lead_id=lead_id,
        segment=segment,
        intent_level=lead.intent_level,
        lead_score=lead.lead_score
    )

    return LeadResponse(
        success=True,
        lead_id=lead_id,
        message=f"Lead saved: {lead.first_name} {lead.last_name} ({lead.company}) [Segment: {segment}]",
        instantly_synced=instantly_synced
    )


@app.post("/api/leads/bulk")
async def receive_leads_bulk(leads: list[LeadInput], background_tasks: BackgroundTasks):
    """Receive multiple leads at once"""
    saved = 0
    failed = 0
    rejected = 0

    for lead in leads:
        # --- VALIDATION GATE ---
        lead_dict = {
            "email": lead.email,
            "first_name": lead.first_name,
            "last_name": lead.last_name,
            "name": f"{lead.first_name} {lead.last_name}",
            "company": lead.company,
            "title": lead.title,
        }
        valid, issues = LeadValidator.validate(lead_dict)
        if not valid:
            logger.warning("bulk_lead_validation_rejected", email=lead.email, issues=issues)
            rejected += 1
            continue

        lead_id = save_lead_to_db(lead)
        if lead_id:
            saved += 1
            if INSTANTLY_API_KEY and INSTANTLY_CAMPAIGN_ID:
                background_tasks.add_task(sync_to_instantly, lead)
        else:
            failed += 1

    return {
        "success": True,
        "saved": saved,
        "failed": failed,
        "rejected_validation": rejected,
        "total": len(leads)
    }


@app.get("/api/leads/pending")
async def get_pending_leads(limit: int = 100):
    """Get leads that haven't been sent to Instantly yet"""
    start_time = time.time()
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT id, email, name, title, company, linkedin_url, created_at
                FROM leads
                WHERE nurture_sequence = false
                ORDER BY created_at DESC
                LIMIT %s
            """, (limit,))
            result = {"leads": cur.fetchall()}

            # Track query duration
            if METRICS_ENABLED:
                duration = time.time() - start_time
                track_database_query('get_pending_leads', duration)

            return result
    finally:
        return_db_connection(conn)


@app.get("/api/stats")
async def get_stats():
    """Get lead statistics"""
    start_time = time.time()
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT
                    COUNT(*) as total_leads,
                    COUNT(CASE WHEN nurture_sequence = true THEN 1 END) as sent_to_instantly,
                    COUNT(CASE WHEN created_at > NOW() - INTERVAL '24 hours' THEN 1 END) as last_24h,
                    COUNT(CASE WHEN created_at > NOW() - INTERVAL '7 days' THEN 1 END) as last_7d
                FROM leads
            """)
            result = cur.fetchone()

            # Track query duration
            if METRICS_ENABLED:
                duration = time.time() - start_time
                track_database_query('get_stats', duration)

            return result
    finally:
        return_db_connection(conn)


@app.get("/api/segment-test")
async def test_segmentation(title: str, intent_level: str = "none"):
    """
    Test lead segmentation logic.
    Returns which campaign the lead would be routed to.
    """
    segment = determine_segment(title, intent_level)
    campaign_id = CAMPAIGN_MAPPING.get(segment) or CAMPAIGN_MAPPING.get("default")

    return {
        "title": title,
        "intent_level": intent_level,
        "segment": segment,
        "campaign_id": campaign_id or "not_configured",
        "available_segments": list(CAMPAIGN_MAPPING.keys())
    }


@app.get("/api/campaigns")
async def list_campaigns():
    """List configured campaign mappings"""
    return {
        "campaigns": {
            k: v if v else "NOT_CONFIGURED"
            for k, v in CAMPAIGN_MAPPING.items()
        },
        "note": "Set campaign IDs via environment variables: INSTANTLY_CAMPAIGN_PM, INSTANTLY_CAMPAIGN_QUANT, etc."
    }


class OptOutRequest(BaseModel):
    """Request to opt-out a lead"""
    email: EmailStr


class OptOutResponse(BaseModel):
    """Response for opt-out request"""
    success: bool
    email: str
    message: str


@app.post("/api/leads/opt-out", response_model=OptOutResponse)
async def opt_out_lead(body: OptOutRequest):
    """
    Mark a lead as opted out. Opted-out leads will not be synced to Instantly
    and will be excluded from all future email campaigns.
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE leads
                   SET opted_out = TRUE, opted_out_at = %s
                   WHERE email = %s
                   RETURNING id, email""",
                (datetime.utcnow(), body.email)
            )
            row = cur.fetchone()
            conn.commit()

            if row:
                logger.info("lead_opted_out", email=body.email, lead_id=row[0])
                return OptOutResponse(
                    success=True,
                    email=body.email,
                    message=f"Lead {body.email} has been opted out successfully."
                )
            else:
                logger.warning("opt_out_email_not_found", email=body.email)
                return OptOutResponse(
                    success=False,
                    email=body.email,
                    message=f"No lead found with email {body.email}."
                )
    except Exception as e:
        conn.rollback()
        logger.error("opt_out_error", error=str(e), email=body.email)
        raise HTTPException(status_code=500, detail=f"Opt-out failed: {str(e)}")
    finally:
        return_db_connection(conn)


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "ok", "service": "lead_receiver", "version": "2.1"}


@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint"""
    if METRICS_ENABLED:
        return metrics_endpoint()
    else:
        return {"error": "Metrics not enabled"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
