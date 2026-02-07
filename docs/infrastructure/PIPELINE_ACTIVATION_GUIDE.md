# PIPELINE ACTIVATION GUIDE
## Apollo → n8n → PostgreSQL → Instantly

**Created:** 2026-01-30 19:00 UTC
**Status:** Ready for activation
**Estimated Time:** 30 minutes

---

## 📋 PRE-ACTIVATION CHECKLIST

### ✅ Systems Ready
- [x] n8n: Running and healthy
- [x] Lead Receiver API: Active (port 8001)
- [x] PostgreSQL: 37 leads in database
- [x] Instantly: Account active
- [x] Apollo: API key configured
- [x] Email templates: Created (4 templates)

### ✅ Tests Passed
- [x] Lead Receiver: Test lead saved (ID 72)
- [x] Instantly sync: Working (instantly_synced=true)
- [x] Database: Unique constraint verified
- [x] API endpoints: All responding

---

## 🚀 STEP 1: Activate Apollo Workflow in n8n

### 1.1 Access n8n Dashboard
```
URL: http://35.246.214.156:5678
Credentials: [Your n8n login]
```

### 1.2 Open Apollo Workflow
1. Navigate to "Workflows" in left sidebar
2. Find "FLOW 7 - Apollo to PostgreSQL"
3. Click to open workflow

### 1.3 Verify Workflow Configuration

**Check these nodes:**

**Node 1: Schedule Trigger**
- Trigger: Every 6 hours
- Status: Should show schedule

**Node 2: Apollo Search**
- URL: https://api.apollo.io/v1/mixed_people/search
- Method: POST
- Headers: `api_key: koTQfXNe_OM599OsEpyEbA`
- Body:
```json
{
  "person_titles": ["Portfolio Manager", "Investment Analyst", "Head of Alternative Data"],
  "person_locations": ["United States", "United Kingdom"],
  "organization_num_employees_ranges": ["201,500", "501,1000"],
  "per_page": 25
}
```

**Node 3: Split People**
- Input: `{{ $json.people }}`
- Splits array into individual leads

**Node 4: Enrich Lead (Apollo /people/match)**
- URL: https://api.apollo.io/v1/people/match
- Method: POST
- Body:
```json
{
  "email": "{{ $json.email }}",
  "first_name": "{{ $json.first_name }}",
  "last_name": "{{ $json.last_name }}"
}
```

**Node 5: Save to Database**
- URL: http://localhost:8001/api/lead
- Method: POST
- Body:
```json
{
  "email": "{{ $json.email }}",
  "first_name": "{{ $json.first_name }}",
  "last_name": "{{ $json.last_name }}",
  "title": "{{ $json.title }}",
  "company": "{{ $json.organization.name }}",
  "company_domain": "{{ $json.organization.website_url }}",
  "industry": "{{ $json.organization.industry }}",
  "linkedin_url": "{{ $json.linkedin_url }}"
}
```

### 1.4 Test Workflow
1. Click "Execute Workflow" button (top right)
2. Watch nodes execute (should turn green)
3. Check "Executions" tab for results
4. Verify no errors

### 1.5 Activate Workflow
1. Toggle "Inactive" → "Active" (top right)
2. Confirm activation
3. Workflow will now run every 6 hours automatically

**Expected result:** Green "Active" badge on workflow

---

## 🚀 STEP 2: Setup Instantly Campaign

### 2.1 Access Instantly Dashboard
```
URL: https://app.instantly.ai
Login: [Your Instantly credentials]
```

### 2.2 Check Domain Warmup Status

1. Navigate to "Warmup" in left sidebar
2. Check each domain:

| Domain | Current % | Target % | Status |
|--------|-----------|----------|--------|
| reviewsignal.cc | ? | 70%+ | Check |
| reviewsignal.net | ? | 70%+ | Check |
| reviewsignal.org | ? | 70%+ | Check |

**If warmup < 50%:** Wait 1-2 more weeks before sending emails
**If warmup > 50%:** Can send 10-20 emails/day
**If warmup > 70%:** Can send 50-100 emails/day

### 2.3 Create New Campaign

1. Click "Campaigns" → "Create Campaign"
2. **Campaign Name:** "ReviewSignal - Hedge Funds Q1 2026"
3. **Campaign Type:** "Cold Email Sequence"
4. **Schedule:**
   - Days: Monday - Friday
   - Time: 9:00 AM - 6:00 PM EST
   - Max emails/day: 20 (start conservative)
   - Timezone: America/New_York

### 2.4 Import Email Templates

**Email 1: Initial Outreach (Day 0)**
```
Subject: Alternative data signal for {{company}}

[Copy from /home/info_betsim/reviewsignal-5.0/email_templates/01_initial_outreach.txt]
```

