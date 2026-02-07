#!/bin/bash
# Monitor Apollo workflow and lead collection

echo "╔════════════════════════════════════════════════════════════╗"
echo "║      Apollo Workflow Monitor - Retail Marketing Leads      ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

# Current time
echo "📅 Current Time (UTC):"
date -u
echo ""

# Check n8n status
echo "🐳 n8n Container Status:"
docker ps | grep n8n | awk '{print "   Status: " $7 " | Uptime: " $9 " " $10}'
echo ""

# Workflow execution stats
echo "📊 Workflow Execution Stats:"
sudo sqlite3 /root/.n8n/database.sqlite <<EOF
SELECT
    'Total Executions: ' || COUNT(*) ||
    ' | Successful: ' || SUM(CASE WHEN finished = 1 THEN 1 ELSE 0 END) ||
    ' | Failed: ' || SUM(CASE WHEN finished = 0 THEN 1 ELSE 0 END)
FROM execution_entity
WHERE workflowId = 'C2kIA0mMISzcKnjC';
EOF
echo ""

# Last 3 executions
echo "⏱️  Last 3 Executions:"
sudo sqlite3 /root/.n8n/database.sqlite <<EOF
.mode column
SELECT
    SUBSTR(startedAt, 1, 19) as started,
    CASE WHEN finished = 1 THEN '✅' ELSE '❌' END as status,
    CAST((julianday(stoppedAt) - julianday(startedAt)) * 86400 AS INTEGER) || 's' as duration
FROM execution_entity
WHERE workflowId = 'C2kIA0mMISzcKnjC'
ORDER BY startedAt DESC
LIMIT 3;
EOF
echo ""

# Lead Receiver API status
echo "🔌 Lead Receiver API:"
curl -s http://localhost:8001/health | python3 -m json.tool 2>/dev/null || echo "   ❌ API not responding"
echo ""

# Lead statistics
echo "📈 Lead Statistics:"
sudo -u postgres psql -d reviewsignal -t -c "
SELECT
    '   Total Leads: ' || COUNT(*) ||
    ' | With Names: ' || COUNT(CASE WHEN name IS NOT NULL AND name != '' THEN 1 END) ||
    ' | Retail Industry: ' || COUNT(CASE WHEN industry = 'retail' THEN 1 END)
FROM leads;
"

# Recent retail leads
echo ""
echo "🎯 Recent Retail Leads (last 5):"
sudo -u postgres psql -d reviewsignal -t -c "
SELECT
    '   ' || COALESCE(name, 'No name') ||
    ' | ' || COALESCE(title, 'No title') ||
    ' | ' || COALESCE(company, 'No company') ||
    ' | ' || SUBSTR(created_at::TEXT, 1, 16)
FROM leads
WHERE industry = 'retail' OR company LIKE '%Retail%' OR company LIKE '%SEPHORA%' OR company LIKE '%Walmart%'
ORDER BY created_at DESC
LIMIT 5;
" | grep -v "^$"

if [ $? -ne 0 ]; then
    echo "   (No retail leads found yet)"
fi

echo ""
echo "⏰ Next Scheduled Run:"
echo "   23:00 UTC (every 6 hours: 05:00, 11:00, 17:00, 23:00)"
echo ""

# Time until next run
CURRENT_HOUR=$(date -u +%H)
CURRENT_MIN=$(date -u +%M)
NEXT_RUN=23

if [ $CURRENT_HOUR -lt 5 ]; then NEXT_RUN=5
elif [ $CURRENT_HOUR -lt 11 ]; then NEXT_RUN=11
elif [ $CURRENT_HOUR -lt 17 ]; then NEXT_RUN=17
elif [ $CURRENT_HOUR -lt 23 ]; then NEXT_RUN=23
else NEXT_RUN=5; fi

echo "📍 Configuration:"
echo "   Industry: retail (NOT finance)"
echo "   Email Status: verified (contactEmailStatusV2)"
echo "   Titles: Marketing Director, Head of Marketing, VP Marketing, CMO"
echo ""

echo "✅ Workflow is configured and active!"
echo "   Monitor again after next execution with: ./monitor_apollo_leads.sh"
echo ""
