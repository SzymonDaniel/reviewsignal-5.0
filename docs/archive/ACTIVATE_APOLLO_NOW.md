# 🚀 ACTIVATE APOLLO WORKFLOW NOW

**Date:** 2026-01-30
**Status:** READY TO ACTIVATE
**Goal:** Collect 500-1,000 leads while domains warm up (2 weeks)

---

## 📋 QUICK ACTIVATION STEPS

### 1. Access n8n Dashboard

```
URL: http://35.246.214.156:5678
```

- Open in browser
- Login if required
- Navigate to "Workflows" tab

### 2. Find Apollo Workflow

**Workflow name:** `FLOW 7 - Apollo to PostgreSQL`

Alternative names to look for:
- "Apollo Integration"
- "Apollo Lead Collection"
- "Apollo to DB"

### 3. Activate the Workflow

1. Click on the workflow name
2. Look for the **toggle switch** (usually top-right)
3. Switch from "Inactive" to **"Active"** ✅
4. Confirm activation if prompted

### 4. Verify It's Running

Check for:
- ✅ Green "Active" status badge
- ✅ Toggle switch is ON
- ✅ No error messages
- ✅ Execution log shows activity

---

## ⚙️ APOLLO WORKFLOW CONFIGURATION

### Current Settings (Should Already Be Configured)

**Apollo API:**
- Endpoint: Apollo.io API
- Authentication: API key stored in n8n credentials
- Rate limit: Respects Apollo limits

**Search Criteria:**
- Industry: SaaS, E-commerce, Digital Marketing
- Company size: 10-500 employees
- Location: EU, UK, US
- Job titles: CEO, Founder, Marketing Director, Head of Growth

**Output:**
- Database: PostgreSQL (reviewsignal)
- Table: `leads` or `apollo_leads`
- Fields: name, email, company, title, linkedin_url, etc.

**Schedule:**
- Frequency: Every 2 hours (or as configured)
- Batch size: 25-50 leads per run
- Daily target: ~30-50 new leads

### Expected Results (Over 2 Weeks)

```
Day 1-7:  ~250 leads collected
Day 8-14: ~500 leads total
Day 15+:  ~1,000 leads ready for Feb 14 launch
```

---

## 🔍 VERIFY DATA IS FLOWING

### Option 1: Check n8n Executions

1. In n8n, go to "Executions" tab
2. Look for recent runs of Apollo workflow
3. Click on execution to see results
4. Verify leads were added successfully

### Option 2: Check PostgreSQL Database

```bash
# Connect to database
docker exec -it reviewsignal_postgres psql -U reviewsignal -d reviewsignal

# Check lead count
SELECT COUNT(*) FROM leads WHERE source = 'apollo';

# View recent leads
SELECT name, email, company, created_at
FROM leads
WHERE source = 'apollo'
ORDER BY created_at DESC
LIMIT 10;

# Exit
\q
```

### Option 3: Check n8n Logs

```bash
# If n8n is running in Docker
docker logs reviewsignal_n8n --tail 50 --follow

# Look for successful executions
# Should see: "Apollo workflow executed successfully"
```

---

## ⚠️ TROUBLESHOOTING

### Workflow Not Starting

**Problem:** Toggle is ON but no executions

**Solutions:**
1. Check Apollo API credentials in n8n
2. Verify API key is valid (test in Apollo.io)
3. Check n8n logs for errors
4. Try manual execution (click "Execute Workflow")

### No Leads Being Collected

**Problem:** Workflow runs but no data in database

**Solutions:**
1. Check Apollo search criteria (might be too narrow)
2. Verify database connection in n8n
3. Check PostgreSQL table exists
4. Review execution logs for specific errors

### Apollo API Rate Limit

**Problem:** "Rate limit exceeded" errors

**Solutions:**
1. Reduce execution frequency (every 3-4 hours instead of 2)
2. Reduce batch size (25 leads per run instead of 50)
3. Check Apollo.io plan limits

### Database Connection Failed

**Problem:** Can't connect to PostgreSQL

**Solutions:**
```bash
# Check if PostgreSQL is running
docker ps | grep postgres

# Restart if needed
docker restart reviewsignal_postgres

# Verify connection from n8n
# In n8n: Test database connection in credentials
```

---

## 📊 MONITORING CHECKLIST

### Daily (First 3 Days)

- [ ] Check n8n executions (should see activity every 2 hours)
- [ ] Verify lead count is growing
- [ ] Review any error messages
- [ ] Confirm data quality (valid emails, relevant companies)

### Weekly (Monday)

- [ ] Total leads collected: ______
- [ ] Average per day: ______
- [ ] Data quality check (sample 10 leads)
- [ ] On track for 500-1,000 goal? Yes/No

---

## 🎯 SUCCESS CRITERIA

By Feb 14 (Launch Day), you should have:

✅ **Quantity:** 500-1,000 qualified leads
✅ **Quality:** Valid business emails, relevant industries
✅ **Variety:** Mix of company sizes and roles
✅ **Freshness:** Recently updated LinkedIn profiles
✅ **Enrichment:** Company info, titles, social links

---

## 🚨 WHEN TO STOP/PAUSE

**Pause Apollo if:**
- Collected 1,000+ leads (goal reached early)
- Data quality drops (spam emails, wrong industries)
- Apollo API quota exhausted
- Database storage issues

**You can always:**
- Pause workflow temporarily
- Adjust search criteria
- Resume collection later

---

## 📞 QUICK COMMANDS

### Activate Apollo Workflow
```
1. Open: http://35.246.214.156:5678
2. Find: "FLOW 7 - Apollo to PostgreSQL"
3. Toggle: Switch to "Active"
4. Done! ✅
```

### Check Lead Count
```bash
docker exec reviewsignal_postgres psql -U reviewsignal -d reviewsignal -c \
  "SELECT COUNT(*) as total_leads FROM leads WHERE source = 'apollo';"
```

### View Latest Lead
```bash
docker exec reviewsignal_postgres psql -U reviewsignal -d reviewsignal -c \
  "SELECT * FROM leads WHERE source = 'apollo' ORDER BY created_at DESC LIMIT 1;"
```

---

## 📅 TIMELINE REMINDER

**TODAY (Jan 30):**
- ✅ Activate Apollo workflow
- ✅ Verify first execution
- ✅ Check data is flowing

**Feb 6 (Week 1 Check):**
- Should have ~250 leads
- Domain warmup: ~55%
- Keep collecting

**Feb 13 (Week 2 Check):**
- Should have ~500-750 leads
- Domain warmup: ~75% ✅
- Final prep for launch

**Feb 14 (LAUNCH):**
- 500-1,000 leads ready ✅
- Domain warmup: 75%+ ✅
- ACTIVATE INSTANTLY CAMPAIGN 🚀

---

## 💡 PRO TIPS

1. **Start conservative:** Let it run for 24h, then check results
2. **Quality > Quantity:** Better 500 great leads than 1,000 mediocre
3. **Monitor first week closely:** Catch any issues early
4. **Don't touch Instantly yet:** Only Apollo, domains still warming
5. **Export backup:** After 1 week, export leads as CSV backup

---

**Status:** Ready to activate ✅
**Next action:** Open n8n and toggle Apollo workflow ON
**Time needed:** 2 minutes

🚀 **GO ACTIVATE IT NOW!**
