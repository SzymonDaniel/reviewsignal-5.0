# STRIPE WEBHOOK SETUP GUIDE

**Created:** 2026-01-31
**Status:** Ready for deployment
**Author:** ReviewSignal Team

---

## 📋 Overview

This guide explains how to set up the Stripe webhook handler for ReviewSignal.ai. The webhook listens for payment events from Stripe and automatically updates user subscriptions in the database.

## 🔧 Components

### 1. Webhook API
- **File:** `/home/info_betsim/reviewsignal-5.0/api/stripe_webhook.py`
- **Port:** 8002
- **Framework:** FastAPI + Uvicorn

### 2. Supported Events
- `payment_intent.succeeded` - Payment completed
- `payment_intent.payment_failed` - Payment failed
- `customer.subscription.created` - New subscription
- `customer.subscription.updated` - Subscription changed
- `customer.subscription.deleted` - Subscription cancelled
- `invoice.paid` - Invoice paid
- `invoice.payment_failed` - Invoice payment failed

---

## 🚀 Installation Steps

### Step 1: Configure Stripe Keys

Edit `/home/info_betsim/reviewsignal-5.0/.env` and add your Stripe keys:

```bash
# Get keys from: https://dashboard.stripe.com/apikeys
STRIPE_API_KEY=sk_test_YOUR_TEST_KEY
STRIPE_WEBHOOK_SECRET=whsec_YOUR_WEBHOOK_SECRET
STRIPE_PUBLISHABLE_KEY=pk_test_YOUR_PUBLISHABLE_KEY
```

**How to get webhook secret:**
1. Go to https://dashboard.stripe.com/test/webhooks
2. Click "Add endpoint"
3. URL: `https://api.reviewsignal.ai/webhook/stripe`
4. Events to listen: Select all payment and subscription events
5. Copy the "Signing secret" (starts with `whsec_`)

### Step 2: Create systemd service

Create `/etc/systemd/system/stripe-webhook.service`:

```bash
sudo nano /etc/systemd/system/stripe-webhook.service
```

Add the following:

```ini
[Unit]
Description=ReviewSignal Stripe Webhook API
After=network.target postgresql.service redis.service

[Service]
Type=simple
User=info_betsim
WorkingDirectory=/home/info_betsim/reviewsignal-5.0
Environment="PATH=/usr/local/bin:/usr/bin:/bin"
Environment="DB_HOST=localhost"
Environment="DB_PORT=5432"
Environment="DB_NAME=reviewsignal"
Environment="DB_USER=reviewsignal"
Environment="DB_PASS=<REDACTED>"
Environment="STRIPE_API_KEY=sk_test_YOUR_KEY_HERE"
Environment="STRIPE_WEBHOOK_SECRET=whsec_YOUR_SECRET_HERE"

ExecStart=/usr/bin/python3 -m uvicorn api.stripe_webhook:app --host 0.0.0.0 --port 8002

Restart=always
RestartSec=10
StandardOutput=append:/home/info_betsim/reviewsignal-5.0/logs/stripe-webhook.log
StandardError=append:/home/info_betsim/reviewsignal-5.0/logs/stripe-webhook-error.log

[Install]
WantedBy=multi-user.target
```

### Step 3: Enable and start service

```bash
# Reload systemd
sudo systemctl daemon-reload

# Enable service (start on boot)
sudo systemctl enable stripe-webhook

# Start service now
sudo systemctl start stripe-webhook

# Check status
sudo systemctl status stripe-webhook
```

### Step 4: Verify service is running

```bash
# Check if running
curl http://localhost:8002/health

# Expected response:
# {
#   "status": "ok",
#   "service": "stripe_webhook",
#   "stripe_configured": true
# }
```

---

## 🌐 Nginx Configuration (Production)

Add webhook endpoint to nginx config:

```nginx
# In /etc/nginx/sites-available/reviewsignal

server {
    listen 443 ssl http2;
    server_name api.reviewsignal.ai;

    # Existing SSL config...

    # Stripe Webhook (NO AUTHENTICATION!)
    location /webhook/stripe {
        proxy_pass http://localhost:8002/webhook/stripe;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Important: No rate limiting for Stripe webhooks
        limit_req zone=api_limit burst=100 nodelay;
    }

    # Protected endpoints (require auth)
    location /webhook/events {
        proxy_pass http://localhost:8002/webhook/events;
        # Add authentication here
    }

    location /webhook/stats {
        proxy_pass http://localhost:8002/webhook/stats;
        # Add authentication here
    }
}
```

Reload nginx:
```bash
sudo nginx -t
sudo systemctl reload nginx
```

---

## 🧪 Testing

### Test 1: Local webhook endpoint

```bash
# Check if service is running
curl http://localhost:8002/health

# Test webhook events log (should be empty initially)
curl http://localhost:8002/webhook/events

# Check stats
curl http://localhost:8002/webhook/stats
```

### Test 2: Stripe CLI (recommended for testing)

Install Stripe CLI:
```bash
# Install
wget https://github.com/stripe/stripe-cli/releases/download/v1.19.4/stripe_1.19.4_linux_x86_64.tar.gz
tar -xvf stripe_1.19.4_linux_x86_64.tar.gz
sudo mv stripe /usr/local/bin/

# Login
stripe login

# Forward webhooks to local endpoint
stripe listen --forward-to localhost:8002/webhook/stripe
```

Trigger test events:
```bash
# Test payment success
stripe trigger payment_intent.succeeded

# Test subscription created
stripe trigger customer.subscription.created

# Test invoice paid
stripe trigger invoice.paid
```

