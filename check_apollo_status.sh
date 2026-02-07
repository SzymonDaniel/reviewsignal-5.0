#!/bin/bash

# Quick script to check Apollo lead collection status
# Usage: ./check_apollo_status.sh

echo "=================================================="
echo "🔍 APOLLO LEAD COLLECTION STATUS"
echo "=================================================="
echo ""
echo "📅 Date: $(date '+%Y-%m-%d %H:%M:%S')"
echo ""

# Check if PostgreSQL is running
echo "1️⃣ Checking PostgreSQL status..."
if docker ps | grep -q reviewsignal_postgres; then
    echo "   ✅ PostgreSQL is running"
else
    echo "   ❌ PostgreSQL is NOT running!"
    echo "   Run: docker start reviewsignal_postgres"
    exit 1
fi
echo ""

# Check lead count
echo "2️⃣ Checking total leads collected..."
TOTAL_LEADS=$(docker exec reviewsignal_postgres psql -U reviewsignal -d reviewsignal -t -c \
    "SELECT COUNT(*) FROM leads WHERE source = 'apollo';" 2>/dev/null | tr -d ' ')

if [ -z "$TOTAL_LEADS" ]; then
    echo "   ⚠️  Could not query database (table might not exist yet)"
    echo "   This is normal if Apollo hasn't run yet"
else
    echo "   📊 Total Apollo leads: $TOTAL_LEADS"

    # Calculate progress
    TARGET=500
    PROGRESS=$((TOTAL_LEADS * 100 / TARGET))
    echo "   📈 Progress to target (500): ${PROGRESS}%"

    # Days to launch
    LAUNCH_DATE="2026-02-14"
    TODAY=$(date +%Y-%m-%d)
    DAYS_LEFT=$(( ($(date -d "$LAUNCH_DATE" +%s) - $(date -d "$TODAY" +%s)) / 86400 ))
    echo "   ⏱️  Days until launch: $DAYS_LEFT days"

    # Daily rate needed
    if [ $DAYS_LEFT -gt 0 ]; then
        NEEDED_PER_DAY=$(( (TARGET - TOTAL_LEADS) / DAYS_LEFT ))
        echo "   🎯 Leads needed per day: ~$NEEDED_PER_DAY"
    fi
fi
echo ""

# Check recent leads
echo "3️⃣ Latest lead collected..."
docker exec reviewsignal_postgres psql -U reviewsignal -d reviewsignal -c \
    "SELECT name, email, company, created_at
     FROM leads
     WHERE source = 'apollo'
     ORDER BY created_at DESC
     LIMIT 1;" 2>/dev/null

if [ $? -ne 0 ]; then
    echo "   ⚠️  No leads yet or table doesn't exist"
    echo "   Activate Apollo workflow in n8n!"
fi
echo ""

# Check leads from last 24h
echo "4️⃣ Leads collected in last 24 hours..."
RECENT_COUNT=$(docker exec reviewsignal_postgres psql -U reviewsignal -d reviewsignal -t -c \
    "SELECT COUNT(*) FROM leads
     WHERE source = 'apollo'
     AND created_at > NOW() - INTERVAL '24 hours';" 2>/dev/null | tr -d ' ')

if [ -z "$RECENT_COUNT" ]; then
    echo "   ⚠️  Could not query recent leads"
else
    echo "   📊 Leads in last 24h: $RECENT_COUNT"
    if [ "$RECENT_COUNT" -eq 0 ]; then
        echo "   ⚠️  No recent activity! Check Apollo workflow in n8n"
    elif [ "$RECENT_COUNT" -lt 20 ]; then
        echo "   ⚠️  Low activity. Expected: 30-50/day"
    else
        echo "   ✅ Good activity level!"
    fi
fi
echo ""

# Summary
echo "=================================================="
echo "📋 QUICK SUMMARY"
echo "=================================================="
if [ ! -z "$TOTAL_LEADS" ] && [ "$TOTAL_LEADS" -ge 500 ]; then
    echo "✅ TARGET REACHED! You have $TOTAL_LEADS leads"
elif [ ! -z "$TOTAL_LEADS" ] && [ "$TOTAL_LEADS" -gt 0 ]; then
    echo "⏳ Collection in progress: $TOTAL_LEADS / 500 leads"
else
    echo "🚀 ACTIVATE APOLLO WORKFLOW in n8n now!"
    echo "   URL: http://35.246.214.156:5678"
fi
echo ""
echo "Next check: Tomorrow same time"
echo "=================================================="
