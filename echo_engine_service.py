#!/usr/bin/env python3
"""
Echo Engine Service Launcher
Runs the Echo Engine API on port 8002
"""

import os
import sys
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / '.env')

# Validate required env vars
if not os.getenv('JWT_SECRET') or len(os.getenv('JWT_SECRET', '')) < 32:
    raise RuntimeError("JWT_SECRET must be set in .env and be at least 32 characters")

# Import and run
import uvicorn

if __name__ == "__main__":
    print("Starting Echo Engine API on port 8002...")
    uvicorn.run(
        "api.echo_api:app",
        host="0.0.0.0",
        port=8002,
        workers=2,
        log_level="info",
        access_log=True
    )
