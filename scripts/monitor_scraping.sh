#!/bin/bash
# Monitor USA Expansion Scraping Progress

echo "════════════════════════════════════════════════════════"
echo "   USA EXPANSION SCRAPING - LIVE MONITORING"
echo "════════════════════════════════════════════════════════"
echo ""

# Check if process is running
if pgrep -f "usa_expansion_scraper" > /dev/null; then
    echo "✅ Scraper Status: RUNNING"
    PID=$(pgrep -f "usa_expansion_scraper")
    echo "   PID: $PID"
    echo "   CPU: $(ps -p $PID -o %cpu= | tr -d ' ')%"
    echo "   MEM: $(ps -p $PID -o %mem= | tr -d ' ')%"
    echo ""
else
    echo "⚠️  Scraper Status: NOT RUNNING"
    echo ""
fi

# Latest log file
LATEST_LOG=$(ls -t logs/usa_expansion_*.log 2>/dev/null | head -1)

if [ -n "$LATEST_LOG" ]; then
    echo "📊 Latest Progress (last 15 lines):"
    echo "────────────────────────────────────────────────────────"
    tail -15 "$LATEST_LOG"
    echo ""
fi

# Database stats
echo "────────────────────────────────────────────────────────"
echo "📈 Database Statistics:"
echo "────────────────────────────────────────────────────────"

sudo -u postgres psql -d reviewsignal << 'EOSQL'
SELECT
    'Total Locations' as metric,
    COUNT(*)::text as value
FROM locations
UNION ALL
SELECT
    'USA Locations',
    COUNT(*)::text
FROM locations
WHERE country = 'US' OR country LIKE '%USA%'
UNION ALL
SELECT
    'Casual Dining',
    COUNT(*)::text
FROM locations l
JOIN chains c ON l.chain_id = c.id
WHERE c.category = 'casual_dining'
UNION ALL
SELECT
    'Drugstores',
    COUNT(*)::text
FROM locations l
JOIN chains c ON l.chain_id = c.id
WHERE c.category = 'drugstore'
UNION ALL
SELECT
    'Added in last hour',
    COUNT(*)::text
FROM locations
WHERE created_at > NOW() - INTERVAL '1 hour';
EOSQL

echo ""
echo "════════════════════════════════════════════════════════"
echo "Odśwież: bash scripts/monitor_scraping.sh"
echo "════════════════════════════════════════════════════════"
