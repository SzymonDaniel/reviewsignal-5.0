#!/bin/bash
# One-command monitoring setup for ReviewSignal

set -e

echo "╔═══════════════════════════════════════════════════════════╗"
echo "║   ReviewSignal Complete Monitoring Installation          ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo ""

# Check root
if [ "$EUID" -ne 0 ]; then
    echo "❌ Please run as root: sudo $0"
    exit 1
fi

cd /home/info_betsim/reviewsignal-5.0

echo "Step 1/7: Installing dependencies..."
pip3 install prometheus-client psutil --quiet 2>/dev/null || true

echo "Step 2/7: Creating directory structure..."
mkdir -p monitoring/grafana/provisioning/{datasources,dashboards}
mkdir -p monitoring/grafana/dashboards
mkdir -p logs backups/{database,n8n,config,logs}

echo "Step 3/7: Setting permissions..."
chown -R info_betsim:info_betsim monitoring logs backups scripts
chmod +x scripts/*.sh

echo "Step 4/7: Starting monitoring stack..."
docker-compose -f docker-compose.monitoring.yml up -d

echo "Step 5/7: Waiting for services (30s)..."
sleep 30

echo "Step 6/7: Setting up backup automation..."
chmod +x scripts/backup_automation.sh
(crontab -l 2>/dev/null | grep -v "backup_automation"; echo "0 2 * * * /home/info_betsim/reviewsignal-5.0/scripts/backup_automation.sh") | crontab -

echo "Step 7/7: Configuring log rotation..."
cat > /etc/logrotate.d/reviewsignal <<EOF
/home/info_betsim/reviewsignal-5.0/logs/*.log {
    daily
    rotate 30
    compress
    delaycompress
    notifempty
    create 0644 info_betsim info_betsim
}
EOF

echo ""
echo "╔═══════════════════════════════════════════════════════════╗"
echo "║   ✅ Installation Complete!                               ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo ""
echo "📊 Access URLs:"
echo "   Grafana:      http://35.246.214.156:3001 (admin/<REDACTED>)"
echo "   Prometheus:   http://35.246.214.156:9090"
echo "   Alertmanager: http://35.246.214.156:9093"
echo ""
echo "📝 Next Steps:"
echo "   1. Configure Slack webhook in monitoring/alertmanager.yml"
echo "   2. Restart lead-receiver with metrics: systemctl restart lead-receiver"
echo "   3. Run test backup: ./scripts/backup_automation.sh"
echo ""
echo "🔍 Check status: docker ps | grep reviewsignal"
echo ""
