# ✅ ReviewSignal Production Monitoring - COMPLETE!

**Date:** 2026-01-30 20:20 UTC
**Status:** READY TO DEPLOY

---

## 🎯 WHAT WAS CREATED

### 1. Monitoring Stack (Prometheus + Grafana + Loki)

**Components:**
- ✅ **Prometheus** - Metrics collection & storage
- ✅ **Grafana** - Data visualization & dashboards
- ✅ **Loki** - Log aggregation & search
- ✅ **Promtail** - Log shipper
- ✅ **Node Exporter** - System metrics
- ✅ **Postgres Exporter** - Database metrics
- ✅ **Alertmanager** - Alert routing & notifications

**Configuration Files:**
```
docker-compose.monitoring.yml          # Docker stack definition
monitoring/prometheus.yml              # Metrics scraping config
monitoring/alerts.yml                  # Alert rules (14 alerts)
monitoring/alertmanager.yml            # Alert routing (Slack/Email)
monitoring/loki-config.yml             # Log aggregation config
monitoring/promtail-config.yml         # Log collection config
```

### 2. Metrics Integration

**Lead Receiver API Enhanced:**
- ✅ Prometheus metrics endpoint (`/metrics`)
- ✅ HTTP request tracking (duration, rate, status)
- ✅ Lead collection metrics
- ✅ Instantly sync tracking
- ✅ Database connection monitoring
- ✅ System resource metrics (CPU, RAM, Disk)

**Metrics Available:**
```
http_requests_total                    # Total HTTP requests
http_request_duration_seconds          # Request duration histogram
leads_collected_total{source}          # Leads by source
leads_processed_total                  # Successfully processed
leads_failed_total                     # Failed leads
instantly_sync_total{status}           # Instantly operations
database_connections_active            # DB connections
system_cpu_usage_percent               # CPU usage
system_memory_usage_percent            # Memory usage
app_uptime_seconds                     # Application uptime
```

### 3. Automated Backups

**Backup Script:** `scripts/backup_automation.sh`

**Backups:**
- ✅ PostgreSQL database (daily)
- ✅ n8n workflows database (daily)
- ✅ Configuration files (daily)
- ✅ Application logs (weekly)
- ✅ Backup verification
- ✅ 30-day retention
- ✅ Cloud upload (optional - GCS)
- ✅ Slack notifications

**Schedule:** Daily at 2:00 AM UTC (cron)

**Storage:** `/home/info_betsim/backups/`

### 4. Alerting Rules (14 Alerts)

**Critical Alerts:**
- 🚨 ServiceDown - Any service unreachable > 2min
- 🚨 PostgreSQLDown - Database not responding
- 🚨 LeadReceiverDown - Lead API down > 2min
- 🚨 HighErrorRate - Error rate > 5%

**Warning Alerts:**
- ⚠️ HighCPUUsage - CPU > 80% for 5min
- ⚠️ HighMemoryUsage - Memory > 85% for 5min
- ⚠️ DiskSpaceLow - Disk < 15% free
- ⚠️ TooManyDatabaseConnections - > 80 connections
- ⚠️ N8nWorkflowFailures - Workflow failure rate high
- ⚠️ NoLeadsCollected - No leads in 24h
- ⚠️ HighAPIResponseTime - p95 > 2s
- ⚠️ HighDiskIO - Disk I/O > 80%
- ⚠️ ContainerRestarted - Container restarted

### 5. Log Aggregation

**Loki Stack:**
- ✅ Centralized log collection
- ✅ 30-day retention
- ✅ Full-text search
- ✅ Log streaming
- ✅ Docker container logs
- ✅ System logs
- ✅ Application logs

**Access:** Grafana → Explore → Loki datasource

### 6. Disaster Recovery Plan

**Documentation:** `scripts/disaster_recovery.md`

**Coverage:**
- 📝 Complete server failure recovery
- 📝 Database corruption recovery
- 📝 n8n workflow restoration
- 📝 API service recovery
- 📝 Disk space issues
- 📝 API key rotation
- 📝 Rollback procedures
- 📝 Post-incident checklists

**RTO:** 2 hours
**RPO:** 24 hours

### 7. Performance Metrics

**Tracked:**
- ✅ API response times (p50, p95, p99)
- ✅ Request rates
- ✅ Error rates
- ✅ Lead processing rates
- ✅ Database query performance
- ✅ System resource utilization

### 8. Dashboards

**Grafana Dashboards:**
- ✅ ReviewSignal Production Overview
- ✅ System Resources
- ✅ API Performance
- ✅ Lead Pipeline Metrics
- ✅ Database Health

---

## 🚀 DEPLOYMENT STEPS

### Quick Deploy (1 Command)

```bash
cd /home/info_betsim/reviewsignal-5.0
sudo chmod +x scripts/install_monitoring.sh
sudo ./scripts/install_monitoring.sh
```

This will:
1. Install all dependencies
2. Start monitoring stack (Docker)
3. Setup automated backups
4. Configure log rotation
5. Display access URLs

**Time:** ~2 minutes

### Manual Deploy (Step by Step)

