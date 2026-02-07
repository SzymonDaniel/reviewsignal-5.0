#!/usr/bin/env python3
"""
Echo Engine Service Launcher
Runs the Echo Engine API on port 8002
"""

import os
import sys

# Set environment
os.environ.setdefault('JWT_SECRET', 'reviewsignal_production_secret_key_2026_minimum32chars')

# Add project to path
sys.path.insert(0, '/home/info_betsim/reviewsignal-5.0')

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
