# 🚀 INSTANTLY CAMPAIGN ACTIVATION GUIDE

**Data:** 2026-02-06
**Status:** READY TO LAUNCH
**Leady:** 721 zsegmentowane
**Email Accounts:** 7/8 @ 99.6% warmup

---

## QUICK START (5 KROKÓW)

### ✅ KROK 1: Dodaj Email Accounts do Kampanii

Wszystkie 7 kont email są już w Instantly i mają 99-100% health score!

**Goto:** https://app.instantly.ai/app/accounts

**Status email accounts:**
```
✅ betsim@betsim.io             - 100% health (58 warmup emails)
✅ simon@reviewsignal.cc        - 99%  health (70 warmup emails)
✅ simon@reviewsignal.net       - 100% health (70 warmup emails)
✅ simon@reviewsignal.org       - 100% health (70 warmup emails)
✅ simon@reviewsignal.review    - 99%  health (70 warmup emails)
✅ simon@reviewsignal.work      - 100% health (70 warmup emails)
✅ simon@reviewsignal.xyz       - 100% health (70 warmup emails)
🟡 team@reviewsignal.ai         - Warmup in progress
```

**Akcja:**
1. Przejdź do każdej kampanii (5 kampanii poniżej)
2. W sekcji "Email Accounts" dodaj wszystkie 7 gotowych kont
3. Zostaw team@reviewsignal.ai na warmup (nie dodawaj jeszcze)

---

### ✅ KROK 2: Zaimportuj Leady do Kampanii

Użyj skryptu eksportującego:

```bash
cd /home/info_betsim/reviewsignal-5.0
python3 scripts/export_to_instantly.py
```

**Wygenerowane pliki CSV:**
```
exports/instantly/portfolio_manager_sequence.csv    (32 leads)
exports/instantly/quant_analyst_sequence.csv        (104 leads)
exports/instantly/head_alt_data_sequence.csv        (1 lead)
exports/instantly/cio_sequence.csv                  (3 leads)
exports/instantly/high_intent_sequence.csv          (569 leads)
```

**Dla każdej kampanii:**
1. Goto: https://app.instantly.ai/app/campaigns
2. Otwórz kampanię (np. "Portfolio Manager Outreach")
3. Kliknij "Add Leads" → "Upload CSV"
4. Upload odpowiedni CSV file
5. Mapuj kolumny: `email`, `first_name`, `company_name`

---

### ✅ KROK 3: Dodaj Email Sequences

Mamy 5 gotowych sekwencji w formacie JSON. Dla każdej kampanii:

**Campaign → Sequence → Add Variant**

#### 📧 KAMPANIA 1: Portfolio Manager Outreach
**Campaign ID:** `4e5a0e31-f0f0-4d5e-8ed9-ed5c89283eb3`
**Sequence file:** `email_templates/sequences/portfolio_manager_sequence.json`
**Leads:** 32

**Sekwencja (4 emaile):**
1. **Day 0** - "Alpha signal for {{company_name}} - consumer sentiment data"
2. **Day 3** - "Re: Alpha signal for {{company_name}}" (Chipotle case study)
3. **Day 7** - "15 min to show you our track record?"
4. **Day 14** - "Closing the loop" (breakup email)

---

#### 📧 KAMPANIA 2: Quant Analyst Outreach
**Campaign ID:** `7ac4becc-f05c-425b-9483-ab41356e024c`
**Sequence file:** `email_templates/sequences/quant_analyst_sequence.json`
**Leads:** 104 (największa grupa!)

**Sekwencja (4 emaile):**
1. **Day 0** - "Alternative data source for your models"
2. **Day 3** - "Re: Alternative data source" (Technical deep-dive)
3. **Day 7** - "Sample data + methodology doc?"
4. **Day 14** - "Last note from me"

---

#### 📧 KAMPANIA 3: Head of Alt Data Outreach
**Campaign ID:** `15def6db-dffe-4269-b844-b458919f38c3`
**Sequence file:** `email_templates/sequences/head_alt_data_sequence.json`
**Leads:** 1