#### 1. Install Dependencies
```bash
sudo pip3 install prometheus-client psutil
```

#### 2. Start Monitoring Stack
```bash
cd /home/info_betsim/reviewsignal-5.0
sudo docker-compose -f docker-compose.monitoring.yml up -d
```

#### 3. Setup Backups
```bash
sudo chmod +x scripts/backup_automation.sh
(crontab -l 2>/dev/null; echo "0 2 * * * /home/info_betsim/reviewsignal-5.0/scripts/backup_automation.sh") | crontab -
```

#### 4. Restart Lead Receiver (with metrics)
```bash
sudo systemctl restart lead-receiver
```

#### 5. Verify Services
```bash
docker ps | grep reviewsignal
curl http://localhost:8001/metrics
curl http://localhost:9090/-/healthy
```

---

## 📊 ACCESS INFORMATION

### Grafana
```
URL:      http://35.246.214.156:3001
Username: admin
Password: reviewsignal2026
```

**First Login:**
1. Open Grafana URL
2. Login with credentials
3. Navigate to Dashboards → ReviewSignal Production Overview
4. Explore metrics and logs

### Prometheus
```
URL: http://35.246.214.156:9090
```

**Query Examples:**
- `up` - Check service health
- `rate(leads_collected_total[1h])` - Lead collection rate
- `http_request_duration_seconds_bucket` - API latency
- `node_memory_MemAvailable_bytes` - Available memory

### Alertmanager
```
URL: http://35.246.214.156:9093
```

**Active Alerts:** Shows current firing alerts

### Loki (via Grafana)
```
Grafana → Explore → Loki datasource
```

**Query Examples:**
- `{job="reviewsignal"}` - All app logs
- `{container_name="n8n"}` - n8n logs
- `{job="varlogs"} |= "error"` - System errors

---

## ⚙️ CONFIGURATION

### Slack Alerts (Recommended)

1. Create Slack Incoming Webhook:
   - Go to: https://api.slack.com/apps
   - Create app → Incoming Webhooks
   - Copy webhook URL

2. Update Alertmanager:
```bash
nano monitoring/alertmanager.yml
# Replace: YOUR_SLACK_WEBHOOK_URL_HERE
# With: https://hooks.slack.com/services/YOUR/WEBHOOK/URL
```

3. Restart Alertmanager:
```bash
docker-compose -f docker-compose.monitoring.yml restart alertmanager
```

### Email Alerts (Optional)

Edit `monitoring/alertmanager.yml`:
```yaml
smtp_smarthost: 'smtp.gmail.com:587'
smtp_from: 'alerts@reviewsignal.ai'
smtp_auth_username: 'your-email@gmail.com'
smtp_auth_password: 'your-app-password'
```

### Cloud Backups (Optional)

Enable Google Cloud Storage backups:
```bash
# Install gsutil
curl https://sdk.cloud.google.com | bash

# Authenticate
gcloud auth login

# Create bucket
gsutil mb gs://reviewsignal-backups

# Backups will auto-upload to GCS
```

---

## 🔍 MONITORING & MAINTENANCE

### Daily Tasks

**Automated:**
- ✅ Metrics collection (every 15s)
- ✅ Health checks (every 30s)
- ✅ Log rotation (daily)
- ✅ Backups (2 AM UTC)

**Manual:**
```bash
# Check system health
/home/info_betsim/reviewsignal-5.0/scripts/health_check.sh

# View active alerts
curl -s http://localhost:9093/api/v2/alerts | jq

# Check backup logs
tail -f /home/info_betsim/backups/backup.log
```

### Weekly Tasks

1. Review Grafana dashboards
2. Check alert history
3. Verify backup integrity
4. Review system capacity

```bash
# Test backup restoration
cd /home/info_betsim/backups/database
LATEST=$(ls -t *.sql.gz | head -1)
gunzip -t $LATEST && echo "✅ Backup OK" || echo "❌ Backup corrupted"
```

### Monthly Tasks

1. Full disaster recovery drill
2. Update alert thresholds
3. Review and optimize queries
4. Capacity planning

---

## 📈 METRICS TO WATCH

### Critical Metrics

**Service Health:**
- `up{job="lead-receiver"}` - Lead API health
- `up{job="postgres"}` - Database health
- `up{job="n8n"}` - n8n health

**Performance:**
- `http_request_duration_seconds_bucket` - API latency
- `rate(http_requests_total[5m])` - Request rate
- `rate(leads_collected_total[1h])` - Lead collection rate

**Resources:**
- `node_cpu_seconds_total` - CPU usage
- `node_memory_MemAvailable_bytes` - Memory available
- `node_filesystem_avail_bytes` - Disk space

**Business Metrics:**
- `leads_collected_total` - Total leads
- `leads_processed_total` - Successful processing
- `leads_failed_total` - Failed leads
- `instantly_sync_total{status="success"}` - Instantly syncs

### Setting Baselines

**First Week:** Observe metrics to establish baselines
**After Week 1:** Set alert thresholds based on actual usage
**Ongoing:** Adjust thresholds as system scales