**Email 2: Case Study (Day 3)**
```
Subject: Case study: Predicting retail earnings with review data

[Copy from 02_followup_case_study.txt]
```

**Email 3: Demo Offer (Day 7)**
```
Subject: 15-min demo - ReviewSignal for {{company}}

[Copy from 03_followup_demo_offer.txt]
```

**Email 4: Breakup (Day 14)**
```
Subject: Closing your file

[Copy from 04_breakup_final.txt]
```

### 2.5 Configure Variables

Map Instantly variables to your fields:
- `{{first_name}}` → First Name column
- `{{company}}` → Company column
- `{{chain}}` → Custom field (default: "McDonald's")

### 2.6 Set Email Delays

- Email 1: Send immediately
- Email 2: Wait 3 days (only if no reply)
- Email 3: Wait 7 days (only if no reply)
- Email 4: Wait 14 days (only if no reply)

### 2.7 Add Sending Accounts

1. Go to "Settings" → "Sending Accounts"
2. Connect warmed domains:
   - reviewsignal.cc
   - reviewsignal.net
   - (Add more as they warm up)
3. Set rotation: Round-robin
4. Set daily limit: 20 emails/account

### 2.8 Save Campaign (Don't Activate Yet!)

**Important:** Save but DON'T activate until domains are 70%+ warmed

---

## 🚀 STEP 3: Import Leads to Instantly

### Option A: Manual CSV Import (Quick Start)

1. Export leads from database:
```bash
psql -d reviewsignal -c "
  COPY (
    SELECT
      email,
      SPLIT_PART(name, ' ', 1) as first_name,
      SPLIT_PART(name, ' ', 2) as last_name,
      company,
      title,
      linkedin_url
    FROM leads
    WHERE status = 'new'
    ORDER BY created_at DESC
    LIMIT 100
  ) TO STDOUT WITH CSV HEADER
" > /tmp/leads_export.csv
```

2. In Instantly:
   - Campaigns → Select your campaign
   - "Add Leads" → "Import CSV"
   - Upload `/tmp/leads_export.csv`
   - Map columns to fields
   - Import

### Option B: API Sync (Automated - Already Working!)

Lead Receiver API automatically syncs leads to Instantly when they're added.

**Verify it's working:**
```bash
# Check sync status
curl http://localhost:8001/api/stats
# Expected: "sent_to_instantly" should increase as leads are added
```

**How it works:**
1. n8n receives lead from Apollo
2. Saves to PostgreSQL via Lead Receiver API
3. Lead Receiver automatically calls Instantly API
4. Lead appears in your Instantly campaign
5. Campaign sends emails based on schedule

---

## 🚀 STEP 4: Activate Campaign (When Ready)

### 4.1 Final Checklist

- [ ] Domain warmup > 70%
- [ ] Email templates imported
- [ ] Variables configured
- [ ] Sending accounts connected
- [ ] Schedule configured (Mon-Fri, 9-6 EST)
- [ ] Daily limit set (20/day to start)
- [ ] Leads imported (at least 50)

### 4.2 Activate

1. Go to Campaigns → Your campaign
2. Click "Activate Campaign"
3. Confirm activation
4. Monitor first 24 hours closely

### 4.3 Expected Results

**Day 1:**
- 20 emails sent
- 6-8 opens (30-40% open rate)
- 1-2 replies (5-10% reply rate)

**Week 1:**
- 100 emails sent (20/day × 5 days)
- 30-40 opens
- 5-10 replies
- 1-2 demo bookings

**Month 1:**
- 400 emails sent
- 120-160 opens
- 20-40 replies
- 4-8 demos
- 1-2 pilot customers

---

## 📊 MONITORING & OPTIMIZATION

### Daily Checks (5 minutes)

```bash
# 1. Check Apollo workflow ran
# In n8n UI: Check "Executions" tab for latest run

# 2. Check new leads in database
psql -d reviewsignal -c "
  SELECT COUNT(*) as new_leads_today
  FROM leads
  WHERE DATE(created_at) = CURRENT_DATE;
"

# 3. Check Instantly stats
# In Instantly UI: Dashboard → Campaign stats
```

### Weekly Review (30 minutes)

**Metrics to track:**
1. **Apollo Performance:**
   - Leads found per run
   - Enrichment success rate
   - Database save rate

2. **Instantly Performance:**
   - Open rate (target: 35%+)
   - Reply rate (target: 8%+)
   - Bounce rate (target: <2%)
   - Unsubscribe rate (target: <0.5%)

3. **Pipeline Health:**
   - n8n uptime
   - Lead Receiver errors
   - Database growth

