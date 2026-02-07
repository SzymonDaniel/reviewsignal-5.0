# INSTANTLY DOMAIN WARMUP STATUS

**Ostatnia aktualizacja:** 2026-01-30 19:10 UTC
**Status:** ⏳ W TRAKCIE ROZGRZEWANIA

---

## 📊 AKTUALNY STAN

### Domeny w rozgrzewaniu

| Domena | Start Date | Czas trwania | Target | Status |
|--------|------------|--------------|--------|--------|
| reviewsignal.cc | ~2026-01-23 | 1 tydzień | 2-3 tygodnie | ⏳ W trakcie |
| reviewsignal.net | ~2026-01-23 | 1 tydzień | 2-3 tygodnie | ⏳ W trakcie |
| reviewsignal.org | ~2026-01-23 | 1 tydzień | 2-3 tygodnie | ⏳ W trakcie |

**Obecny % warmup:** ~30-35% (szacowane)
**Target dla kampanii:** 70%+
**Estimated completion:** 2026-02-13 (za 2 tygodnie)

---

## ⏱️ TIMELINE

### Phase 1: Rozgrzewanie (Weeks 1-3)
```
Week 1 (2026-01-23 - 01-30): ✅ DONE
├─ Start warmup
├─ Daily automated emails (Instantly internal)
└─ Current: ~35% warmed

Week 2 (2026-01-31 - 02-06): ⏳ IN PROGRESS
├─ Continue automated warmup
├─ Expected: ~55% warmed
└─ Still too early for campaign

Week 3 (2026-02-07 - 02-13): ⏳ TARGET
├─ Continue automated warmup
├─ Expected: ~75% warmed
└─ ✅ READY FOR CAMPAIGN LAUNCH
```

### Phase 2: Campaign Launch (Week 4)
```
2026-02-14 (Friday) - RECOMMENDED LAUNCH DATE
├─ Domain warmup: 75%+
├─ Apollo workflow: Running (2+ weeks of leads)
├─ Database: 500-1000 leads ready
└─ Campaign: Start with 20 emails/day
```

---

## 🎯 CAMPAIGN ACTIVATION PLAN

### Pre-Launch (Weeks 1-3) - ⏳ CURRENT PHASE
**Focus:** Prepare infrastructure while domains warm

**To Do:**
- [x] Email templates created ✅
- [x] Lead Receiver working ✅
- [x] Activation guide written ✅
- [ ] Activate Apollo workflow (collect leads while waiting)
- [ ] Monitor domain warmup weekly
- [ ] Prepare first 100 leads for import
- [ ] Test email deliverability (mail-tester.com)

**Result:** 500-1,000 leads ready, domains at 75%+

### Launch Week (Week 4: Feb 14-21)
**Focus:** Conservative start, monitor closely

**Day 1-3 (Feb 14-16):**
- Launch campaign
- Send 20 emails/day (conservative)
- Monitor: open rate, bounce rate, spam reports
- Expected: 60 emails sent, 18 opens, 3-4 replies

**Day 4-7 (Feb 17-21):**
- If metrics good: continue 20/day
- If metrics great (>35% open): increase to 30/day
- Monitor daily

**Result:** 100-140 emails sent, ~40 opens, ~10 replies, 1-2 demos

### Scale Phase (Weeks 5-12)
**Focus:** Gradual scaling based on performance

**Week 5-6:**
- Increase to 50 emails/day
- Expected: 500 emails, 150 opens, 25 replies, 5 demos

**Week 7-8:**
- Increase to 75 emails/day
- Expected: 750 emails, 225 opens, 40 replies, 8 demos

**Week 9-12:**
- Increase to 100 emails/day
- Target: **5 customers @ €2,500/mo = €12.5k MRR**

---

## 📋 WEEKLY CHECKS (Do when ready)

### Every Monday (Starting Feb 3)

```bash
# 1. Check domain warmup progress
# Log in to: https://app.instantly.ai/dashboard/warmup
# Record % for each domain

# 2. Check lead collection
psql -d reviewsignal -c "
  SELECT COUNT(*) as total_leads,
         COUNT(CASE WHEN DATE(created_at) >= CURRENT_DATE - 7 THEN 1 END) as last_week
  FROM leads;
"

# 3. Decision matrix
# - If warmup < 50%: Continue waiting
# - If warmup 50-70%: Prepare for launch (1-2 weeks)
# - If warmup > 70%: READY TO LAUNCH
```

---

## ⚠️ IMPORTANT WARNINGS