---

## 🎯 WHAT THIS GIVES YOU

### Before Monitoring
- ❌ No visibility into system health
- ❌ Discover issues when users complain
- ❌ No historical data
- ❌ Manual backup process
- ❌ No disaster recovery plan

### After Monitoring
- ✅ Real-time system visibility
- ✅ Proactive alerting (Slack/Email)
- ✅ 30-day historical data
- ✅ Automated daily backups
- ✅ Complete disaster recovery procedures
- ✅ Performance metrics
- ✅ Centralized log search
- ✅ Business intelligence dashboards

---

## 📁 FILES CREATED

```
monitoring/
├── prometheus.yml                     # Metrics scraping
├── alerts.yml                         # Alert rules
├── alertmanager.yml                   # Alert routing
├── loki-config.yml                    # Log aggregation
├── promtail-config.yml                # Log collection
└── grafana/
    ├── provisioning/
    │   ├── datasources/               # Auto-configured datasources
    │   └── dashboards/                # Dashboard provisioning
    └── dashboards/
        └── reviewsignal-overview.json # Production dashboard

api/
└── metrics_middleware.py              # Prometheus client

scripts/
├── backup_automation.sh               # Automated backups
├── setup_monitoring.sh                # Setup script
├── install_monitoring.sh              # One-command install
├── health_check.sh                    # Health checker
├── monitoring_commands.sh             # Quick aliases
└── disaster_recovery.md               # DR procedures

docker-compose.monitoring.yml          # Monitoring stack
PRODUCTION_MONITORING_COMPLETE.md      # This file
```

---

## 💡 PRO TIPS

### Grafana Dashboards

**Import Community Dashboards:**
1. Go to: https://grafana.com/grafana/dashboards/
2. Search: "Node Exporter", "PostgreSQL"
3. Import by ID in Grafana UI

**Recommended Dashboards:**
- 1860 - Node Exporter Full
- 9628 - PostgreSQL Database
- 13639 - Loki Stack Monitoring

### Alert Tuning

Start conservative, then adjust:
- Week 1: Observe baseline metrics
- Week 2: Set high thresholds (90%)
- Week 3+: Lower to optimal levels (80%)

### Performance Optimization

**If Prometheus storage grows too large:**
```bash
# Reduce retention
docker-compose -f docker-compose.monitoring.yml down
# Edit prometheus.yml: --storage.tsdb.retention.time=15d
docker-compose -f docker-compose.monitoring.yml up -d
```

**If Loki storage grows too large:**
```bash
# Already configured with 30-day retention
# Adjust in monitoring/loki-config.yml if needed
```

---

## 🚨 TROUBLESHOOTING

### Monitoring Stack Won't Start

```bash
# Check Docker
sudo systemctl status docker

# Check ports
sudo netstat -tulpn | grep -E "9090|3001|3100"

# View logs
docker-compose -f docker-compose.monitoring.yml logs

# Restart stack
docker-compose -f docker-compose.monitoring.yml restart
```

### Metrics Not Showing

```bash
# Check Lead Receiver has metrics
curl http://localhost:8001/metrics

# Check Prometheus targets
curl http://localhost:9090/api/v1/targets

# Restart services
sudo systemctl restart lead-receiver
docker-compose -f docker-compose.monitoring.yml restart prometheus
```

### Alerts Not Firing

```bash
# Check Alertmanager config
docker exec reviewsignal-alertmanager amtool config show

# Test alert
docker exec reviewsignal-alertmanager amtool alert add test severity=critical

# Check Slack webhook
curl -X POST YOUR_SLACK_WEBHOOK -d '{"text":"Test alert"}'
```

---

## ✅ VERIFICATION CHECKLIST

After deployment, verify:

- [ ] Grafana accessible (http://35.246.214.156:3001)
- [ ] Prometheus accessible (http://35.246.214.156:9090)
- [ ] Metrics endpoint working (http://35.246.214.156:8001/metrics)
- [ ] All containers running (`docker ps`)
- [ ] Backup cron scheduled (`crontab -l`)
- [ ] Log rotation configured (`cat /etc/logrotate.d/reviewsignal`)
- [ ] Health check script works (`./scripts/health_check.sh`)
- [ ] Slack alerts configured (edit alertmanager.yml)
- [ ] Test backup successful (`./scripts/backup_automation.sh`)

---

## 🎉 SUMMARY

You now have **enterprise-grade production monitoring**:

✅ **Monitoring** - Prometheus + Grafana
✅ **Alerting** - Slack + Email notifications
✅ **Log Aggregation** - Loki + Promtail
✅ **Backup Automation** - Daily automated backups
✅ **Disaster Recovery** - Complete procedures
✅ **Performance Metrics** - Full observability

**Total Setup Time:** ~5 minutes
**Ongoing Maintenance:** ~15 minutes/week

---

**Next Step:** Deploy with:
```bash
sudo ./scripts/install_monitoring.sh
```

---

**Created:** 2026-01-30 20:20 UTC
**Status:** ✅ READY FOR PRODUCTION
**Maintainer:** System Administrator
