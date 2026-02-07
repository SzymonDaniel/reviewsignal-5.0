# 🌙 EVENING SESSION QUICKSTART
## 2026-01-30 Wieczór - 30 minut do uruchomienia

---

## ✅ DZISIAJ RANO ZROBIONE

- ✅ 77 sieci w bazie (+19)
- ✅ Czysta baza (syntetyczne usunięte)
- ✅ real_scraper.py naprawiony
- ✅ Cron job aktywny

---

## 🎯 WIECZÓR - 4 KROKI (30 MIN)

### **1. Query Fix (15 min)**
```bash
cd /home/info_betsim/reviewsignal-5.0

# SQL
sudo -u postgres psql -d reviewsignal << 'SQL'
ALTER TABLE chains ADD COLUMN IF NOT EXISTS search_query VARCHAR(200);
UPDATE chains SET search_query = 'CVS Pharmacy' WHERE name = 'CVS';
UPDATE chains SET search_query = 'H&M clothing store' WHERE name = 'H&M';
UPDATE chains SET search_query = name WHERE search_query IS NULL;
SQL
```

### **2. Test Scraper (10 min)**
```bash
python3 << 'PY'
from modules.real_scraper import GoogleMapsRealScraper
import os
os.environ['GOOGLE_MAPS_API_KEY'] = 'AIzaSyDZYIYVfDYVV8KMtQdbKJEnYufhwswI3Wk'

scraper = GoogleMapsRealScraper(api_key=os.environ['GOOGLE_MAPS_API_KEY'])
places = scraper.scrape_chain("Starbucks", ["Seattle, WA, USA"], max_per_city=2)
print(f"✅ {len(places)} locations, {sum(len(p['reviews']) for p in places)} reviews")
PY
```

### **3. Night Scraper (2 min)**
```bash
# Uruchom na noc
nohup python3 /tmp/night_scraper.py > /tmp/scraper.log 2>&1 &

# Check
tail -f /tmp/scraper.log
```

### **4. Check Pipeline (3 min)**
```bash
# n8n
curl http://35.246.214.156:5678/healthz

# Instantly
# → https://app.instantly.ai/dashboard/warmup

# Agent
curl http://localhost:8001/health
```

---

## 📊 OCZEKIWANE WYNIKI RANO

```
🎯 Recenzje: 1,000+ (z 105)
🎯 Lokalizacje: 100+ (z 25,894)
🎯 Queries: zoptymalizowane
🎯 Scraper: pracował całą noc
```

---

## 📁 PLIKI DO PRZECZYTANIA

1. **Najpierw:** `SESSION_SUMMARY_2026-01-30.md` (pełny opis)
2. **Potem:** `TODO_NEXT.md` (szczegóły zadań)
3. **Na końcu:** `PROGRESS.md` (log techniczny)

---

## 🚨 PROBLEMY? DEBUG:

```bash
# Scraper nie działa
tail -50 /tmp/night_scraper.log

# Baza danych
sudo -u postgres psql -d reviewsignal -c "SELECT COUNT(*) FROM reviews WHERE source='google_maps';"

# Cron job
crontab -l
```

---

**START TUTAJ:** ☝️ Krok 1  
**CEL:** 1,000+ recenzji do rana  
**CZAS:** 30 min setup + overnight scraping

🚀 **LET'S GO!**
