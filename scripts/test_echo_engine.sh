#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# Echo Engine Test Script
# Tests quantum-inspired sentiment propagation
# ═══════════════════════════════════════════════════════════════

set -e

echo "🔮 Testing Echo Engine - Quantum Sentiment Propagation"
echo "========================================================"
echo ""

# 1. Health check
echo "1️⃣  Health Check"
curl -s http://localhost:8002/api/echo/health | python3 -m json.tool
echo ""
echo ""

# 2. System status
echo "2️⃣  System Status"
curl -s http://localhost:8002/api/echo/system-status | python3 -m json.tool
echo ""
echo ""

# 3. Criticality detection
echo "3️⃣  Critical Locations Detection"
curl -s "http://localhost:8002/api/echo/criticality?threshold=0.3" | python3 -m json.tool
echo ""
echo ""

# 4. Trading signal for top chain
echo "4️⃣  Trading Signal - Starbucks"
curl -s -X POST http://localhost:8002/api/echo/trading-signal \
  -H "Content-Type: application/json" \
  -d '{"chain_name": "Starbucks", "location": "New York"}' | python3 -m json.tool
echo ""
echo ""

echo "✅ Echo Engine Test Complete!"