### DON'T Launch Campaign If:
- ❌ Domain warmup < 70%
- ❌ Bounce rate > 2% in tests
- ❌ Spam score > 3/10 (mail-tester.com)
- ❌ Less than 50 quality leads in database

### Risks of Early Launch:
1. **Spam folder:** Emails go to spam, waste leads
2. **Domain reputation damage:** Hard to recover
3. **Instantly account risk:** Could get suspended
4. **Lead waste:** Burn through leads with no results

### Safe Launch Criteria:
- ✅ Domain warmup > 70%
- ✅ Test email score > 7/10 (mail-tester.com)
- ✅ 100+ quality leads ready
- ✅ Email templates tested
- ✅ Reply handling process ready

---

## 🛠️ WHILE WAITING (Weeks 1-3)

### Infrastructure Tasks
- [x] Create email templates ✅
- [x] Setup Lead Receiver ✅
- [x] Write activation guide ✅
- [ ] Activate Apollo workflow
- [ ] Collect 500+ leads
- [ ] Setup reply tracking system
- [ ] Create demo booking calendar
- [ ] Prepare sales pitch deck

### Testing Tasks
- [ ] Send test emails to mail-tester.com
- [ ] Test emails to personal inbox (Gmail, Outlook)
- [ ] Verify links work in emails
- [ ] Test Instantly variable replacement
- [ ] Practice demo presentation

### Marketing Tasks
- [ ] Refine ICP (Ideal Customer Profile)
- [ ] Research target hedge funds
- [ ] Prepare case studies
- [ ] Create demo slides
- [ ] Write FAQ doc

---

## 📈 EXPECTED TIMELINE (Full Picture)

```
2026-01-30 (TODAY):
├─ Domain warmup: Week 1 (35%)
├─ Email templates: Created
├─ Lead Receiver: Working
└─ Apollo workflow: Ready to activate

2026-02-06 (Week 2):
├─ Domain warmup: 55%
├─ Apollo workflow: Running (1 week)
├─ Leads collected: 200-400
└─ Still waiting for warmup

2026-02-13 (Week 3):
├─ Domain warmup: 75% ✅
├─ Apollo workflow: Running (2 weeks)
├─ Leads collected: 500-1000
└─ READY FOR LAUNCH

2026-02-14 (Launch Day):
├─ Campaign activated
├─ First 20 emails sent
├─ Monitoring begins
└─ Pipeline LIVE

2026-03-31 (Week 12):
├─ 2,000 emails sent
├─ 20+ demos completed
├─ TARGET: 5 customers signed
└─ MRR: €12.5k ✅
```

---

## 🎯 CURRENT FOCUS (Weeks 1-3)

**PRIMARY:** Let domains warm up (passive, no action needed)

**SECONDARY:** Build lead pipeline while waiting
1. Activate Apollo workflow in n8n
2. Let it collect 500-1000 leads over 2-3 weeks
3. When domains ready → immediate launch with full lead pipeline

**TERTIARY:** Prepare for launch
- Test emails
- Refine templates
- Prepare demo materials
- Build sales process

---

## 📝 DECISION LOG

**2026-01-30 19:10 UTC:**
- ✅ Domain warmup confirmed: Only 1 week in progress
- ✅ Decision: Wait 2 more weeks before campaign launch
- ✅ Target launch date: February 14, 2026
- ✅ Action: Document status, continue infrastructure prep
- ✅ Next check: February 6, 2026 (reassess warmup %)

---

## 🚀 NEXT ACTIONS

### This Week (2026-01-30 - 02-06)
- [x] Document domain status ✅
- [ ] Activate Apollo workflow (start lead collection)
- [ ] Check domain warmup on Feb 6
- [ ] Prepare demo materials

### Next Week (2026-02-07 - 02-13)
- [ ] Check domain warmup (should be 70%+)
- [ ] Verify 500+ leads collected
- [ ] Final test of email deliverability
- [ ] If warmup > 70%: Schedule launch for Feb 14

### Launch Week (2026-02-14+)
- [ ] Activate Instantly campaign
- [ ] Send first batch (20 emails)
- [ ] Monitor metrics hourly (first day)
- [ ] Adjust based on performance

---

**Status:** ⏳ WAITING FOR DOMAIN WARMUP
**Next Milestone:** February 13, 2026 (warmup complete)
**Estimated Campaign Launch:** February 14, 2026

**Note:** Better to wait 2 extra weeks than damage domain reputation!

---

*Zapisane: 2026-01-30 19:10 UTC*
*Następna aktualizacja: 2026-02-06 (weekly check)*