### Optimization Actions

**If open rate < 25%:**
- Test new subject lines
- Check spam score (use mail-tester.com)
- Verify domain warmup

**If reply rate < 5%:**
- Test shorter emails
- Add more personalization
- Improve value proposition

**If bounce rate > 2%:**
- Verify Apollo data quality
- Use email validation service
- Clean email list

---

## 🔧 TROUBLESHOOTING

### Problem: Apollo workflow not running

**Solution:**
```bash
# Check n8n logs
docker logs n8n --tail 100

# Check workflow is active in n8n UI
# Check schedule trigger is configured correctly
```

### Problem: Leads not saving to database

**Solution:**
```bash
# Test Lead Receiver manually
curl -X POST http://localhost:8001/api/lead \
  -H "Content-Type: application/json" \
  -d '{"email":"test@test.com","first_name":"Test","last_name":"User","company":"Test Co"}'

# Check Lead Receiver logs
sudo journalctl -u lead-receiver -n 50

# Restart if needed
sudo systemctl restart lead-receiver
```

### Problem: Leads not syncing to Instantly

**Solution:**
```bash
# Check Instantly API key
echo $INSTANTLY_API_KEY

# Check campaign ID
echo $INSTANTLY_CAMPAIGN_ID

# Test Instantly API manually
curl -X POST "https://api.instantly.ai/api/v2/lead/add" \
  -H "Authorization: Bearer $INSTANTLY_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "campaign_id": "'$INSTANTLY_CAMPAIGN_ID'",
    "email": "test@example.com",
    "first_name": "Test",
    "last_name": "User"
  }'
```

### Problem: Emails going to spam

**Solution:**
1. Check domain warmup (must be 70%+)
2. Reduce daily sending volume
3. Test email with mail-tester.com
4. Add SPF, DKIM, DMARC records to DNS
5. Avoid spam trigger words ("free", "urgent", "limited time")

---

## ✅ SUCCESS METRICS

### Week 1 Goals
- [ ] Apollo workflow running successfully (4 runs)
- [ ] 100+ new leads in database
- [ ] 50+ leads in Instantly campaign
- [ ] 100 emails sent (if domains ready)
- [ ] 30+ email opens
- [ ] 5+ replies
- [ ] 1 demo booked

### Month 1 Goals
- [ ] 1,000+ leads collected
- [ ] 400 emails sent
- [ ] 120+ opens (30% open rate)
- [ ] 20+ replies (5% reply rate)
- [ ] 4-8 demos booked
- [ ] 1-2 pilot customers signed

### Quarter 1 Goals (Week 12)
- [ ] 5,000+ leads collected
- [ ] 2,000 emails sent
- [ ] 600+ opens
- [ ] 100+ replies
- [ ] 20+ demos
- [ ] **5 customers @ €2,500/mo = €12.5k MRR** ✅

---

## 📝 ACTIVATION COMMANDS (Quick Reference)

```bash
# Check systems health
curl http://localhost:5678/healthz              # n8n
curl http://localhost:8001/health               # Lead Receiver
psql -d reviewsignal -c "SELECT COUNT(*) FROM leads;"  # Database

# Monitor leads
watch -n 60 'psql -d reviewsignal -c "SELECT COUNT(*) FROM leads;"'

# Export leads for Instantly
psql -d reviewsignal -c "
  COPY (SELECT email, SPLIT_PART(name, ' ', 1) as first_name, company
        FROM leads WHERE status='new' LIMIT 100)
  TO STDOUT WITH CSV HEADER
" > /tmp/leads_export.csv

# Check Instantly sync status
curl http://localhost:8001/api/stats | jq
```

---

## 🎯 EXPECTED OUTCOME

**After full activation:**

1. **Apollo workflow:** Finds 25-50 new leads every 6 hours
2. **n8n:** Enriches and saves to database automatically
3. **Lead Receiver:** Syncs to Instantly automatically
4. **Instantly:** Sends emails based on schedule
5. **Replies:** Come to your connected email inbox
6. **Demos:** Booked via calendar link in emails
7. **Customers:** Converted from successful demos

**Result:** Fully automated lead generation → nurture → booking pipeline

**ROI:** €12.5k MRR by Week 12 (5 customers @ €2,500/mo)

---

**Status:** Ready for activation
**Next step:** Check domain warmup in Instantly dashboard
**If warmup > 70%:** Activate campaign today
**If warmup < 70%:** Wait 1-2 weeks, activate February

---

*Created: 2026-01-30 19:00 UTC*
*Last Updated: 2026-01-30 19:00 UTC*
*Author: Claude (ReviewSignal Team)*
