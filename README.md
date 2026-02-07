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

**Powinno pokazać DOKŁADNIE 5 plików:**
```
-rw-r--r-- 1 root root ~26000 real_scraper.py        ← Google Maps API
-rw-r--r-- 1 root root ~25000 ml_anomaly_detector.py ← ML/AI engine
-rw-r--r-- 1 root root ~32000 payment_processor.py   ← Stripe payments
-rw-r--r-- 1 root root ~33000 user_manager.py        ← JWT auth
-rw-r--r-- 1 root root ~32000 database_schema.py     ← PostgreSQL
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

# Test wszystkich modułów
python real_scraper.py        # Google Maps scraper
python ml_anomaly_detector.py # ML anomaly detection
python payment_processor.py   # Stripe payments
python user_manager.py        # Auth & JWT
python database_schema.py     # Database models
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

# Apollo.io (lead generation - ZAMIAST LinkedIn)
# NIE używamy LinkedIn - ryzyko bana za scraping!
APOLLO_API_KEY=your_apollo_api_key

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
    ├── real_scraper.py         # 5.0.1 - ~726 linii - Google Maps scraper
    ├── ml_anomaly_detector.py  # 5.0.2 - ~500 linii - ML anomaly detection
    ├── payment_processor.py    # 5.0.3 - ~600 linii - Stripe payments
    ├── user_manager.py         # 5.0.4 - ~650 linii - Auth & users
    └── database_schema.py      # 5.0.5 - ~700 linii - PostgreSQL models
```

## Docelowa lokalizacja na serwerze:

```
/root/reviewsignal/
├── .env                        # Konfiguracja
└── modules/
    ├── real_scraper.py         # Google Maps API scraper
    ├── ml_anomaly_detector.py  # Sentiment & anomaly ML
    ├── payment_processor.py    # Stripe integration
    ├── user_manager.py         # JWT auth, roles
    └── database_schema.py      # SQLAlchemy models
```

---

# 📊 OPIS MODUŁÓW

| Moduł | Plik | Linii | Co robi |
|--------|------|-------|----------|
| **5.0.1** | `real_scraper.py` | ~726 | Scraping Google Maps (111 miast globalnie) |
| **5.0.2** | `ml_anomaly_detector.py` | ~500 | ML wykrywanie anomalii w recenzjach |
| **5.0.3** | `payment_processor.py` | ~600 | Płatności Stripe + subskrypcje |
| **5.0.4** | `user_manager.py` | ~650 | Auth, JWT, sesje, uprawnienia |
| **5.0.5** | `database_schema.py` | ~700 | PostgreSQL modele + queries |

**Lead generation: Apollo.io (cold outreach) - NIE LinkedIn (ryzyko bana)**

**RAZEM: ~3,176 linii production-ready kodu!**

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

# ✅ CHECKLIST

Zaznacz po wykonaniu:

- [ ] Połączyłem się z serwerem przez SSH
- [ ] Sklonowałem repo: `git clone https://github.com/SzymonDaniel/reviewsignal-5.0.git`
- [ ] Skopiowałem 5 modułów do `/root/reviewsignal/modules/`
- [ ] Zainstalowałem zależności: `pip install -r requirements.txt`
- [ ] Zainstalowałem Playwright: `playwright install chromium`
- [ ] Przetestowałem każdy moduł: `python nazwa_modulu.py`
- [ ] Utworzyłem plik `.env` z kluczami API (Apollo.io, nie LinkedIn!)
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
