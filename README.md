# 🚀 REVIEWSIGNAL 5.0 - COMPLETE SYSTEM

```
██████╗ ███████╗██╗   ██╗██╗███████╗██╗    ██╗
██╔══██╗██╔════╝██║   ██║██║██╔════╝██║    ██║
██████╔╝█████╗  ██║   ██║██║█████╗  ██║ █╗ ██║
██╔══██╗██╔══╝  ╚██╗ ██╔╝██║██╔══╝  ██║███╗██║
██║  ██║███████╗ ╚████╔╝ ██║███████╗╚███╔███╔╝
╚═╝  ╚═╝╚══════╝  ╚═══╝  ╚═╝╚══════╝ ╚══╝╚══╝ 
         S I G N A L   5.0
```

---

# ⚠️⚠️⚠️ WAŻNE DLA COPILOT COMETA ⚠️⚠️⚠️

## MUSISZ ZASTĄPIĆ STARY MODUŁ 5.0.1!

Stary plik `real_scraper.py` który wcześniej wgrałeś jest **USZKODZONY** (miał ucięty kod - zakończył się w środku funkcji).

To repozytorium zawiera **KOMPLETNE, DZIAŁAJĄCE** wersje wszystkich 6 modułów!

---

# 📋 INSTRUKCJA WGRANIA NA SSH (KROK PO KROKU)

## KROK 1: Połącz się z serwerem

```bash
ssh root@your-server-ip
```

## KROK 2: Usuń stare pliki i sklonuj nowe repo

```bash
# Przejdź do folderu głównego
cd /root

# Usuń stare repo jeśli istnieje
rm -rf reviewsignal-5.0

# Sklonuj świeże repo z GitHuba
git clone https://github.com/SzymonDaniel/reviewsignal-5.0.git

# Wejdź do folderu
cd reviewsignal-5.0
```

## KROK 3: Skopiuj moduły do docelowej lokalizacji

```bash
# Utwórz folder docelowy jeśli nie istnieje
mkdir -p /root/reviewsignal/modules

# SKOPIUJ WSZYSTKIE 6 MODUŁÓW (flaga -f wymusza nadpisanie starych!)
cp -f /root/reviewsignal-5.0/modules/*.py /root/reviewsignal/modules/

# SPRAWDŹ czy wszystkie pliki są:
ls -la /root/reviewsignal/modules/
```

**Powinno pokazać DOKŁADNIE 6 plików:**
```
-rw-r--r-- 1 root root ~18000 real_scraper.py        ← NOWY! ZASTĘPUJE STARY!
-rw-r--r-- 1 root root ~22000 linkedin_lead_hunter.py
-rw-r--r-- 1 root root ~20000 ml_anomaly_detector.py
-rw-r--r-- 1 root root ~25000 payment_processor.py
-rw-r--r-- 1 root root ~27000 user_manager.py
-rw-r--r-- 1 root root ~26000 database_schema.py
```

## KROK 4: Zainstaluj zależności Python

```bash
# Zainstaluj wszystkie wymagane pakiety
pip install playwright beautifulsoup4 httpx structlog numpy scipy scikit-learn stripe bcrypt pyjwt sqlalchemy psycopg2-binary

# Zainstaluj przeglądarkę dla Playwright
playwright install chromium
playwright install-deps
```

## KROK 5: Przetestuj każdy moduł

```bash
cd /root/reviewsignal/modules

# Test modułu 5.0.1 (TEN BYŁ WCZEŚNIEJ USZKODZONY!)
python real_scraper.py
# Powinno pokazać: "✅ GoogleMapsScraper ready!"

# Test pozostałych modułów
python linkedin_lead_hunter.py
python ml_anomaly_detector.py
python payment_processor.py
python user_manager.py
python database_schema.py
```

**Każdy moduł powinien uruchomić się BEZ BŁĘDÓW i pokazać test output.**

## KROK 6: Utwórz plik konfiguracyjny .env

```bash
cat > /root/reviewsignal/.env << 'EOF'
# ========================================
# REVIEWSIGNAL 5.0 CONFIGURATION
# ========================================

# Google Maps API
GOOGLE_MAPS_API_KEY=your_google_maps_api_key_here

# LinkedIn (opcjonalne - do lead huntingu)
LINKEDIN_EMAIL=your_linkedin_email
LINKEDIN_PASSWORD=your_linkedin_password

# Stripe Payments
STRIPE_API_KEY=sk_live_xxxxxxxxxxxx
STRIPE_WEBHOOK_SECRET=whsec_xxxxxxxxxxxx

# PostgreSQL Database
DATABASE_URL=postgresql://reviewsignal:password@localhost:5432/reviewsignal

# JWT Secret (minimum 32 znaki!)
JWT_SECRET=your_super_secret_random_key_at_least_32_characters

# Mode
DEBUG=false
ENVIRONMENT=production
EOF
```

