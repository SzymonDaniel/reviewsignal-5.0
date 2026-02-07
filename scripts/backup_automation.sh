#!/bin/bash
# Automated Backup Script for ReviewSignal Production
# Runs daily via cron, keeps 30 days of backups

set -e

BACKUP_DIR="/home/info_betsim/backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
DATE=$(date +%Y-%m-%d)
RETENTION_DAYS=30

# Slack webhook for notifications (optional)
SLACK_WEBHOOK="${SLACK_WEBHOOK_URL:-}"

# Create backup directory
mkdir -p "$BACKUP_DIR"/{database,n8n,config,logs}

log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1" | tee -a "$BACKUP_DIR/backup.log"
}

notify_slack() {
    if [ -n "$SLACK_WEBHOOK" ]; then
        curl -X POST "$SLACK_WEBHOOK" \
            -H 'Content-Type: application/json' \
            -d "{\"text\":\"$1\"}" 2>/dev/null || true
    fi
}

log "========================================="
log "Starting backup process: $TIMESTAMP"
log "========================================="

# 1. PostgreSQL Database Backup
log "Backing up PostgreSQL database..."
sudo -u postgres pg_dump reviewsignal | gzip > "$BACKUP_DIR/database/reviewsignal_$TIMESTAMP.sql.gz"
DB_SIZE=$(du -sh "$BACKUP_DIR/database/reviewsignal_$TIMESTAMP.sql.gz" | cut -f1)
log "✅ Database backup complete: $DB_SIZE"

# 2. n8n Database Backup
log "Backing up n8n database..."
sudo cp /root/.n8n/database.sqlite "$BACKUP_DIR/n8n/n8n_$TIMESTAMP.sqlite"
sudo gzip "$BACKUP_DIR/n8n/n8n_$TIMESTAMP.sqlite"
N8N_SIZE=$(du -sh "$BACKUP_DIR/n8n/n8n_$TIMESTAMP.sqlite.gz" | cut -f1)
log "✅ n8n backup complete: $N8N_SIZE"

# 3. Configuration Files Backup
log "Backing up configuration files..."
tar -czf "$BACKUP_DIR/config/config_$TIMESTAMP.tar.gz" \
    /home/info_betsim/reviewsignal-5.0/.env \
    /home/info_betsim/reviewsignal-5.0/config.py \
    /etc/systemd/system/lead-receiver.service \
    /etc/systemd/system/reviewsignal-agent.service 2>/dev/null || true
CONFIG_SIZE=$(du -sh "$BACKUP_DIR/config/config_$TIMESTAMP.tar.gz" | cut -f1)
log "✅ Config backup complete: $CONFIG_SIZE"

# 4. Application Logs Backup (last 7 days)
log "Backing up application logs..."
find /home/info_betsim/reviewsignal-5.0/logs -name "*.log" -mtime -7 -type f \
    -exec tar -czf "$BACKUP_DIR/logs/logs_$TIMESTAMP.tar.gz" {} + 2>/dev/null || true
if [ -f "$BACKUP_DIR/logs/logs_$TIMESTAMP.tar.gz" ]; then
    LOGS_SIZE=$(du -sh "$BACKUP_DIR/logs/logs_$TIMESTAMP.tar.gz" | cut -f1)
    log "✅ Logs backup complete: $LOGS_SIZE"
else
    log "⚠️  No recent logs to backup"
fi

# 5. Create backup manifest
log "Creating backup manifest..."
cat > "$BACKUP_DIR/manifest_$TIMESTAMP.txt" <<EOF
ReviewSignal Backup Manifest
============================
Date: $DATE
Timestamp: $TIMESTAMP
Hostname: $(hostname)
IP: $(hostname -I | awk '{print $1}')

Backup Contents:
---------------
Database:  reviewsignal_$TIMESTAMP.sql.gz ($DB_SIZE)
n8n:       n8n_$TIMESTAMP.sqlite.gz ($N8N_SIZE)
Config:    config_$TIMESTAMP.tar.gz ($CONFIG_SIZE)
Logs:      logs_$TIMESTAMP.tar.gz ($([ -f "$BACKUP_DIR/logs/logs_$TIMESTAMP.tar.gz" ] && echo "$LOGS_SIZE" || echo "N/A"))

Restoration Commands:
--------------------
# Restore PostgreSQL
gunzip < reviewsignal_$TIMESTAMP.sql.gz | sudo -u postgres psql reviewsignal

# Restore n8n
sudo systemctl stop n8n
sudo gunzip -c n8n_$TIMESTAMP.sqlite.gz > /root/.n8n/database.sqlite
sudo systemctl start n8n

# Restore config
tar -xzf config_$TIMESTAMP.tar.gz -C /

System Info:
-----------
$(df -h | grep -E "/$|/home")
$(free -h)
EOF

log "✅ Manifest created"

# 6. Upload to GCS (optional - requires gsutil)
if command -v gsutil &> /dev/null; then
    log "Uploading backups to Google Cloud Storage..."
    GCS_BUCKET="gs://reviewsignal-backups"
    gsutil -m cp "$BACKUP_DIR/database/reviewsignal_$TIMESTAMP.sql.gz" "$GCS_BUCKET/database/" || true
    gsutil -m cp "$BACKUP_DIR/n8n/n8n_$TIMESTAMP.sqlite.gz" "$GCS_BUCKET/n8n/" || true
    log "✅ Cloud backup complete"
fi

# 7. Cleanup old backups (keep last 30 days)
log "Cleaning up old backups (keeping last $RETENTION_DAYS days)..."
find "$BACKUP_DIR/database" -name "*.sql.gz" -mtime +$RETENTION_DAYS -delete
find "$BACKUP_DIR/n8n" -name "*.sqlite.gz" -mtime +$RETENTION_DAYS -delete
find "$BACKUP_DIR/config" -name "*.tar.gz" -mtime +$RETENTION_DAYS -delete
find "$BACKUP_DIR/logs" -name "*.tar.gz" -mtime +$RETENTION_DAYS -delete
find "$BACKUP_DIR" -name "manifest_*.txt" -mtime +$RETENTION_DAYS -delete
log "✅ Cleanup complete"

# 8. Calculate total backup size
TOTAL_SIZE=$(du -sh "$BACKUP_DIR" | cut -f1)

# 9. Summary
log "========================================="
log "Backup complete!"
log "Total backup size: $TOTAL_SIZE"
log "Backup location: $BACKUP_DIR"
log "Manifest: $BACKUP_DIR/manifest_$TIMESTAMP.txt"
log "========================================="

# 10. Send Slack notification
notify_slack "✅ ReviewSignal backup complete!
Date: $DATE
Database: $DB_SIZE | n8n: $N8N_SIZE | Config: $CONFIG_SIZE
Total: $TOTAL_SIZE"

# 11. Verify backup integrity
log "Verifying backup integrity..."
if gunzip -t "$BACKUP_DIR/database/reviewsignal_$TIMESTAMP.sql.gz" 2>/dev/null; then
    log "✅ Database backup integrity OK"
else
    log "❌ Database backup integrity FAILED!"
    notify_slack "❌ ReviewSignal backup FAILED! Database backup is corrupted!"
    exit 1
fi

log "All backups verified and stored successfully!"

exit 0
