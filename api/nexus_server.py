#!/usr/bin/env python3
"""
HIGGS NEXUS SERVER - Standalone API Server
ReviewSignal 5.0

Runs Higgs Nexus as independent service on port 8004.
Orchestrates Echo Engine + Singularity Engine signals.
"""

import os
import sys
from pathlib import Path

# Add project root to path (needed when run as standalone script via systemd)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / '.env')

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from modules.higgs_nexus.nexus_api import router, startup, shutdown

# Create FastAPI app
app = FastAPI(
    title="Higgs Nexus API",
    description="""
    # Higgs Nexus - Quantum Field Intelligence Orchestration

    Orchestrates Echo Engine and Singularity Engine to produce unified trading signals.

    ## Key Features
    - **Phase Detection**: Mexican hat potential dynamics for market phase identification
    - **Swarm Intelligence**: Collective AI decision making
    - **Signal Arbitration**: Combines multiple engines into single recommendation

    ## Endpoints
    - `POST /nexus/analyze` - Main analysis combining all engines
    - `GET /nexus/phase` - Current market phase state
    - `GET /nexus/health` - System health check
    - `GET /nexus/swarm/metrics` - Swarm intelligence metrics
    """,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://reviewsignal.ai",
        "https://app.reviewsignal.ai",
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-API-Key"],
)

# Include Nexus router
app.include_router(router)

# Root endpoint
@app.get("/")
async def root():
    return {
        "name": "Higgs Nexus",
        "version": "1.0.0",
        "description": "Quantum Field Intelligence Orchestration Layer",
        "docs": "/docs",
        "endpoints": {
            "analyze": "POST /nexus/analyze",
            "phase": "GET /nexus/phase",
            "health": "GET /nexus/health",
            "swarm": "GET /nexus/swarm/metrics"
        }
    }

# Health check at root level
@app.get("/health")
async def health():
    return {"status": "healthy", "service": "higgs_nexus"}

# Startup/shutdown events
@app.on_event("startup")
async def on_startup():
    await startup()

@app.on_event("shutdown")
async def on_shutdown():
    await shutdown()


if __name__ == "__main__":
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8004,
        workers=1,
        log_level="info"
    )
