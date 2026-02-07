# 🚨 ReviewSignal Disaster Recovery Plan

**Last Updated:** 2026-01-30
**Version:** 1.0
**RTO (Recovery Time Objective):** 2 hours
**RPO (Recovery Point Objective):** 24 hours (daily backups)

---

## 1. EMERGENCY CONTACTS

### Technical Team
- **System Owner:** info_betsim
- **Email:** [YOUR_EMAIL]
- **Slack:** #reviewsignal-alerts

### External Services
- **GCP Support:** Cloud Console → Support
- **Apollo.io:** support@apollo.io
- **Instantly:** support@instantly.ai

---

## 2. BACKUP LOCATIONS

### Daily Automated Backups
```
Location: /home/info_betsim/backups/
Frequency: Daily at 2:00 AM UTC
Retention: 30 days
```

**Backup Contents:**
- PostgreSQL database (`database/reviewsignal_*.sql.gz`)
- n8n workflows (`n8n/n8n_*.sqlite.gz`)
- Configuration files (`config/config_*.tar.gz`)
- Application logs (`logs/logs_*.tar.gz`)

### Cloud Backups (Optional)
```
Location: gs://reviewsignal-backups/ (Google Cloud Storage)
Frequency: Daily (if configured)
Retention: 90 days
```

---

## 3. DISASTER SCENARIOS & RECOVERY PROCEDURES

### Scenario 1: Complete Server Failure ⚠️⚠️⚠️

**Symptoms:**
- Server unreachable
- All services down
- SSH connection refused

**Recovery Steps:**

#### 1.1 Provision New Server
```bash
# Create new GCP VM
gcloud compute instances create reviewsignal-prod-new \
    --zone=us-central1-a \
    --machine-type=e2-medium \
    --image-family=ubuntu-2204-lts \
    --image-project=ubuntu-os-cloud \
    --boot-disk-size=50GB

# Note the new IP address
NEW_IP=$(gcloud compute instances describe reviewsignal-prod-new \
    --zone=us-central1-a --format='get(networkInterfaces[0].accessConfigs[0].natIP)')
```

#### 1.2 Install Base System
```bash
ssh $NEW_IP

# Update system
sudo apt update && sudo apt upgrade -y

# Install dependencies
sudo apt install -y docker.io docker-compose postgresql-14 redis-server python3-pip git

# Start Docker
sudo systemctl enable --now docker
sudo usermod -aG docker $USER
```

#### 1.3 Restore Application Code
```bash
# Clone repository
git clone https://github.com/SzymonDaniel/reviewsignal.git /home/info_betsim/reviewsignal-5.0
cd /home/info_betsim/reviewsignal-5.0
```

#### 1.4 Restore Database
```bash
# Get latest backup (from cloud or local copy)
gsutil cp gs://reviewsignal-backups/database/reviewsignal_latest.sql.gz .

# Restore PostgreSQL
sudo -u postgres createdb reviewsignal
sudo -u postgres createuser reviewsignal -P  # Password: <REDACTED>
gunzip < reviewsignal_latest.sql.gz | sudo -u postgres psql reviewsignal

# Verify
sudo -u postgres psql -d reviewsignal -c "SELECT COUNT(*) FROM leads;"
```

#### 1.5 Restore n8n Workflows
```bash
# Restore n8n database
sudo mkdir -p /root/.n8n
gsutil cp gs://reviewsignal-backups/n8n/n8n_latest.sqlite.gz .
sudo gunzip -c n8n_latest.sqlite.gz > /root/.n8n/database.sqlite

# Start n8n
docker run -d --name n8n \
    -p 5678:5678 \
    -v /root/.n8n:/home/node/.n8n \
    --restart unless-stopped \
    n8nio/n8n
```

#### 1.6 Restore Configuration
```bash
# Extract config files
tar -xzf config_latest.tar.gz -C /

# Update .env file
cat > .env <<EOF
DB_HOST=localhost
DB_PORT=5432
DB_NAME=reviewsignal
DB_USER=reviewsignal
DB_PASS=<REDACTED>
INSTANTLY_API_KEY=<REDACTED_SEE_ENV>
INSTANTLY_CAMPAIGN_ID=f30d31ff-46fe-4ae6-a602-597643a17a0c
APOLLO_API_KEY=<REDACTED_SEE_ENV_FILE>
EOF
```

