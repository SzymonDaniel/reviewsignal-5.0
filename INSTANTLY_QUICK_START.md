# 🚀 INSTANTLY QUICK START (5 MINUT)

**Status:** ✅ READY TO LAUNCH
**Leady:** 709 gotowych do wysyłki
**Email accounts:** 7 @ 99.6% warmup

---

## STEP 1: Upload Leads (2 min)

Goto: https://app.instantly.ai/app/campaigns

### Campaign 1: High Intent Outreach 🔥 (569 leads)
```
Campaign ID: 9dfb46a4-ac6d-4c1d-960d-aa5d6f46a1fb
Upload: exports/instantly/leads/high_intent_leads.csv
Avg Score: 80.7 (najlepsze leads!)
```

### Campaign 2: Quant Analyst (104 leads)
```
Campaign ID: 7ac4becc-f05c-425b-9483-ab41356e024c
Upload: exports/instantly/leads/quant_analyst_leads.csv
Avg Score: 55.2
```

### Campaign 3: Portfolio Manager (32 leads)
```
Campaign ID: 4e5a0e31-f0f0-4d5e-8ed9-ed5c89283eb3
Upload: exports/instantly/leads/portfolio_manager_leads.csv
Avg Score: 50.8
```

### Campaign 4: CIO (3 leads)
```
Campaign ID: 0075dfde-b47b-46d8-9537-ffca8b46b66d
Upload: exports/instantly/leads/cio_leads.csv
Avg Score: 53.7
```

### Campaign 5: Head Alt Data (1 lead)
```
Campaign ID: 15def6db-dffe-4269-b844-b458919f38c3
Upload: exports/instantly/leads/head_alt_data_leads.csv
Avg Score: 50.0
```

---

## STEP 2: Add Email Accounts (1 min)

W każdej kampanii dodaj te 7 kont:
```
✅ betsim@betsim.io
✅ simon@reviewsignal.cc
✅ simon@reviewsignal.net
✅ simon@reviewsignal.org
✅ simon@reviewsignal.review
✅ simon@reviewsignal.work
✅ simon@reviewsignal.xyz
```

⚠️ **NIE dodawaj:** team@reviewsignal.ai (jeszcze w warmup)

---

## STEP 3: Configure Schedule (1 min)

Każda kampania:
```
Days: Mon-Fri (no weekends)
Hours: 09:00 - 18:00
Max sends/day: 50 per account
Delay: 2-5 minutes between emails
```

---

## STEP 4: Verify Sequences (1 min)

Każda kampania powinna mieć 4 emaile (3 dla CIO):

**High Intent Example:**
- Email 1 (Day 0): "Noticed you're researching..."
- Email 2 (Day 2): Follow-up
- Email 3 (Day 5): Demo offer
- Email 4 (Day 10): Breakup

Wszystkie sekwencje w: `email_templates/sequences/`

---

## STEP 5: LAUNCH! 🚀

**Final Checklist:**
```
✅ Leads uploaded
✅ Email accounts added
✅ Schedule configured
✅ Sequences verified
```

**Click "Launch Campaign" dla każdej kampanii!**

---

## Expected Results

### Week 1
- 350-500 emails sent (warming up)
- 40-50% open rate
- 10-20 replies

### Month 1
- ~3,000 emails sent total
- 5-15 demo calls booked
- 1-3 pilot customers

---

## Monitor Daily

Dashboard: https://app.instantly.ai/app/campaigns

**Watch:**
- Open rate >40% ✅
- Reply rate >3% ✅
- Bounce rate <2% ✅

**If bounce rate >5%:** PAUSE and investigate

---

## Files Location

```
CSV Leads:        exports/instantly/leads/
Email Sequences:  email_templates/sequences/
Campaign Config:  .env (INSTANTLY_CAMPAIGN_*)
```

---

## Help Commands

```bash
# Re-export leads
python3 scripts/export_leads_to_csv.py

# Re-segment leads
python3 scripts/segment_leads.py

# Check lead stats
sudo -u postgres psql -d reviewsignal -c "SELECT segment, COUNT(*) FROM leads WHERE email IS NOT NULL GROUP BY segment;"
```

---

**GOOD LUCK!** 🚀

Time to launch: **5 minutes**
Expected ROI: **5-15 meetings/month**
