#!/bin/bash
#
# NEURAL CORE SETUP SCRIPT
# Installs MiniLM embeddings, configures services, and sets up cron jobs
#
# Usage: sudo ./scripts/setup_neural_core.sh
#
# Author: ReviewSignal Team
# Version: 5.1.0
# Date: February 2026

set -e

echo ""
echo "════════════════════════════════════════════════════════════════"
echo "  NEURAL CORE SETUP - ReviewSignal 5.1.0"
echo "════════════════════════════════════════════════════════════════"
echo ""

# Check if running as root or with sudo
if [[ $EUID -ne 0 ]]; then
   echo "  ⚠️  This script should be run with sudo"
   echo "  Usage: sudo ./scripts/setup_neural_core.sh"
   exit 1
fi

PROJECT_DIR="/home/info_betsim/reviewsignal-5.0"
VENV_DIR="$PROJECT_DIR/venv"
LOG_DIR="/var/log/reviewsignal"
USER="info_betsim"

# ─────────────────────────────────────────────────────────────
# Step 1: Install Python dependencies
# ─────────────────────────────────────────────────────────────
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  STEP 1: Installing Python dependencies"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Activate virtual environment
source "$VENV_DIR/bin/activate"

# Install sentence-transformers (includes torch)
echo "  Installing sentence-transformers (MiniLM)..."
pip install --quiet sentence-transformers==2.2.2

# Verify installation
python -c "from sentence_transformers import SentenceTransformer; print('  ✅ sentence-transformers installed')"

# Install other dependencies if missing
pip install --quiet prometheus-client redis structlog

echo "  ✅ Dependencies installed"
echo ""

# ─────────────────────────────────────────────────────────────
# Step 2: Create log directory
# ─────────────────────────────────────────────────────────────
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  STEP 2: Setting up log directory"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

mkdir -p "$LOG_DIR"
touch "$LOG_DIR/neural-api.log"
touch "$LOG_DIR/neural_refit.log"
chown -R "$USER:$USER" "$LOG_DIR"
chmod 755 "$LOG_DIR"

echo "  ✅ Log directory configured: $LOG_DIR"
echo ""

# ─────────────────────────────────────────────────────────────
# Step 3: Install systemd service
# ─────────────────────────────────────────────────────────────
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  STEP 3: Installing systemd service"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Copy service file
cp "$PROJECT_DIR/systemd/neural-api.service" /etc/systemd/system/

# Reload systemd
systemctl daemon-reload

# Enable service
systemctl enable neural-api

echo "  ✅ Systemd service installed and enabled"
echo ""

# ─────────────────────────────────────────────────────────────
# Step 4: Setup cron jobs
# ─────────────────────────────────────────────────────────────
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  STEP 4: Setting up cron jobs"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Make refit script executable
chmod +x "$PROJECT_DIR/scripts/weekly_neural_refit.py"

# Add cron job for weekly refit (Sunday 00:00 UTC)
CRON_JOB="0 0 * * 0 $VENV_DIR/bin/python $PROJECT_DIR/scripts/weekly_neural_refit.py >> $LOG_DIR/neural_refit.log 2>&1"

# Check if cron job already exists
(crontab -u "$USER" -l 2>/dev/null | grep -v "weekly_neural_refit" ; echo "$CRON_JOB") | crontab -u "$USER" -

echo "  ✅ Weekly refit cron job added (Sunday 00:00 UTC)"
echo ""

# ─────────────────────────────────────────────────────────────
# Step 5: Pre-download MiniLM model
# ─────────────────────────────────────────────────────────────
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  STEP 5: Pre-downloading MiniLM model"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Download model to cache
sudo -u "$USER" bash -c "cd $PROJECT_DIR && source $VENV_DIR/bin/activate && python -c \"
from sentence_transformers import SentenceTransformer
print('  Downloading all-MiniLM-L6-v2 model...')
model = SentenceTransformer('all-MiniLM-L6-v2')
test = model.encode('test')
print(f'  ✅ Model downloaded and verified (embedding shape: {test.shape})')
\""

echo ""

# ─────────────────────────────────────────────────────────────
# Step 6: Start service
# ─────────────────────────────────────────────────────────────
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  STEP 6: Starting Neural API service"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

systemctl start neural-api
sleep 3

# Check status
if systemctl is-active --quiet neural-api; then
    echo "  ✅ Neural API is running on port 8005"
else
    echo "  ⚠️  Neural API failed to start. Check logs:"
    echo "  sudo journalctl -u neural-api -n 50"
fi

echo ""

# ─────────────────────────────────────────────────────────────
# Step 7: Verify installation
# ─────────────────────────────────────────────────────────────
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  STEP 7: Verification"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Test API endpoint
sleep 2
if curl -s http://localhost:8005/health > /dev/null 2>&1; then
    echo "  ✅ API health check passed"

    # Test embedding endpoint
    RESPONSE=$(curl -s -X POST http://localhost:8005/api/neural/embed \
        -H "Content-Type: application/json" \
        -d '{"text": "test embedding"}')

    if echo "$RESPONSE" | grep -q "embedding"; then
        echo "  ✅ Embedding endpoint working"
    else
        echo "  ⚠️  Embedding endpoint not responding correctly"
    fi
else
    echo "  ⚠️  API not responding. Service may still be starting..."
fi

echo ""

# ─────────────────────────────────────────────────────────────
# Summary
# ─────────────────────────────────────────────────────────────
echo "════════════════════════════════════════════════════════════════"
echo "  NEURAL CORE SETUP COMPLETE"
echo "════════════════════════════════════════════════════════════════"
echo ""
echo "  Components installed:"
echo "  ├── sentence-transformers (MiniLM, 80MB)"
echo "  ├── Neural API service (port 8005)"
echo "  ├── Weekly refit cron (Sunday 00:00 UTC)"
echo "  └── Echo-Neural Bridge"
echo ""
echo "  Services:"
echo "  ├── neural-api.service → systemctl status neural-api"
echo "  └── Logs → /var/log/reviewsignal/neural-api.log"
echo ""
echo "  API Endpoints:"
echo "  ├── http://localhost:8005/health"
echo "  ├── http://localhost:8005/api/neural/embed"
echo "  ├── http://localhost:8005/api/neural/stats/update"
echo "  └── http://localhost:8005/api/neural/anomaly/check"
echo ""
echo "  Quick Test:"
echo "  curl http://localhost:8005/api/neural/health"
echo ""
echo "════════════════════════════════════════════════════════════════"