#### 1.7 Start Services
```bash
# Install Python dependencies
pip3 install -r requirements.txt

# Setup Lead Receiver service
sudo cp /home/info_betsim/reviewsignal-5.0/scripts/lead-receiver.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now lead-receiver

# Start monitoring stack
docker-compose -f docker-compose.monitoring.yml up -d

# Verify all services
systemctl status lead-receiver
docker ps
```

#### 1.8 Update DNS
```bash
# Update Cloudflare DNS A records
# reviewsignal.ai → NEW_IP
# *.reviewsignal.ai → NEW_IP
```

#### 1.9 Verify Recovery
```bash
# Test API
curl http://localhost:8001/health

# Check database
sudo -u postgres psql -d reviewsignal -c "SELECT COUNT(*) FROM leads;"

# Test n8n
curl http://localhost:5678

# Trigger test workflow
```

**Estimated Recovery Time:** 1-2 hours

---

### Scenario 2: Database Corruption 💾

**Symptoms:**
- PostgreSQL won't start
- Database queries fail
- Data integrity errors

**Recovery Steps:**

```bash
# 1. Stop all services using the database
sudo systemctl stop lead-receiver
docker stop n8n

# 2. Backup corrupted database (for forensics)
sudo -u postgres pg_dump reviewsignal > /tmp/corrupted_backup.sql 2>&1 || true

# 3. Drop corrupted database
sudo -u postgres psql -c "DROP DATABASE reviewsignal;"

# 4. Restore from last good backup
cd /home/info_betsim/backups/database
LATEST=$(ls -t reviewsignal_*.sql.gz | head -1)
sudo -u postgres createdb reviewsignal
gunzip < $LATEST | sudo -u postgres psql reviewsignal

# 5. Verify data integrity
sudo -u postgres psql -d reviewsignal <<EOF
SELECT COUNT(*) as total_leads FROM leads;
SELECT COUNT(*) as locations FROM locations;
SELECT COUNT(*) as reviews FROM reviews;
\q
EOF

# 6. Restart services
sudo systemctl start lead-receiver
docker start n8n
```

**Estimated Recovery Time:** 30 minutes

---

### Scenario 3: n8n Workflow Corruption 🔄

**Symptoms:**
- Workflows not executing
- n8n UI errors
- Workflow configuration lost

**Recovery Steps:**

```bash
# 1. Stop n8n
docker stop n8n

# 2. Backup current database
sudo cp /root/.n8n/database.sqlite /root/.n8n/database.sqlite.corrupted

# 3. Restore from last good backup
cd /home/info_betsim/backups/n8n
LATEST=$(ls -t n8n_*.sqlite.gz | head -1)
sudo gunzip -c $LATEST > /root/.n8n/database.sqlite

# 4. Restart n8n
docker start n8n

# 5. Verify workflows
docker logs n8n --tail 50
curl http://localhost:5678
```

**Estimated Recovery Time:** 10 minutes

---

### Scenario 4: Lead Receiver API Down 🔴

**Symptoms:**
- API not responding on port 8001
- Health check fails
- Leads not being saved

**Recovery Steps:**

```bash
# 1. Check service status
sudo systemctl status lead-receiver

# 2. Check logs
sudo journalctl -u lead-receiver -n 100

# 3. Restart service
sudo systemctl restart lead-receiver

# 4. If still failing, check dependencies
systemctl status postgresql
systemctl status redis

# 5. Check database connectivity
psql -h localhost -U reviewsignal -d reviewsignal -c "SELECT 1;"

# 6. Manual start (for debugging)
cd /home/info_betsim/reviewsignal-5.0
python3 -m uvicorn api.lead_receiver:app --host 0.0.0.0 --port 8001

# 7. Check firewall
sudo ufw status
```

**Estimated Recovery Time:** 5-15 minutes

---

### Scenario 5: Out of Disk Space 💽

**Symptoms:**
- Services crashing
- Cannot write files
- Database errors

**Recovery Steps:**

```bash
# 1. Check disk usage
df -h

# 2. Find large files
sudo du -sh /* | sort -h | tail -20

# 3. Clear Docker logs
docker system prune -af --volumes

# 4. Clear old backups
find /home/info_betsim/backups -mtime +30 -delete

# 5. Clear old logs
sudo journalctl --vacuum-time=7d
find /home/info_betsim/reviewsignal-5.0/logs -name "*.log" -mtime +7 -delete

# 6. Clear PostgreSQL logs
sudo find /var/log/postgresql -name "*.log" -mtime +7 -delete

# 7. Restart services
sudo systemctl restart lead-receiver postgresql
docker restart n8n
```