**Sekwencja (4 emaile):**
1. **Day 0** - "New alt data source: Consumer sentiment at scale"
2. **Day 3** - "Re: New alt data source" (Pricing transparency)
3. **Day 7** - "Worth a conversation?"
4. **Day 14** - "Final note"

---

#### 📧 KAMPANIA 4: CIO Outreach
**Campaign ID:** `0075dfde-b47b-46d8-9537-ffca8b46b66d`
**Sequence file:** `email_templates/sequences/cio_sequence.json`
**Leads:** 3

**Sekwencja (3 emaile - shorter for C-level):**
1. **Day 0** - "Alternative data edge for your portfolio"
2. **Day 5** - "Re: Alternative data edge"
3. **Day 12** - "Closing the loop"

---

#### 📧 KAMPANIA 5: High Intent Outreach 🔥
**Campaign ID:** `9dfb46a4-ac6d-4c1d-960d-aa5d6f46a1fb`
**Sequence file:** `email_templates/sequences/high_intent_sequence.json`
**Leads:** 569 (78.9%!)

**Sekwencja (4 emaile):**
1. **Day 0** - "Noticed you're researching consumer sentiment tools"
2. **Day 2** - "Re: Consumer sentiment tools" (Faster follow-up!)
3. **Day 5** - "Quick demo of ReviewSignal?"
4. **Day 10** - "Last note from me"

**NOTE:** High intent leads mają krótsze delay (2-5-10 dni zamiast 3-7-14)

---

### ✅ KROK 4: Skonfiguruj Schedule

Dla każdej kampanii ustaw:

**Campaign Settings → Schedule:**
- **Days:** Monday - Friday (no weekends!)
- **Hours:** 09:00 - 18:00 (local time zone)
- **Max sends per day:** 50 per account
- **Delay between emails:** 2-5 minutes

**Time Zone:** Set to prospect's timezone (USA: ET/PT, UK: GMT, EU: CET)

---

### ✅ KROK 5: AKTYWUJ KAMPANIE! 🚀

**Przed aktywacją - FINAL CHECKLIST:**
```
✅ Email accounts dodane (7 kont)
✅ Leady zaimportowane (CSV)
✅ Sekwencje dodane (4 emails każda)
✅ Schedule skonfigurowany (Mon-Fri, 9-18)
✅ Variables test: {{first_name}}, {{company_name}}
✅ Unsubscribe link dodany (automated przez Instantly)
✅ Warmup kontynuowany (zostaw włączony!)
```

**ACTIVATION:**
1. Goto każdej kampanii
2. Review wszystkie ustawienia
3. Click **"Launch Campaign"** ✅

---

## KAMPANIE PRIORITIES

Sugerowana kolejność aktywacji:

### FAZA 1 (DZISIAJ) - High Intent
```
Priority 1: High Intent Campaign (569 leads)
- Highest quality leads
- Apollo intent signals
- Avg score: 80.7
```

### FAZA 2 (ZA 2 DNI) - Technical
```
Priority 2: Quant Analyst Campaign (104 leads)
- Largest segment after intent
- Technical focus
- 15 firms (high concentration)
```

### FAZA 3 (ZA TYDZIEŃ) - Decision Makers
```
Priority 3: Portfolio Manager Campaign (32 leads)
Priority 4: CIO Campaign (3 leads)
Priority 5: Head Alt Data Campaign (1 lead)
```

**Dlaczego stopniowo?**
- Monitor response rates po pierwszej kampanii
- Adjust messaging based on feedback
- Avoid overwhelming the system

---

## MONITORING & METRICS

### Track Daily
```
Dashboard: https://app.instantly.ai/app/campaigns
```

**Key Metrics:**
- **Open Rate:** Target >40% (good deliverability)
- **Reply Rate:** Target >5% (B2B hedge funds)
- **Bounce Rate:** Keep <2% (email health)
- **Unsubscribe:** Monitor <1%

### Weekly Review
- Which subject lines perform best?
- Which segments convert best?
- Adjust messaging based on replies

---

## LEAD SEGMENTATION BREAKDOWN

