#!/bin/bash

# Simple Apollo status checker for n8n setup
# Usage: ./check_apollo_simple.sh

echo "╔══════════════════════════════════════════════════════╗"
echo "║  🚀 APOLLO WORKFLOW STATUS CHECK                    ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""
echo "📅 $(date '+%Y-%m-%d %H:%M:%S')"
echo ""

# Check if n8n is running
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "1️⃣ Checking n8n status..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if docker ps | grep -q n8n; then
    UPTIME=$(docker ps --format "{{.Status}}" --filter "name=n8n")
    echo "   ✅ n8n is running ($UPTIME)"
    echo "   🌐 URL: http://35.246.214.156:5678"
else
    echo "   ❌ n8n is NOT running!"
    echo "   Run: docker start n8n"
    exit 1
fi
echo ""

# Check n8n accessibility
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "2️⃣ Checking n8n accessibility..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://35.246.214.156:5678 --max-time 5)
if [ "$HTTP_STATUS" = "200" ]; then
    echo "   ✅ n8n is accessible"
elif [ "$HTTP_STATUS" = "302" ] || [ "$HTTP_STATUS" = "301" ]; then
    echo "   ✅ n8n is accessible (redirect to login)"
else
    echo "   ⚠️  Got HTTP $HTTP_STATUS (might need login)"
fi
echo ""

# Timeline check
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "3️⃣ Launch timeline..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

LAUNCH_DATE="2026-02-14"
TODAY=$(date +%Y-%m-%d)
DAYS_LEFT=$(( ($(date -d "$LAUNCH_DATE" +%s) - $(date -d "$TODAY" +%s)) / 86400 ))

echo "   📅 Today: $TODAY"
echo "   🎯 Launch: $LAUNCH_DATE"
echo "   ⏱️  Days left: $DAYS_LEFT days"
echo ""

if [ $DAYS_LEFT -le 0 ]; then
    echo "   🚀 LAUNCH DAY! Time to activate Instantly campaign!"
elif [ $DAYS_LEFT -le 7 ]; then
    echo "   🔥 Final week! Check domain warmup (target 75%)"
else
    echo "   ⏳ Keep collecting leads, domains warming up"
fi
echo ""

# Action items
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "4️⃣ Your action items..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "   🎯 APOLLO WORKFLOW:"
echo "      1. Open: http://35.246.214.156:5678"
echo "      2. Go to: Workflows → FLOW 7"
echo "      3. Toggle: Active ✅"
echo "      4. Check: Executions tab for activity"
echo ""
echo "   📊 DOMAIN WARMUP:"
echo "      1. Check: https://app.instantly.ai/dashboard/warmup"
echo "      2. Current target: 70%+"
echo "      3. Launch target: 75%+"
echo ""
echo "   📋 WEEKLY CHECKS (Mondays):"
echo "      [ ] Check warmup progress"
echo "      [ ] Review n8n executions"
echo "      [ ] Verify leads are collecting"
echo ""

# Summary
echo "╔══════════════════════════════════════════════════════╗"
echo "║  📋 QUICK SUMMARY                                   ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""
echo "   n8n Status:     ✅ Running"
echo "   Apollo:         ⏳ Activate in n8n dashboard"
echo "   Days to launch: $DAYS_LEFT days"
echo "   Next check:     Next Monday 9 AM"
echo ""
echo "══════════════════════════════════════════════════════════"
echo "🚀 Ready to activate Apollo! Open n8n now!"
echo "══════════════════════════════════════════════════════════"