**Estimated Recovery Time:** 15-30 minutes

---

### Scenario 6: Apollo API Key Revoked 🔑

**Symptoms:**
- Workflow executions failing
- 401/403 errors in n8n logs
- No new leads collected

**Recovery Steps:**

```bash
# 1. Get new API key from Apollo.io dashboard
# Visit: https://app.apollo.io/settings/integrations

# 2. Update n8n workflow
sudo sqlite3 /root/.n8n/database.sqlite

# In sqlite:
# UPDATE workflow_entity
# SET nodes = replace(nodes, 'OLD_API_KEY', 'NEW_API_KEY')
# WHERE id = 'C2kIA0mMISzcKnjC';

# 3. Restart n8n
docker restart n8n

# 4. Test workflow manually
# Open http://IP:5678 and execute workflow
```

**Estimated Recovery Time:** 10 minutes

---

## 4. DATA RECOVERY PRIORITIES

### Critical (Restore First)
1. **PostgreSQL Database** - Contains all leads and business data
2. **n8n Workflows** - Business automation logic
3. **Configuration Files** - API keys, credentials

### Important (Restore Second)
4. **Application Code** - Can be pulled from GitHub
5. **Logs** - For forensics and debugging

### Nice to Have
6. **Monitoring Data** - Can rebuild from scratch

---

## 5. PREVENTIVE MEASURES

### Daily
- ✅ Automated backups (2 AM UTC)
- ✅ Health checks (every 15 minutes)
- ✅ Log rotation

### Weekly
- [ ] Test backup restoration (Sundays)
- [ ] Review system metrics
- [ ] Update dependencies

### Monthly
- [ ] Full disaster recovery drill
- [ ] Security audit
- [ ] Capacity planning review

---

## 6. POST-INCIDENT CHECKLIST

After resolving any disaster:

- [ ] Document what happened
- [ ] Document what worked/didn't work
- [ ] Update recovery procedures
- [ ] Identify root cause
- [ ] Implement preventive measures
- [ ] Notify stakeholders
- [ ] Update runbooks
- [ ] Schedule post-mortem meeting

---

## 7. QUICK REFERENCE COMMANDS

```bash
# Check all services
systemctl status lead-receiver
docker ps | grep -E "n8n|prometheus|grafana"
sudo -u postgres psql -d reviewsignal -c "SELECT version();"

# View logs
sudo journalctl -u lead-receiver -f
docker logs -f n8n
tail -f /home/info_betsim/reviewsignal-5.0/logs/app.log

# Backup now
sudo /home/info_betsim/reviewsignal-5.0/scripts/backup_automation.sh

# Health check
curl http://localhost:8001/health
curl http://localhost:5678
```

---

## 8. ROLLBACK PROCEDURES

### Rollback Application Code
```bash
# Return to previous commit
cd /home/info_betsim/reviewsignal-5.0
git log --oneline | head -10
git checkout <PREVIOUS_COMMIT_HASH>
sudo systemctl restart lead-receiver
```

### Rollback Database
```bash
# Use backup from before change
cd /home/info_betsim/backups/database
gunzip < reviewsignal_YYYYMMDD_HHMMSS.sql.gz | sudo -u postgres psql reviewsignal
```

### Rollback n8n Workflows
```bash
# Use backup from before change
cd /home/info_betsim/backups/n8n
sudo gunzip -c n8n_YYYYMMDD_HHMMSS.sqlite.gz > /root/.n8n/database.sqlite
docker restart n8n
```

---

## 9. ESCALATION PATH

1. **Level 1:** Automated alerts → Slack
2. **Level 2:** Critical failures → Email team
3. **Level 3:** Extended outage → SMS/Call

**Critical Incident Threshold:**
- Services down > 15 minutes
- Data loss detected
- Security breach suspected

---

## 10. TESTING SCHEDULE

| Test Type | Frequency | Next Test |
|-----------|-----------|-----------|
| Backup restoration | Monthly | TBD |
| Failover drill | Quarterly | TBD |
| Full DR simulation | Annually | TBD |

---

**Document Owner:** System Administrator
**Review Schedule:** Quarterly
**Next Review:** 2026-04-30