### Summary Stats (2026-02-06)
```
Total Leads:       721
Segmented:         709 (98.3%)
Unclassified:      12 (1.7%)

By Segment:
- High Intent:     569 leads (78.9%) → Campaign: 9dfb46a4-ac6d-4c1d-960d-aa5d6f46a1fb
- Quant Analyst:   104 leads (14.4%) → Campaign: 7ac4becc-f05c-425b-9483-ab41356e024c
- Portfolio Mgr:   32 leads (4.4%)   → Campaign: 4e5a0e31-f0f0-4d5e-8ed9-ed5c89283eb3
- CIO:             3 leads (0.4%)    → Campaign: 0075dfde-b47b-46d8-9537-ffca8b46b66d
- Head Alt Data:   1 lead (0.1%)     → Campaign: 15def6db-dffe-4269-b844-b458919f38c3
```

### Top Firms in Database
```
1. Millennium Management - 115 leads ($60B AUM)
2. Balyasny Asset Management - 109 leads ($16B AUM)
3. Point72 - 51 leads ($27B AUM)
4. Marshall Wace - 23 leads ($65B AUM)
5. ExodusPoint Capital - 20 leads ($12B AUM)
```

---

## RĘCZNE IMPORTOWANIE SEQUENCE DO INSTANTLY

Jeśli preferujesz manual import (zamiast CSV):

### Dla każdej kampanii:

1. **Otwórz kampanię w Instantly**
2. **Sequence → Add Variant → "Manual"**
3. **Dodaj każdy email:**

**Email 1:**
```
Subject: Alpha signal for {{company_name}} - consumer sentiment data
Body: [Copy from portfolio_manager_sequence.json step 1]
Delay: 0 days
```

**Email 2:**
```
Subject: Re: Alpha signal for {{company_name}}
Body: [Copy from portfolio_manager_sequence.json step 2]
Delay: 3 days
```

**Email 3:**
```
Subject: 15 min to show you our track record?
Body: [Copy from portfolio_manager_sequence.json step 3]
Delay: 7 days
```

**Email 4:**
```
Subject: Closing the loop
Body: [Copy from portfolio_manager_sequence.json step 4]
Delay: 14 days
```

---

## TROUBLESHOOTING

### Problem: Bounce rate >5%
**Solution:**
- Pause kampanię
- Verify email addresses: python3 scripts/verify_emails.py
- Remove invalid emails
- Resume

### Problem: Low open rate <20%
**Solution:**
- Test different subject lines (A/B test)
- Check spam score: mail-tester.com
- Verify SPF/DKIM records

### Problem: Spam complaints
**Solution:**
- Immediately pause campaign
- Review messaging (too aggressive?)
- Add more personalization
- Slow down send rate

---

## ADVANCED: AUTO-SYNC NEW LEADS

Aby automatycznie dodawać nowe leady z Apollo do kampanii:

```bash
# Cron job (już skonfigurowany):
# 09:00 UTC + 21:00 UTC daily

# Apollo → PostgreSQL (automated)
# PostgreSQL → Instantly (TODO: automate)
```

**Będzie w następnej wersji:** Auto-sync leadów do Instantly API po każdym Apollo run.

---

## FINAL NOTES

### What's Already Done ✅
- ✅ 721 leads collected (Apollo)
- ✅ Lead segmentation (5 segments)
- ✅ Email sequences written (5 sequences)
- ✅ Email accounts warmed up (7 accounts @ 99.6%)
- ✅ Instantly campaigns created (5 campaigns)
- ✅ CSV exports generated
- ✅ Campaign IDs configured (.env)

### What You Need to Do 🎯
1. Import CSVs do Instantly campaigns (5 min each)
2. Add email accounts to campaigns (2 min each)
3. Configure sequences (10 min each)
4. Set schedule Mon-Fri 9-18 (2 min each)
5. Launch campaigns! 🚀

**Total time:** ~2 hours
**Expected results:** 5-15 meetings/month from 721 outreach

---

**Document:** INSTANTLY_ACTIVATION_GUIDE.md
**Created:** 2026-02-06 21:10 UTC
**Author:** Claude Sonnet 4.5
**Status:** READY TO EXECUTE
