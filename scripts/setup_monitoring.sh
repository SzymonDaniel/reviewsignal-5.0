#!/bin/bash
# Setup ReviewSignal Monitoring Stack
# Installs and configures Prometheus, Grafana, Loki

set -e

echo "╔═══════════════════════════════════════════════════════════╗"
echo "║   ReviewSignal Production Monitoring Setup               ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

log_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Check if running as root or with sudo
if [ "$EUID" -ne 0 ]; then
    log_error "Please run as root or with sudo"
    exit 1
fi

# Create monitoring directory structure
log_success "Creating monitoring directories..."
mkdir -p /home/info_betsim/reviewsignal-5.0/monitoring/grafana/provisioning/{datasources,dashboards}
mkdir -p /home/info_betsim/reviewsignal-5.0/monitoring/grafana/dashboards

# Install Docker Compose if not present
if ! command -v docker-compose &> /dev/null; then
    log_warning "Docker Compose not found, installing..."
    curl -L "https://github.com/docker/compose/releases/download/v2.20.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    chmod +x /usr/local/bin/docker-compose
    log_success "Docker Compose installed"
fi

# Install Prometheus Python client
log_success "Installing Prometheus Python client..."
pip3 install prometheus-client psutil --quiet

# Create Grafana provisioning config
log_success "Creating Grafana provisioning config..."
cat > /home/info_betsim/reviewsignal-5.0/monitoring/grafana/provisioning/datasources/datasources.yml <<EOF
apiVersion: 1

datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true
    editable: true

  - name: Loki
    type: loki
    access: proxy
    url: http://loki:3100
    editable: true
EOF

cat > /home/info_betsim/reviewsignal-5.0/monitoring/grafana/provisioning/dashboards/dashboards.yml <<EOF
apiVersion: 1

providers:
  - name: 'ReviewSignal'
    orgId: 1
    folder: ''
    type: file
    disableDeletion: false
    updateIntervalSeconds: 30
    allowUiUpdates: true
    options:
      path: /etc/grafana/provisioning/dashboards
EOF

# Set permissions
chown -R info_betsim:info_betsim /home/info_betsim/reviewsignal-5.0/monitoring
chmod +x /home/info_betsim/reviewsignal-5.0/scripts/*.sh

# Start monitoring stack
log_success "Starting monitoring stack with Docker Compose..."
cd /home/info_betsim/reviewsignal-5.0
docker-compose -f docker-compose.monitoring.yml up -d

# Wait for services to start
log_success "Waiting for services to start (30 seconds)..."
sleep 30

# Check if services are running
echo ""
echo "Checking service health..."
for service in prometheus grafana loki promtail node-exporter alertmanager; do
    if docker ps | grep -q "reviewsignal-$service"; then
        log_success "$service is running"
    else
        log_error "$service failed to start"
    fi
done

# Display access information
echo ""
echo "╔═══════════════════════════════════════════════════════════╗"
echo "║   Monitoring Stack Deployed Successfully!                ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo ""
echo "Access URLs:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📊 Grafana:      http://35.246.214.156:3001"
echo "   Username:     admin"
echo "   Password:     <REDACTED>"
echo ""
echo "📈 Prometheus:   http://35.246.214.156:9090"
echo "📝 Loki:         http://35.246.214.156:3100"
echo "🔔 Alertmanager: http://35.246.214.156:9093"
echo ""
echo "Metrics Endpoints:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "System:          http://35.246.214.156:9100/metrics"
echo "PostgreSQL:      http://35.246.214.156:9187/metrics"
echo "Lead API:        http://35.246.214.156:8001/metrics"
echo ""

# Setup automated backups
log_success "Setting up automated backups..."
chmod +x /home/info_betsim/reviewsignal-5.0/scripts/backup_automation.sh

# Add to crontab (daily at 2 AM)
(crontab -l 2>/dev/null | grep -v "backup_automation.sh"; echo "0 2 * * * /home/info_betsim/reviewsignal-5.0/scripts/backup_automation.sh") | crontab -
log_success "Backup automation scheduled (daily at 2 AM UTC)"

# Setup log rotation
log_success "Configuring log rotation..."
cat > /etc/logrotate.d/reviewsignal <<EOF
/home/info_betsim/reviewsignal-5.0/logs/*.log {
    daily
    rotate 30
    compress
    delaycompress
    notifempty
    create 0644 info_betsim info_betsim
    sharedscripts
    postrotate
        systemctl reload lead-receiver || true
    endscript
}
EOF

log_success "Log rotation configured (30 days retention)"

# Create health check script
cat > /home/info_betsim/reviewsignal-5.0/scripts/health_check.sh <<'EOF'
#!/bin/bash
# Health check for all ReviewSignal services

check_service() {
    local name=$1
    local url=$2
    if curl -sf "$url" > /dev/null 2>&1; then
        echo "✅ $name: OK"
        return 0
    else
        echo "❌ $name: DOWN"
        return 1
    fi
}

echo "ReviewSignal Health Check - $(date)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

check_service "Lead Receiver API" "http://localhost:8001/health"
check_service "n8n" "http://localhost:5678"
check_service "Prometheus" "http://localhost:9090/-/healthy"
check_service "Grafana" "http://localhost:3001/api/health"
check_service "Loki" "http://localhost:3100/ready"

echo ""
docker ps --format "table {{.Names}}\t{{.Status}}" | grep reviewsignal
EOF

chmod +x /home/info_betsim/reviewsignal-5.0/scripts/health_check.sh
log_success "Health check script created"

# Create quick monitoring commands
cat > /home/info_betsim/reviewsignal-5.0/scripts/monitoring_commands.sh <<'EOF'
#!/bin/bash
# Quick monitoring commands

alias mon-logs="docker logs -f --tail 100"
alias mon-grafana="firefox http://35.246.214.156:3001 &"
alias mon-prometheus="firefox http://35.246.214.156:9090 &"
alias mon-health="/home/info_betsim/reviewsignal-5.0/scripts/health_check.sh"
alias mon-alerts="curl -s http://localhost:9093/api/v2/alerts | jq"
alias mon-metrics="curl -s http://localhost:8001/metrics"
alias mon-restart="cd /home/info_betsim/reviewsignal-5.0 && docker-compose -f docker-compose.monitoring.yml restart"

echo "Monitoring commands loaded:"
echo "  mon-logs <container>  - Tail container logs"
echo "  mon-grafana          - Open Grafana"
echo "  mon-prometheus       - Open Prometheus"
echo "  mon-health           - Check all services"
echo "  mon-alerts           - List active alerts"
echo "  mon-metrics          - Show API metrics"
echo "  mon-restart          - Restart monitoring stack"
EOF

log_success "Monitoring aliases created"

echo ""
echo "╔═══════════════════════════════════════════════════════════╗"
echo "║   Next Steps                                              ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo ""
echo "1. Configure Slack webhook for alerts:"
echo "   Edit: monitoring/alertmanager.yml"
echo "   Set: YOUR_SLACK_WEBHOOK_URL_HERE"
echo ""
echo "2. Restart Lead Receiver API with metrics:"
echo "   sudo systemctl restart lead-receiver"
echo ""
echo "3. Open Grafana and import dashboards:"
echo "   http://35.246.214.156:3001"
echo ""
echo "4. Test backup automation:"
echo "   sudo /home/info_betsim/reviewsignal-5.0/scripts/backup_automation.sh"
echo ""
echo "5. Check system health:"
echo "   /home/info_betsim/reviewsignal-5.0/scripts/health_check.sh"
echo ""

log_success "Monitoring setup complete! 🎉"