---

# 📁 GDZIE SĄ PLIKI?

## W tym repozytorium:

```
https://github.com/SzymonDaniel/reviewsignal-5.0
└── modules/
    ├── real_scraper.py         # 5.0.1 - ~450 linii (NOWY!)
    ├── linkedin_lead_hunter.py # 5.0.2 - ~550 linii
    ├── ml_anomaly_detector.py  # 5.0.3 - ~500 linii
    ├── payment_processor.py    # 5.0.4 - ~600 linii
    ├── user_manager.py         # 5.0.5 - ~650 linii
    └── database_schema.py      # 5.0.6 - ~700 linii
```

## Docelowa lokalizacja na serwerze:

```
/root/reviewsignal/
├── .env                        # Konfiguracja
└── modules/
    ├── real_scraper.py         # ← TEN PLIK ZASTĘPUJE STARY USZKODZONY!
    ├── linkedin_lead_hunter.py
    ├── ml_anomaly_detector.py
    ├── payment_processor.py
    ├── user_manager.py
    └── database_schema.py
```

---

# 📊 OPIS MODUŁÓW

| Moduł | Plik | Linii | Co robi |
|--------|------|-------|----------|
| **5.0.1** | `real_scraper.py` | ~450 | Scraping Google Maps (111 miast DE) |
| **5.0.2** | `linkedin_lead_hunter.py` | ~550 | Szukanie leadów na LinkedIn |
| **5.0.3** | `ml_anomaly_detector.py` | ~500 | ML wykrywanie anomalii w recenzjach |
| **5.0.4** | `payment_processor.py` | ~600 | Płatności Stripe + subskrypcje |
| **5.0.5** | `user_manager.py` | ~650 | Auth, JWT, sesje, uprawnienia |
| **5.0.6** | `database_schema.py` | ~700 | PostgreSQL modele + queries |

**RAZEM: ~3,450 linii production-ready kodu!**

---

# 🔧 TROUBLESHOOTING

### Problem: "ModuleNotFoundError"
```bash
export PYTHONPATH=/root/reviewsignal:$PYTHONPATH
```

### Problem: "Playwright not installed"
```bash
playwright install chromium
playwright install-deps
```

### Problem: "PostgreSQL connection failed"
```bash
# Sprawdź status PostgreSQL
sudo systemctl status postgresql

# Jeśli nie działa, uruchom
sudo systemctl start postgresql

# Utwórz bazę danych
sudo -u postgres createdb reviewsignal
sudo -u postgres createuser reviewsignal -P
```

### Problem: "Permission denied"
```bash
chmod +x /root/reviewsignal/modules/*.py
```

---

# ✅ CHECKLIST DLA COMETA

Zaznacz po wykonaniu:

- [ ] Połączyłem się z serwerem przez SSH
- [ ] Sklonowałem repo: `git clone https://github.com/SzymonDaniel/reviewsignal-5.0.git`
- [ ] Skopiowałem 6 modułów do `/root/reviewsignal/modules/`
- [ ] **ZASTĄPIŁEM stary uszkodzony `real_scraper.py`**
- [ ] Zainstalowałem zależności: `pip install ...`
- [ ] Zainstalowałem Playwright: `playwright install chromium`
- [ ] Przetestowałem każdy moduł: `python nazwa_modulu.py`
- [ ] Utworzyłem plik `.env` z kluczami API
- [ ] Wszystkie testy przeszły bez błędów

---

# 💰 PRICING

| Tier | Cena | API Calls | Raporty | Miasta |
|------|------|-----------|---------|--------|
| Trial | €0 (14 dni) | 100 | 5 | 1 |
| Starter | €2,500/mies | 1,000 | 50 | 5 |
| Pro | €5,000/mies | 10,000 | 500 | 30 |
| Enterprise | €10,000+/mies | Unlimited | Unlimited | 111 |

---

# 🔗 LINKI

- **Repozytorium:** https://github.com/SzymonDaniel/reviewsignal-5.0
- **Moduły:** https://github.com/SzymonDaniel/reviewsignal-5.0/tree/main/modules

---

**© 2026 ReviewSignal - B2B Data Intelligence**

*System stworzony przez Claude AI dla Simona*