### Test 3: Stripe Dashboard

1. Go to https://dashboard.stripe.com/test/webhooks
2. Select your webhook endpoint
3. Click "Send test webhook"
4. Select event type (e.g., `payment_intent.succeeded`)
5. Click "Send test webhook"
6. Check logs: `sudo journalctl -u stripe-webhook -n 50`

---

## 📊 Monitoring

### View logs
```bash
# Live logs
sudo journalctl -u stripe-webhook -f

# Last 100 lines
sudo journalctl -u stripe-webhook -n 100

# Error logs only
tail -50 /home/info_betsim/reviewsignal-5.0/logs/stripe-webhook-error.log
```

### Check webhook events in database
```bash
# Connect to database
sudo -u postgres psql -d reviewsignal

# View recent events
SELECT event_id, event_type, customer_id, status, created_at
FROM webhook_events
ORDER BY created_at DESC
LIMIT 10;

# Count events by type
SELECT event_type, COUNT(*) as count
FROM webhook_events
GROUP BY event_type
ORDER BY count DESC;
```

### API endpoints
```bash
# Recent events
curl http://localhost:8002/webhook/events?limit=20

# Events by type
curl http://localhost:8002/webhook/events?event_type=payment_intent.succeeded

# Statistics
curl http://localhost:8002/webhook/stats
```

---

## 🔐 Security Notes

### Important:
1. **Webhook signature verification** - Always enabled, Stripe verifies all incoming webhooks
2. **HTTPS required** - Stripe only sends webhooks to HTTPS endpoints in production
3. **IP allowlisting** (optional) - Stripe webhook IPs: https://stripe.com/docs/ips
4. **No authentication on webhook endpoint** - Stripe uses signature verification instead
5. **Protect other endpoints** - `/webhook/events` and `/webhook/stats` should require authentication

### Stripe signature verification
The webhook handler automatically verifies signatures using `STRIPE_WEBHOOK_SECRET`:
- If signature is invalid, webhook is rejected with 400 error
- Events are logged to `webhook_events` table after verification
- Duplicate events (same `event_id`) are automatically handled

---

## 🔄 What happens when webhook is received?

### 1. Webhook arrives at endpoint
```
POST https://api.reviewsignal.ai/webhook/stripe
Header: Stripe-Signature: t=xxx,v1=yyy
Body: { "id": "evt_xxx", "type": "payment_intent.succeeded", ... }
```

### 2. Signature verification
- Webhook secret validates the request came from Stripe
- Invalid signatures are rejected immediately

### 3. Event processing
- Event is logged to `webhook_events` table
- Event type determines action:
  - Payment success → Record in `payments` table
  - Subscription created → Update `users.subscription_tier` and `subscriptions` table
  - Subscription cancelled → Mark subscription as cancelled

### 4. Database updates
- User subscription status updated
- Payment records created
- Reports can be triggered (future feature)

---

## 📝 Database Schema

### webhook_events table
```sql
CREATE TABLE webhook_events (
    id SERIAL PRIMARY KEY,
    event_id VARCHAR(255) UNIQUE NOT NULL,
    event_type VARCHAR(100) NOT NULL,
    customer_id VARCHAR(255),
    subscription_id VARCHAR(255),
    payment_id VARCHAR(255),
    amount INTEGER,
    status VARCHAR(50),
    data JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    processed_at TIMESTAMP DEFAULT NOW()
);
```

This table is **automatically created** on first webhook event.

---

## 🐛 Troubleshooting

### Service won't start
```bash
# Check service status
sudo systemctl status stripe-webhook

# Check logs for errors
sudo journalctl -u stripe-webhook -n 50

# Common issues:
# 1. Port 8002 already in use: netstat -tulpn | grep 8002
# 2. Missing environment variables: check .env file
# 3. Database connection failed: check PostgreSQL is running
```

### Webhooks not arriving
```bash
# 1. Check nginx is proxying correctly
curl https://api.reviewsignal.ai/webhook/stripe

# 2. Check Stripe webhook endpoint in dashboard
# Go to: https://dashboard.stripe.com/test/webhooks
# Verify URL matches: https://api.reviewsignal.ai/webhook/stripe

# 3. Check firewall allows Stripe IPs
# Stripe IPs: https://stripe.com/docs/ips
```

### Events not being processed
```bash
# Check database connection
cd /tmp && sudo -u postgres psql -d reviewsignal -c "SELECT COUNT(*) FROM webhook_events;"

# Check if events are logged but not processed
curl http://localhost:8002/webhook/events | jq

# Check processing errors in logs
sudo journalctl -u stripe-webhook | grep ERROR
```

---

## 📚 Resources

- Stripe Webhooks Documentation: https://stripe.com/docs/webhooks
- Stripe CLI: https://stripe.com/docs/stripe-cli
- Stripe Test Cards: https://stripe.com/docs/testing
- Stripe Event Types: https://stripe.com/docs/api/events/types

---

## ✅ Checklist

- [ ] Stripe API keys configured in .env
- [ ] Webhook secret obtained from Stripe dashboard
- [ ] systemd service created and started
- [ ] Service running on port 8002
- [ ] Nginx configured to proxy webhook endpoint
- [ ] Tested with Stripe CLI
- [ ] Webhook endpoint registered in Stripe dashboard
- [ ] Database table `webhook_events` created
- [ ] Logs are working

---

**Last updated:** 2026-01-31
**Status:** Ready for deployment
