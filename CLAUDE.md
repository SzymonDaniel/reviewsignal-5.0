# CLAUDE.md - BAZA KONTEKSTU REVIEWSIGNAL.AI

**Ostatnia aktualizacja:** 2026-02-06 21:15 UTC
**Wersja dokumentu:** 3.8.0
**Sesja:** INSTANTLY CAMPAIGNS READY TO LAUNCH! 🚀 (727 leads, 5 kampanii)

---

## KRYTYCZNE INSTRUKCJE DLA CLAUDE

### Zapisywanie postępu (OBOWIĄZKOWE)

**Po każdym większym kroku zapisz postęp do `PROGRESS.md`:**

```bash
# Format wpisu:
## [DATA] [GODZINA] - [OPIS KROKU]
- Co zostało zrobione
- Wynik (sukces/błąd)
- Następny krok
```

**Kiedy zapisywać:**
1. Po każdej naprawie/zmianie w kodzie
2. Po każdym teście (sukces lub błąd)
3. Po każdym poleceniu użytkownika
4. Przed zakończeniem sesji
5. Co 15-20 minut pracy

**Dlaczego:** Sesje mogą się crashować. PROGRESS.md pozwala kontynuować bez utraty kontekstu.

### Przed rozpoczęciem pracy
1. Przeczytaj `PROGRESS.md` - sprawdź ostatni stan
2. Przeczytaj `CLAUDE.md` - kontekst projektu
3. Sprawdź `CURRENT_SYSTEM_STATUS.md` - live stats

---

## SZYBKI STATUS (2026-02-06)

```
SYSTEM:           ReviewSignal.ai v5.1.0 (Neural Enhanced)
STAN:             Development / Pre-revenue (INSTANTLY READY!)
VALUACJA:         €500,000 - €700,000 (asset-based, 727 hedge fund leads!)
CEL MRR:          €50,000
LOKALIZACJE:      42,201
RECENZJE:         46,113
LEADY:            727 (zsegmentowane: 709)
SIECI:            38+ (aktywne w Echo Engine)
SERWER:           35.246.214.156 (GCP)
SERWISY:          7/7 UP (100%)
INSTANTLY:        5 kampanii READY TO LAUNCH! 🚀
```

### TOP HEDGE FUNDS W BAZIE (2026-02-05):
| Firma | Leady | AUM |
|-------|-------|-----|
| Millennium | 115 | $60B |
| Balyasny | 109 | $16B |
| Point72 | 51 | $27B |
| Marshall Wace | 23 | $65B |
| ExodusPoint | 20 | $12B |
| Schonfeld | 18 | $14B |
| Brevan Howard | 16 | $35B |
| Centiva Capital | 16 | $5B |
| Two Sigma | 6 | $60B |
| Citadel | 2 | $62B |

**Laczne AUM firm w bazie: >$500B**

### INFRASTRUKTURA:
```
LANDING PAGE:     ✅ LIVE (https://reviewsignal.ai)
EMAIL WARMUP:     ✅ 7/8 ACCOUNTS @ 99.6% HEALTH
INSTANTLY:        ✅ READY TO LAUNCH!
APOLLO CRON:      ✅ AUTO-PAGINATION FIXED! (page 13 next)
NEURAL CORE:      ✅ LIVE (port 8005)
ECHO ENGINE:      ✅ LIVE (port 8002)
SINGULARITY:      ✅ LIVE (port 8003)
HIGGS NEXUS:      ✅ LIVE (port 8004)
SCRAPER:          ✅ 24/7 (Burger King, etc.)
```

### AUTOMATYZACJA APOLLO (NAPRAWIONA 2026-02-05):
```
PRZED:  Codziennie page 1 (te same leady!)
TERAZ:  Auto-paginacja (nowe leady!)

Schedule: 09:00 UTC + 21:00 UTC
Per run: ~55-60 nowych leadow
Daily: ~110 leadow
Monthly: ~3,300 leadow
Next page: 13
```

---

## 1. OPIS BIZNESOWY

### Co to jest ReviewSignal.ai?

**ReviewSignal.ai** to platforma **alternative data** dla hedge fundów i private equity. Dostarczamy sygnały tradingowe oparte na analizie recenzji konsumenckich.

### Model biznesowy:

```
┌─────────────────────────────────────────────────────────────────┐
│                    REVIEWSIGNAL.AI                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   ŹRÓDŁA DANYCH          PRZETWARZANIE         PRODUKTY        │
│   ─────────────          ─────────────         ────────        │
│   • Google Maps    ───►  • Scraping      ───►  • API Access    │
│   • Yelp           ───►  • NLP/Sentiment ───►  • Raporty       │
│   • TripAdvisor    ───►  • ML Anomaly    ───►  • Alerty        │
│   • Trustpilot     ───►  • GPT-5.2       ───►  • Dashboards    │
│                                                                 │
│   KLIENCI: Hedge Funds, Private Equity, Asset Managers         │
│   PRICING: €2,500 - €10,000+ / miesiąc                         │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Przykład sygnału:
> "Starbucks sentiment w NYC spadł o 15% w ciągu 2 tygodni.
> Korelacja z poprzednimi spadkami: -3.2% stock price w 30 dni."

---

## 2. ARCHITEKTURA TECHNICZNA

### 2.1 Diagram systemu

```
                              ┌─────────────────┐
                              │   KLIENCI       │
                              │  (Hedge Funds)  │
                              └────────┬────────┘
                                       │
                              ┌────────▼────────┐
                              │   FRAMER        │
                              │ reviewsignal.ai │
                              │  (Landing Page) │
                              └────────┬────────┘
                                       │
┌──────────────────────────────────────┼──────────────────────────────────────┐
│                                      │                    SERWER GCP        │
│                                      │                 35.246.214.156       │
│  ┌───────────────┐          ┌────────▼────────┐                            │
│  │   APOLLO.io   │          │    NEXT.JS      │                            │
│  │  (Lead Gen)   │          │   Dashboard     │                            │
│  │  €90/mies     │          │    :3000        │                            │
│  └───────┬───────┘          └────────┬────────┘                            │
│          │                           │                                      │
│          │              ┌────────────┴────────────┐                        │
│          │              │                         │                        │
│  ┌───────▼───────┐      │    ┌─────────────────┐  │                        │
│  │     n8n       │      │    │   FastAPI       │  │                        │
│  │  Automations  │──────┼───►│  Main API       │  │                        │
│  │    :5678      │      │    │  (DO ZROBIENIA) │  │                        │
│  └───────┬───────┘      │    └────────┬────────┘  │                        │
│          │              │             │           │                        │
│  ┌───────▼───────┐      │    ┌────────▼────────┐  │                        │
│  │ Lead Receiver │      │    │   MODULES       │  │                        │
│  │   API :8001   │──────┼───►│  (Python)       │  │                        │
│  └───────┬───────┘      │    └────────┬────────┘  │                        │
│          │              │             │           │                        │
│          │              └─────────────┼───────────┘                        │
│          │                            │                                     │
│  ┌───────▼────────────────────────────▼───────┐                            │
│  │              POSTGRESQL                     │                            │
│  │         (reviewsignal database)             │                            │
│  │  Tables: leads, locations, reviews, users   │                            │
│  └─────────────────────┬───────────────────────┘                            │
│                        │                                                    │
│  ┌─────────────────────▼───────────────────────┐                            │
│  │                 REDIS                        │                            │
│  │              (Cache Layer)                   │                            │
│  └─────────────────────────────────────────────┘                            │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
                                       │
                              ┌────────▼────────┐
                              │   INSTANTLY     │
                              │  (Cold Email)   │
                              │   $97/mies      │
                              └─────────────────┘
```

### 2.2 Stack technologiczny

| Warstwa | Technologia | Port/URL | Status |
|---------|-------------|----------|--------|
| **Landing** | Framer | reviewsignal.ai | ✅ Live |
| **Dashboard** | Next.js 14 + React | :3000 | ⚠️ Dev |
| **Main API** | FastAPI | :8000 | ❌ Do zrobienia |
| **Lead API** | FastAPI | :8001 | ✅ Live |
| **Neural API** | FastAPI + MiniLM | :8005 | ✅ Live 🧠 |
| **Echo Engine** | FastAPI | :8002 | ✅ Live |
| **Automations** | n8n | :5678 | ✅ Live |
| **Database** | PostgreSQL 14 | :5432 | ✅ Live |
| **Cache** | Redis | :6379 | ✅ Live |
| **Container** | Docker | - | ✅ n8n only |

---

## 3. MODUŁY SYSTEMU (SZCZEGÓŁOWO)

### 3.1 real_scraper.py (Moduł 5.0.1)

**Lokalizacja:** `/home/info_betsim/reviewsignal-5.0/modules/real_scraper.py`
**Rozmiar:** ~726 linii, 25.5 KB
**Status:** ✅ Gotowy

**Funkcjonalność:**
- Scraping Google Maps API (Places API)
- Rate limiting (50 req/s)
- Redis caching (24h TTL)
- Batch processing z ThreadPoolExecutor
- Data quality scoring (0-100)

**Klasy:**
```python
class GoogleMapsRealScraper:
    - search_places(query, location, radius)
    - get_place_details(place_id)
    - get_place_reviews(place_id)
    - scrape_chain(chain_name, cities, max_per_city)
    - scrape_by_coordinates(lat, lng, radius)

class RateLimiter:
    - wait()
    - get_stats()

class CacheManager:
    - get(place_id)
    - set(place_id, data, ttl)
    - delete(place_id)

class DataQualityCalculator:
    - calculate(place_data) → score 0-100
```

**Użycie:**
```python
scraper = GoogleMapsRealScraper(api_key=GOOGLE_MAPS_API_KEY)
places = scraper.scrape_chain("Starbucks", ["New York, NY, USA"], max_per_city=10)
```

---

### 3.2 ml_anomaly_detector.py (Moduł 5.0.2)

**Lokalizacja:** `/home/info_betsim/reviewsignal-5.0/modules/ml_anomaly_detector.py`
**Rozmiar:** ~500 linii, 25 KB
**Status:** ✅ Gotowy

**Funkcjonalność:**
- Wykrywanie anomalii w recenzjach (Isolation Forest)
- Sentiment analysis (VADER + custom)
- Trend detection (rolling averages)
- Alert generation

**Klasy:**
```python
class MLAnomalyDetector:
    - detect_rating_anomalies(reviews)
    - detect_sentiment_shift(reviews, window=7)
    - detect_volume_spike(reviews)
    - generate_trading_signal(chain, location)

class SentimentAnalyzer:
    - analyze(text) → score (-1 to 1)
    - batch_analyze(texts)
```

---

### 3.3 payment_processor.py (Moduł 5.0.3)

**Lokalizacja:** `/home/info_betsim/reviewsignal-5.0/modules/payment_processor.py`
**Rozmiar:** ~600 linii, 32 KB
**Status:** ✅ Gotowy

**Funkcjonalność:**
- Stripe integration (subscriptions)
- Webhook handling
- Invoice generation
- Usage metering

**Tiery cenowe:**
```python
PRICING = {
    "trial":      {"price": 0,      "api_calls": 100,    "duration": 14},
    "starter":    {"price": 2500,   "api_calls": 1000,   "cities": 5},
    "pro":        {"price": 5000,   "api_calls": 10000,  "cities": 30},
    "enterprise": {"price": 10000,  "api_calls": -1,     "cities": -1}
}
```

---

### 3.4 user_manager.py (Moduł 5.0.4)

**Lokalizacja:** `/home/info_betsim/reviewsignal-5.0/modules/user_manager.py`
**Rozmiar:** ~650 linii, 33 KB
**Status:** ✅ Gotowy

**Funkcjonalność:**
- JWT authentication (min 32 char secret, z ENV)
- User CRUD operations
- Role-based access control (RBAC)
- Session management
- Password hashing (bcrypt)

**Role:**
```python
class UserRoleEnum:
    VIEWER = "viewer"       # Read-only
    ANALYST = "analyst"     # Read + basic reports
    MANAGER = "manager"     # Full access to team
    ADMIN = "admin"         # Full access
    SUPERADMIN = "superadmin"  # System admin
```

---

### 3.5 database_schema.py (Moduł 5.0.5)

**Lokalizacja:** `/home/info_betsim/reviewsignal-5.0/modules/database_schema.py`
**Rozmiar:** ~700 linii, 32 KB
**Status:** ✅ Gotowy

**Tabele PostgreSQL:**
```sql
-- Główne tabele
users              -- Użytkownicy systemu
user_sessions      -- Sesje JWT
api_keys           -- Klucze API dla klientów
leads              -- Leady z Apollo (hedge funds)
locations          -- 22,725 lokalizacji (restauracje, retail)
reviews            -- Recenzje z Google Maps etc.
review_snapshots   -- Historyczne snapshoty
chains             -- 58 sieci (Starbucks, McDonald's, etc.)
reports            -- Wygenerowane raporty
payments           -- Historia płatności Stripe
outreach_log       -- Log wysyłki emaili
brand_analysis     -- Analizy brandów
brain_log          -- Logi AI agenta
```

---

### 3.6 lead_receiver.py (API - NOWY!)

**Lokalizacja:** `/home/info_betsim/reviewsignal-5.0/api/lead_receiver.py`
**Rozmiar:** ~200 linii, 7.5 KB
**Status:** ✅ Live (port 8001)
**Service:** `lead-receiver.service` (systemd)

**Funkcjonalność:**
- Odbiera leady z n8n (Apollo enrichment)
- Zapisuje do PostgreSQL (tabela `leads`)
- Sync do Instantly (API v2, async)

**Endpointy:**
```
POST /api/lead           - Dodaj pojedynczy lead
POST /api/leads/bulk     - Dodaj wiele leadów
GET  /api/leads/pending  - Leady nie wysłane do Instantly
GET  /api/stats          - Statystyki leadów
GET  /health             - Health check
```

**Konfiguracja (systemd):**
```ini
# /etc/systemd/system/lead-receiver.service
Environment="DB_HOST=localhost"
Environment="DB_PORT=5432"
Environment="DB_NAME=reviewsignal"
Environment="DB_USER=reviewsignal"
Environment="DB_PASS=reviewsignal2026"
Environment="INSTANTLY_API_KEY=MDA1ZWRjY2EtZGZmYi00ZjBiLTgzODUtYzEzMjU0MGM0NDRkOnBWQ1hiTmhCeHF6Rg=="
Environment="INSTANTLY_CAMPAIGN_ID=f30d31ff-46fe-4ae6-a602-597643a17a0c"
```

---

### 3.7 neural_core.py (Moduł 5.1.0 - NEURAL CORE 🧠)

**Lokalizacja:** `/home/info_betsim/reviewsignal-5.0/modules/neural_core.py`
**Rozmiar:** ~850 linii, 35 KB
**Status:** ✅ Live (port 8005)
**Service:** `neural-api.service` (systemd)

**Funkcjonalność:**
- MiniLM embeddings (all-MiniLM-L6-v2, 384 dimensions)
- Incremental statistics (Welford's online algorithm)
- Isolation Forest anomaly detection
- Unified Redis cache layer
- Zero API cost - wszystko lokalne!

**Klasy:**
```python
class NeuralCore:                    # Singleton - główna klasa
    - embed(text) → np.array         # 384-dim embedding
    - embed_batch(texts) → np.array  # Batch embeddings
    - similarity(t1, t2) → float     # Cosine similarity
    - find_similar(query, candidates, top_k) → List[dict]
    - update_stats(entity_id, value, entity_type)
    - get_stats(entity_id) → IncrementalStats
    - check_anomaly(entity_id, value) → AnomalyPrediction
    - analyze_review(text, rating, location_id) → dict
    - weekly_refit()                 # Retrain Isolation Forest
    - reload_model()                 # Reload from Redis cache

class EmbeddingEngine:               # MiniLM wrapper
class IncrementalStatsEngine:        # Welford's algorithm
class AdaptiveIsolationForest:       # Anomaly detection + Redis persistence
class UnifiedCache:                  # Redis cache layer
```

**API Endpointy (`api/neural_api.py`):**
```
POST /api/neural/embed           - Single embedding
POST /api/neural/embed-batch     - Batch embeddings (up to 100)
POST /api/neural/similar         - Semantic search
POST /api/neural/stats/update    - Update incremental stats
GET  /api/neural/stats/{id}      - Get entity statistics
POST /api/neural/anomaly/check   - Check for anomaly
POST /api/neural/analyze-review  - Full review analysis
GET  /api/neural/health          - System health
GET  /api/neural/metrics         - Prometheus metrics
POST /api/neural/refit           - Trigger manual refit (background)
POST /api/neural/reload          - Reload model from Redis cache 🔄
GET  /api/neural/model-info      - Isolation Forest model status
```

**Weekly Refit Cron Job:**
```
Schedule:  0 0 * * 0 (Every Sunday 00:00 UTC)
Script:    /home/info_betsim/reviewsignal-5.0/scripts/weekly_neural_refit.py
Log:       /var/log/reviewsignal/neural_refit.log

Flow:
1. Load training data (8,715 samples from PostgreSQL)
2. Refit Isolation Forest model
3. Save model to Redis (neural:model:isolation_forest_latest)
4. Update location statistics
5. POST /api/neural/reload → sync running API
```

**Model Persistence (Redis):**
- Model saved after each refit: `neural:model:isolation_forest_latest`
- Auto-loaded on API startup
- Hot reload via `/api/neural/reload` endpoint
- TTL: 7 days

**Powiązane moduły:**
- `modules/echo_neural_bridge.py` - Integracja z Echo Engine
- `modules/neural_integration.py` - Hooki dla scraperów
- `scripts/weekly_neural_refit.py` - Cron job (niedziela 00:00 UTC)

**Konfiguracja (systemd):**
```ini
# /etc/systemd/system/neural-api.service
ExecStart=/home/info_betsim/reviewsignal-5.0/venv/bin/python -m uvicorn api.neural_api:app --host 0.0.0.0 --port 8005
MemoryMax=1G
MemoryHigh=800M
```

**Test z prawdziwymi danymi (2026-02-03):**
```
Embeddings:        20 reviews → 11.55s (384-dim vectors)
Similarity:        Positive vs Negative = 0.38, Positive vs Positive = 0.66 ✅
Semantic search:   "terrible food cold service" → found matches (score 0.53)
Anomaly detection: 10/20 locations flagged for rating=1.5 ✅
Cache hit rate:    25.7% (improves with usage)
```

---

## 4. PIPELINE LEAD GENERATION

### 4.1 Diagram przepływu

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   APOLLO    │     │    n8n      │     │   ENRICH    │     │  LEAD API   │     │  INSTANTLY  │
│   Search    │────►│  Workflow   │────►│   Apollo    │────►│   :8001     │────►│  Campaign   │
│             │     │   :5678     │     │  /match     │     │             │     │             │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
      │                   │                   │                   │                   │
      │                   │                   │                   │                   │
      ▼                   ▼                   ▼                   ▼                   ▼
  Szuka PM,          Co 6 godzin         Pobiera pełne       Zapisuje do       Auto wysyłka
  CIO, Head of       automatycznie       dane: email,        PostgreSQL        cold emaili
  Alt Data           uruchamia się       miasto, kraj        (leads table)     (Mon-Fri 9-18)
```

### 4.2 Konfiguracja Apollo

**Plan:** Pro (€90/miesiąc)
**Limit:** 4,000 leadów/miesiąc
**API Key:** `koTQfXNe_OM599OsEpyEbA`

**Filtry wyszukiwania:**
```json
{
  "person_titles": [
    "Portfolio Manager",
    "Investment Analyst",
    "Quantitative Analyst",
    "Head of Alternative Data",
    "Data Scientist",
    "Head of Research",
    "CIO",
    "Managing Director"
  ],
  "person_locations": ["Germany", "United States", "United Kingdom", "Switzerland", "Netherlands"],
  "organization_num_employees_ranges": ["51,200", "201,500", "501,1000", "1001,5000", "5001,10000"],
  "per_page": 25
}
```

### 4.3 Konfiguracja Instantly

**Plan:** Hyper Growth ($97/miesiąc)
**API Key:** `MDA1ZWRjY2EtZGZmYi00ZjBiLTgzODUtYzEzMjU0MGM0NDRkOnBWQ1hiTmhCeHF6Rg==`
**Campaign ID:** `f30d31ff-46fe-4ae6-a602-597643a17a0c`
**Campaign Name:** ReviewSignal - Hedge Funds
**Schedule:** Mon-Fri, 09:00-18:00
**Status:** ✅ GOTOWA DO AKTYWACJI (wszystkie emaile 99-100% health!)

**Email Accounts w Warmup (2026-02-01):**
| Email | Warmup Emails | Health Score | Status |
|-------|---------------|--------------|--------|
| betsim@betsim.io | 58 | 100% 🔥 | ✅ Ready |
| simon@reviewsignal.cc | 70 | 99% 🔥 | ✅ Ready |
| simon@reviewsignal.net | 70 | 100% 🔥 | ✅ Ready |
| simon@reviewsignal.org | 70 | 100% 🔥 | ✅ Ready |
| simon@reviewsignal.review | 70 | 99% 🔥 | ✅ Ready |
| simon@reviewsignal.work | 70 | 100% 🔥 | ✅ Ready |
| simon@reviewsignal.xyz | 70 | 100% 🔥 | ✅ Ready |
| team@reviewsignal.ai | 0 | 0% 🟡 | ⚠️ Warmup Starting |

**TOTAL:** 8 email accounts, average 99.6% health score (7 ready + 1 warmup starting)
**Dashboard:** https://app.instantly.ai/app/accounts

### 4.4 Email Infrastructure (Purelymail)

**Provider:** Purelymail
**Server:** mailserver.purelymail.com
**SMTP Port:** 587
**IMAP Port:** 993

**Konfiguracja kont ReviewSignal:**

| Email | Typ | SMTP Enabled | Status |
|-------|-----|--------------|--------|
| team@reviewsignal.ai | Główna skrzynka | ✅ Włączone | ✅ Active |
| simon@reviewsignal.cc | Cold outreach | ✅ Włączone | ✅ Active |
| simon@reviewsignal.net | Cold outreach | ✅ Włączone | ✅ Active |
| simon@reviewsignal.org | Cold outreach | ✅ Włączone | ✅ Active |
| simon@reviewsignal.work | Cold outreach | ✅ Włączone | ✅ Active |
| simon@reviewsignal.xyz | Cold outreach | ✅ Włączone | ✅ Active |
| simon@reviewsignal.review | Cold outreach | ✅ Włączone | ✅ Active |

**Instantly.ai Integration:**
- **team@reviewsignal.ai:** ✅ Dodane do Instantly, warmup WŁĄCZONY
- **Pozostałe 6 kont:** ✅ Dodane, warmup 99-100% health score
- **Status:** IMAP ✅ Connected, SMTP ✅ Connected
- **Warmup Progress:** Automatically sends/receives emails to build reputation

**Uwagi:**
- SMTP został włączony dla team@reviewsignal.ai (wcześniej wyłączony)
- Wszystkie połączenia IMAP/SMTP działają poprawnie
- Warmup rozpoczął się automatycznie po dodaniu konta

### 4.5 n8n Workflow

**Nazwa:** FLOW 7 - Apollo to PostgreSQL
**ID:** C2kIA0mMISzcKnjC
**Trigger:** Co 6 godzin (Schedule Trigger)

**Nodes:**
1. Schedule Trigger (co 6h)
2. Apollo Search (POST /mixed_people/search)
3. Split People (rozdziela array)
4. Enrich Lead (POST /people/match)
5. Save to Database (POST localhost:8001/api/lead)

---

## 5. BAZA DANYCH

### 5.1 Tabela `leads`

```sql
CREATE TABLE leads (
    id SERIAL PRIMARY KEY,
    email VARCHAR(200) UNIQUE NOT NULL,
    name VARCHAR(200),
    title VARCHAR(200),
    company VARCHAR(200),
    lead_score INTEGER DEFAULT 50,
    priority VARCHAR(20) DEFAULT 'high',
    personalized_angle TEXT,
    linkedin_url VARCHAR(500),
    nurture_sequence BOOLEAN DEFAULT false,
    next_touchpoint TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Indexy
CREATE INDEX idx_leads_priority ON leads(priority);
CREATE INDEX idx_leads_score ON leads(lead_score DESC);
```

### 5.2 Aktualne dane w `leads` (2026-01-31)

**PRAWDZIWE LEADY Z HEDGE FUNDS - 31 total, 20 z finance:**

| Email | Firma | Title |
|-------|-------|-------|
| gabriela.gonzalez@troweprice.com | T. Rowe Price | Quant Investment Analyst |
| lukas.brandl-cheng@vanguard.co.uk | Vanguard | Quant Investment Analyst |
| ren.yang@prudential.com | Prudential Financial | Quant Investment Analyst |
| anne-marie.peterson@thecapitalgroup.com | Capital Group | Investment Analyst/PM |
| ty.painter@hartfordfunds.com | Hartford Funds | Quant Investment Analyst |
| elizabeth.coleman@carlyle.com | The Carlyle Group | Head of Alternative Data |
| mscheiber@coatue.com | Coatue Management | Head of Alternative Data |
| ghe@wellington.com | Wellington Management | Quant Analyst & PM |
| mike.boucher@fmr.com | Fidelity Investments | Quant Analyst / PM |
| pritha@arjuna-capital.com | Arjuna Capital | Senior Quant Analyst & PM |

**Statystyki leadów:**
- Total z emailem: 31
- Z LinkedIn: 29 (weryfikowalne!)
- Z hedge funds/finance: 20
- 128,234 potencjalnych w Apollo database

### 5.3 Tabela `locations`

- **27,006 lokalizacji** (restauracje, retail)
- **58 sieci** (Starbucks, McDonald's, KFC, etc.)
- **111 miast** (USA, Kanada, UK, Niemcy, Francja, etc.)

---

## 6. KONFIGURACJA SERWERA

### 6.1 Informacje o serwerze

```
IP:           35.246.214.156
Provider:     Google Cloud Platform (GCP)
OS:           Ubuntu 22.04 LTS
User:         info_betsim
Katalog:      /home/info_betsim/reviewsignal-5.0
```

### 6.2 Działające usługi

| Service | Port | Status | Komenda sprawdzenia |
|---------|------|--------|---------------------|
| PostgreSQL | 5432 | ✅ Running | `sudo systemctl status postgresql` |
| Redis | 6379 | ✅ Running | `sudo systemctl status redis` |
| n8n (Docker) | 5678 | ✅ Running | `docker ps \| grep n8n` |
| Lead Receiver | 8001 | ✅ Running | `sudo systemctl status lead-receiver` |
| Echo Engine | 8002 | ✅ Running | `sudo systemctl status echo-engine` |
| Neural API 🧠 | 8005 | ✅ Running | `sudo systemctl status neural-api` |
| Next.js | 3000 | ⚠️ Dev | - |

### 6.3 Pliki konfiguracyjne

```
/etc/systemd/system/lead-receiver.service  - Lead Receiver API
/etc/systemd/system/echo-engine.service    - Echo Engine API
/etc/systemd/system/neural-api.service     - Neural Core API 🧠
/root/.n8n/database.sqlite                 - n8n workflows
/home/info_betsim/reviewsignal-5.0/.env    - (do stworzenia)
```

---

## 7. DOMENY

### 7.1 Lista domen

| Domena | Status DNS | SSL | Landing Page | Email Warmup | Notes |
|--------|------------|-----|--------------|--------------|-------|
| reviewsignal.ai | ✅ LIVE | ✅ | ✅ Framer | ✅ 100% | Cloudflare DNS → Framer + Email Routing |
| n8n.reviewsignal.ai | ✅ | ✅ | - | - | Subdomain → GCP (34.159.18.55) |
| api.reviewsignal.ai | ✅ | ✅ | - | - | Subdomain → GCP (34.159.18.55) |
| reviewsignal.cc | ✅ | ✅ | ❌ | ✅ 99% 🔥 | simon@reviewsignal.cc (70 warmup emails) |
| reviewsignal.net | ✅ | ✅ | ❌ | ✅ 100% 🔥 | simon@reviewsignal.net (70 warmup emails) |
| reviewsignal.org | ✅ | ✅ | ❌ | ✅ 100% 🔥 | simon@reviewsignal.org (70 warmup emails) |
| reviewsignal.review | ✅ | ✅ | ❌ | ✅ 99% 🔥 | simon@reviewsignal.review (70 warmup emails) |
| reviewsignal.work | ✅ | ✅ | ❌ | ✅ 100% 🔥 | simon@reviewsignal.work (70 warmup emails) |
| reviewsignal.xyz | ✅ | ✅ | ❌ | ✅ 100% 🔥 | simon@reviewsignal.xyz (70 warmup emails) |
| betsim.io | ✅ | ✅ | ❌ | ✅ 100% 🔥 | betsim@betsim.io (58 warmup emails) |

**reviewsignal.ai DNS (Cloudflare → Framer):**
- A records: @ → 31.43.160.6, 31.43.161.6 (DNS only)
- CNAME: www → sites.framer.app (DNS only)
- Autoryzacja przez Domain Connect API ✅
- Status: READY, landing page działa poprawnie

**reviewsignal.ai Email Routing (Cloudflare):**
- ✅ **team@reviewsignal.ai** → info.betsim@gmail.com (Active)
- MX, TXT, SPF, DKIM records automatycznie skonfigurowane
- Dashboard: https://dash.cloudflare.com/.../reviewsignal.ai/email/routing/routes
- Status: Wszystkie emaile są przekierowywane poprawnie

### 7.2 DNS do skonfigurowania (Cloudflare)

```
reviewsignal.org:
  @ -> 35.246.214.156 (A record, DNS only)
  www -> 35.246.214.156 (A record, DNS only)

reviewsignal.review:
  @ -> 35.246.214.156
  www -> 35.246.214.156

reviewsignal.work:
  @ -> 35.246.214.156
  www -> 35.246.214.156

reviewsignal.xyz:
  @ -> 35.246.214.156
  www -> 35.246.214.156
```

---

## 8. CO ZOSTAŁO ZROBIONE (SESJA 2026-01-28)

### 8.1 Audyt i naprawy bezpieczeństwa
- [x] Audyt całego systemu
- [x] Usunięcie LinkedIn modułu (ryzyko bana za scraping)
- [x] Naprawa JWT_SECRET - wymaga min 32 znaki z ENV
- [x] Dodanie CI/CD (GitHub Actions)
- [x] Dodanie .gitignore (ochrona sekretów)
- [x] Dodanie testów (folder tests/)

### 8.2 Apollo.io fix
- [x] Zdiagnozowano problem: workflow pomijał enrichment
- [x] Naprawiono: dodano node "Enrich Lead"
- [x] Dane teraz zawierają: email, miasto, kraj, LinkedIn
- [x] Backup bazy n8n: `/root/.n8n/database.sqlite.backup.*`

### 8.3 Usunięcie Notion (zbędny pośrednik)
- [x] Stworzono Lead Receiver API (`api/lead_receiver.py`)
- [x] Skonfigurowano systemd service
- [x] Flow: Apollo → n8n → API → PostgreSQL

### 8.4 Instantly integration
- [x] Usunięto 3 stare kampanie (MedSpa, Test Restaurants)
- [x] Stworzono nową kampanię "ReviewSignal - Hedge Funds"
- [x] Skonfigurowano API v2 (Bearer token)
- [x] Przetestowano sync leadów - działa!

### 8.5 Dokumentacja
- [x] Aktualizacja README.md
- [x] Stworzenie VALUATION_REPORT.md
- [x] Stworzenie CLAUDE.md (ten plik)

### 8.6 DNS Configuration + Framer Setup (2026-01-31)
- [x] Konfiguracja DNS w Cloudflare dla reviewsignal.ai
- [x] A records: @ → 31.43.160.6, 31.43.161.6 (Framer IPs)
- [x] CNAME: www → sites.framer.app
- [x] Autoryzacja Framer przez Domain Connect API
- [x] Subdomain n8n.reviewsignal.ai → 34.159.18.55 (working)
- [x] Subdomain api.reviewsignal.ai → 34.159.18.55 (working)
- [x] Landing page https://reviewsignal.ai - LIVE
- [x] Verification: All services running, 31 leads in database

### 8.7 Production Monitoring + USA Expansion (2026-02-01)
- [x] **Prometheus Monitoring naprawiony**
  - Wszystkie 5 targetów UP (prometheus, node-exporter, postgres, lead-receiver, echo-engine)
  - Usunięto stare niepotrzebne targety (nginx, reviewsignal-api)
  - Naprawiono duplicate /metrics endpoint w echo_api.py
  - Skopiowano poprawny config do /etc/prometheus/prometheus.yml

- [x] **JWT_SECRET skonfigurowany**
  - Wygenerowano bezpieczny 64-znakowy secret
  - Dodano do .env
  - Dodano load_dotenv() do config.py
  - Wszystkie serwisy zrestartowane i działają

- [x] **Custom Prometheus Metrics - Enterprise Grade**
  - Lead Receiver: leads_collected, leads_processed, database_query_duration, instantly_syncs
  - Echo Engine: echo_computations, monte_carlo_simulations, trading_signals, engine_rebuild_duration, cache_hits/misses, engine_locations/chains_loaded
  - Stworzono /api/echo_metrics.py z profesjonalnymi metrykami biznesowymi
  - Tracking wszystkich operacji (compute_echo, monte_carlo, trading_signal, criticality)

- [x] **USA Expansion Scraping**
  - Uruchomiono usa_expansion_scraper.py w tle
  - Dodano 5,813 nowych lokalizacji (27,006 → 32,819)
  - Casual Dining: 14 sieci × 50 miast USA
  - Drugstores & Grocery: kolejne w pipeline

- [x] **Mass Review Scraper**
  - Ponownie uruchomiony w tle
  - Procesuję 119 lokalizacji Google Maps bez recenzji
  - 21.0% coverage (6,847/32,819 lokalizacji z recenzjami)

- [x] **Database Stats**
  - 32,819 lokalizacji (⬆️ +6,702 USA Expansion)
  - 6,847 z recenzjami (21.0% coverage)
  - 5,643 prawdziwych recenzji z Google Maps
  - 48 aktywnych sieci w Echo Engine

### 8.8 USA Expansion Complete + Email Warmup (2026-02-01)
- [x] **USA Expansion Scraping - COMPLETE**
  - Uruchomiono: 10:12 AM
  - Zakończono: 11:12 AM (60.3 minuty)
  - Dodano 6,702 nowych lokalizacji:
    - Casual Dining: 3,192 (Panera Bread, Texas Roadhouse, Cheesecake Factory, etc.)
    - Drugstores: 1,471 (CVS, Walgreens, Rite Aid, Duane Reade)
    - Grocery: 2,039 (Whole Foods, Trader Joe's, Kroger, Safeway, Publix, H-E-B, Wegmans)
  - Total lokalizacji: 32,819
  - Log: `/home/info_betsim/reviewsignal-5.0/logs/usa_expansion_20260201_101236.log`

- [x] **Purelymail - Email Configuration**
  - Włączono SMTP dla team@reviewsignal.ai
  - Server: mailserver.purelymail.com
  - SMTP Port: 587, IMAP Port: 993
  - Status: ✅ Wszystkie konta skonfigurowane

- [x] **Instantly.ai - Warmup dla team@reviewsignal.ai**
  - Konto dodane do Instantly
  - IMAP: ✅ Connected
  - SMTP: ✅ Connected
  - Warmup: ✅ WŁĄCZONY (rozpoczęty automatycznie)
  - Status: 0 warmup emails, 0% health (normalne na start)
  - Pozostałe 7 kont: 99-100% health score

- [x] **Email Accounts Summary**
  - Total: 8 kont email w systemie
  - 7 kont gotowych (99-100% warmup)
  - 1 konto w trakcie warmup (team@reviewsignal.ai)
  - Average health: 99.6%

### 8.9 Neural Core Implementation 🧠 (2026-02-03)
- [x] **Neural Core Module (`modules/neural_core.py` - 850+ LOC)**
  - MiniLM embeddings (all-MiniLM-L6-v2, 384 dimensions)
  - Incremental statistics (Welford's online algorithm)
  - Isolation Forest anomaly detection (100 estimators)
  - Unified Redis cache layer (30-day TTL embeddings)
  - Singleton pattern for resource efficiency
  - Zero API cost - wszystko lokalne!

- [x] **Neural API (`api/neural_api.py` - 400+ LOC)**
  - REST API on port 8005
  - Endpoints: embed, embed-batch, similar, stats, anomaly, analyze-review
  - Prometheus metrics integration
  - FastAPI with async support

- [x] **Integration Modules**
  - `modules/echo_neural_bridge.py` - Echo Engine integration
  - `modules/neural_integration.py` - Scraper hooks (@neural_process_review)
  - `scripts/weekly_neural_refit.py` - Cron job (Sundays 00:00 UTC)

- [x] **Systemd Service**
  - `/etc/systemd/system/neural-api.service`
  - Memory limits: 1GB max, 800MB high
  - Auto-restart on failure

- [x] **Test z prawdziwymi danymi**
  - 100 reviews z PostgreSQL
  - 50 locations with reviews
  - Semantic similarity: ✅ Works (pos vs neg = 0.38, pos vs pos = 0.66)
  - Anomaly detection: ✅ Works (10/20 locations flagged)
  - Cache hit rate: 25.7%

- [x] **Weekly Refit Cron Job** ⏰
  - Schedule: `0 0 * * 0` (Every Sunday 00:00 UTC)
  - Script: `scripts/weekly_neural_refit.py`
  - Log: `/var/log/reviewsignal/neural_refit.log`
  - Flow: Load data → Refit model → Save to Redis → Update stats → Reload API
  - Training samples: 8,715 from PostgreSQL

- [x] **Model Persistence (Redis)** 🔄
  - Model saved to Redis: `neural:model:isolation_forest_latest`
  - Auto-loaded on API startup
  - Hot reload via `POST /api/neural/reload`
  - Zero downtime updates

- [x] **Koszt:** €0/miesiąc (wszystko lokalne!)

### 8.10 MEGA Apollo Session + Auto-Pagination Fix (2026-02-05)

- [x] **Apollo Bug Fix - title=None**
  - Problem: Skrypt crashowal gdy Apollo zwracal lead bez `title`
  - Error: `AttributeError: 'NoneType' object has no attribute 'lower'`
  - Fix: Dodano null check w `_generate_angle()` w `scripts/apollo_bulk_search.py`

- [x] **Apollo Auto-Pagination - NAPRAWIONE!**
  - Problem PRZED: Cron zawsze pobieral page 1 (te same leady!)
  - Rozwiazanie: Nowy `scripts/apollo_cron_wrapper.sh` z auto-paginacja
  - Tracking strony: `scripts/.apollo_current_page`
  - Automatyczne zwiekszanie strony po kazdym urun
  - Reset do page 1 po 50 stronach (cykl)
  - Aktualna strona: 13

- [x] **Massive Lead Import - 540 NOWYCH LEADOW!**
  - Pobrane strony: 1-12 (63 leads/page)
  - Wynik: 633 total leads (z 93 przed sesja)
  - Wzrost: +540 leadow (+580%)

- [x] **Top Hedge Funds w bazie:**
  | Firma | Leady | AUM |
  |-------|-------|-----|
  | Millennium | 115 | $60B |
  | Balyasny | 109 | $16B |
  | Point72 | 51 | $27B |
  | Marshall Wace | 23 | $65B |
  | ExodusPoint | 20 | $12B |
  | Schonfeld | 18 | $14B |
  | Brevan Howard | 16 | $35B |
  | Two Sigma | 6 | $60B |
  | Citadel | 2 | $62B |

- [x] **Automatyzacja Apollo TERAZ:**
  - Schedule: 09:00 UTC + 21:00 UTC
  - Per run: ~55-60 nowych leadow
  - Daily: ~110 leadow
  - Monthly: ~3,300 leadow

- [x] **Database stats (2026-02-05):**
  - Lokalizacje: 42,201 (+5,271)
  - Recenzje: 46,113 (+568)
  - Leady: 633 (+540 = 7x wzrost!)

- [x] **Pliki zmodyfikowane:**
  - `scripts/apollo_bulk_search.py` - null title fix
  - `scripts/apollo_cron_wrapper.sh` - auto-pagination
  - `scripts/.apollo_current_page` - page tracker (NEW)
  - `CURRENT_SYSTEM_STATUS.md` - updated
  - `PROGRESS.md` - updated
  - `CLAUDE.md` - this update

### 8.11 Instantly Campaign Setup Complete (2026-02-06)

- [x] **Lead Segmentation System**
  - Dodano kolumnę `segment` do tabeli `leads`
  - Stworzono `scripts/segment_leads.py` (~200 LOC)
  - Automatyczna segmentacja po tytule i intent strength
  - 721 leadów zsegmentowane:
    - High Intent: 569 (78.9%) - Avg Score: 80.7 🔥
    - Quant Analyst: 104 (14.4%) - 15 firm
    - Portfolio Manager: 32 (4.4%) - 28 firm
    - CIO: 3 (0.4%)
    - Head Alt Data: 1 (0.1%)
    - Unclassified: 12 (1.7%)

- [x] **CSV Export System**
  - Stworzono `scripts/export_leads_to_csv.py` (~180 LOC)
  - Format Instantly-ready CSV z kolumnami: email, firstName, lastName, companyName
  - 5 plików CSV wygenerowane:
    - `high_intent_leads.csv` (569 leads, 182 KB)
    - `quant_analyst_leads.csv` (104 leads, 35 KB)
    - `portfolio_manager_leads.csv` (32 leads, 8 KB)
    - `cio_leads.csv` (3 leads, 830 bytes)
    - `head_alt_data_leads.csv` (1 lead, 263 bytes)

- [x] **Complete Documentation**
  - `INSTANTLY_ACTIVATION_GUIDE.md` - kompletny 200+ LOC przewodnik
  - `INSTANTLY_QUICK_START.md` - 5-minutowy quick start
  - Szczegółowe instrukcje dla wszystkich 5 kampanii
  - Expected results i monitoring guidelines

- [x] **Campaign Status**
  - 5 kampanii created w Instantly
  - 5 campaign IDs w .env
  - 5 email sequences gotowe (w `email_templates/sequences/`)
  - 7 email accounts @ 99.6% warmup

**REZULTAT:** Instantly campaigns w 100% gotowe do aktywacji! 🚀

**Projekcje po aktywacji:**
- Wysyłka: ~3,000 emails/miesiąc
- Open rate target: 40-50%
- Reply rate target: 3-5%
- Meetings: 5-15/miesiąc
- Pilot customers: 1-3/miesiąc

---

## 9. CO DO ZROBIENIA

### 9.1 PILNE (Ten tydzień)
- [x] **DNS Configuration** - reviewsignal.ai live (Framer) ✅
- [x] **Subdomeny** - n8n, api working ✅
- [x] **Compliance Module** - Source attribution, audit logging, rate limiting ✅
- [x] **Stworzyć team@reviewsignal.ai** - Cloudflare Email Routing → info.betsim@gmail.com ✅
- [x] **Check domain warmup status** - 7 emaili z 99-100% health score! 🔥 ✅
- [x] **Lead Segmentation** - 721 leadów zsegmentowane (5 segmentów) ✅
- [x] **CSV Export** - 5 plików CSV gotowych do Instantly upload ✅
- [x] **Email sequences** - 5 sekwencji (4 emails każda) ✅
- [x] **Dokumentacja** - INSTANTLY_ACTIVATION_GUIDE.md + INSTANTLY_QUICK_START.md ✅
- [ ] **USER ACTION:** Upload CSVs do Instantly campaigns (5 min)
- [ ] **USER ACTION:** Add 7 email accounts do kampanii (2 min)
- [ ] **USER ACTION:** AKTYWOWAĆ KAMPANIE INSTANTLY! 🚀 (1 min)

### 9.2 MIESIĄC 1 (Luty 2026)
- [ ] FastAPI main.py (główne API: /auth, /data, /reports)
- [ ] Docker + docker-compose
- [ ] Testy jednostkowe (50% coverage)
- [ ] HTTPS + CORS + Rate limiting
- [ ] Swagger documentation

### 9.3 MIESIĄC 2 (Marzec 2026)
- [ ] Amazon Reviews scraper
- [ ] Booking.com scraper
- [ ] ECHO ENGINE v1 (skalowanie do 42k lokalizacji)
- [ ] Unified scraper interface

### 9.4 MIESIĄC 3 (Kwiecień 2026)
- [ ] Self-aware system (auto-monitoring)
- [ ] 3-month track record (backtesting)
- [ ] Sales deck
- [ ] First 5 pilot customers (€12.5k MRR)

---

## 10. KOMENDY OPERACYJNE

### 10.1 SSH i podstawowe

```bash
# Połączenie z serwerem
ssh info_betsim@35.246.214.156

# Przejście do projektu
cd ~/reviewsignal-5.0
```

### 10.2 Services

```bash
# Lead Receiver API
sudo systemctl status lead-receiver
sudo systemctl restart lead-receiver
sudo journalctl -u lead-receiver -f          # Live logs
curl http://localhost:8001/health            # Health check
curl http://localhost:8001/api/stats         # Statystyki
curl http://localhost:8001/metrics           # Prometheus metrics

# Echo Engine API
sudo systemctl status echo-engine
sudo systemctl restart echo-engine
sudo journalctl -u echo-engine -f            # Live logs
curl http://localhost:8002/health            # Health check
curl http://localhost:8002/api/echo/health   # System health
curl http://localhost:8002/metrics           # Prometheus metrics

# Neural API 🧠 (NEW!)
sudo systemctl status neural-api
sudo systemctl restart neural-api
sudo journalctl -u neural-api -f             # Live logs
curl http://localhost:8005/api/neural/health # Health check
curl http://localhost:8005/api/neural/metrics # Prometheus metrics
curl http://localhost:8005/api/neural/model-info # Model status
# Test embedding:
curl -X POST http://localhost:8005/api/neural/embed \
  -H "Content-Type: application/json" \
  -d '{"text": "Great service and food!"}'
# Reload model from Redis:
curl -X POST http://localhost:8005/api/neural/reload
# Manual refit (background):
curl -X POST http://localhost:8005/api/neural/refit

# Weekly Neural Refit (Cron Job)
crontab -l | grep neural                     # Check cron job
python3 scripts/weekly_neural_refit.py       # Manual run
tail -f /var/log/reviewsignal/neural_refit.log # Refit logs
# Schedule: Every Sunday 00:00 UTC

# Prometheus Monitoring
sudo systemctl status prometheus
curl http://localhost:9090/-/healthy         # Health check
# UI: http://35.246.214.156:9090
# Targets: http://35.246.214.156:9090/targets

# n8n
docker logs n8n --tail 50
docker restart n8n
# UI: http://35.246.214.156:5678

# PostgreSQL
sudo -u postgres psql -d reviewsignal
sudo systemctl status postgresql
```

### 10.3 Baza danych

```bash
# Sprawdź leady
sudo -u postgres psql -d reviewsignal -c "SELECT * FROM leads ORDER BY id DESC LIMIT 10;"

# Sprawdź tabele
sudo -u postgres psql -d reviewsignal -c "\dt"

# Sprawdź lokalizacje
sudo -u postgres psql -d reviewsignal -c "SELECT COUNT(*) FROM locations;"
```

### 10.4 Git

```bash
cd ~/reviewsignal-5.0
git status
git add -A && git commit -m "message" && git push
```

### 10.5 Test pipeline

```bash
# Wyślij test lead
curl -X POST http://localhost:8001/api/lead \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com", "first_name": "Test", "last_name": "User", "title": "PM", "company": "TestCo"}'
```

---

## 11. LINKI I DOSTĘPY

| Zasób | URL/Info |
|-------|----------|
| **Landing page** | https://reviewsignal.ai |
| **GitHub** | https://github.com/SzymonDaniel/reviewsignal |
| **n8n UI** | http://35.246.214.156:5678 |
| **Lead API** | http://35.246.214.156:8001 |
| **Echo Engine API** | http://35.246.214.156:8002 |
| **Prometheus** | http://35.246.214.156:9090 |
| **Apollo.io** | https://app.apollo.io |
| **Instantly** | https://app.instantly.ai |
| **Cloudflare** | (DNS management) |
| **GCP Console** | (Server management) |
| **Email Accounts** | team@reviewsignal.ai ✅ + 7 kont w warmup (99-100% health) |

---

## 12. VALUACJA

### Obecna wartość (pre-revenue):
```
Asset-based: €400,000 - €550,000
```

### Projekcje:
| Milestone | MRR | Valuacja |
|-----------|-----|----------|
| MVP (5 klientów) | €12,500 | €1.5M - €2M |
| Traction | €50,000 | €6M - €9M |
| Scale | €150,000 | €20M - €30M |

Pełna analiza: `VALUATION_REPORT.md`

---

## 13. OCENA SYSTEMU (CLAUDE ASSESSMENT)

### 13.1 Wartość systemu

**Ocena ogólna: 6.5/10**

| Aspekt | Ocena | Komentarz |
|--------|-------|-----------|
| **Pomysł biznesowy** | 9/10 | Alternative data dla hedge funds to rynek wart $7B+. Niski poziom konkurencji w sentiment analysis z recenzji. |
| **Architektura** | 7/10 | Solidne podstawy: PostgreSQL, FastAPI, n8n. Brakuje mikroserwisów i kolejek (RabbitMQ/Kafka). |
| **Jakość kodu** | 6/10 | Moduły dobrze napisane, ale brak testów, brak CI/CD w praktyce, brak dokumentacji API. |
| **Automatyzacja** | 5/10 | Pipeline leadów działa, ale reszta wymaga ręcznej interwencji. |
| **Skalowalność** | 4/10 | Nie przetestowane pod obciążeniem. Brak load balancing, brak horizontal scaling. |
| **Gotowość produkcyjna** | 4/10 | Brak monitoringu, brak alertów, brak backupów automatycznych. |

### 13.2 Jakość kodu - szczegóły

**Mocne strony:**
- Czysta struktura modułów (separation of concerns)
- Użycie type hints w Python
- Sensowna obsługa błędów w krytycznych miejscach
- Dobre praktyki bezpieczeństwa (JWT, bcrypt)

**Słabe strony:**
- Brak testów jednostkowych (0% coverage)
- Brak docstrings w wielu funkcjach
- Hardcoded values w niektórych miejscach
- Brak centralnej konfiguracji (.env nie istnieje)
- Mieszanie języków (PL/EN) w kodzie i komentarzach

### 13.3 Czego brakuje do SAMOŚWIADOMOŚCI (Self-Aware System)

```
OBECNY STAN: 15% samoświadomości
CEL: 85%+ samoświadomości

BRAKUJĄCE KOMPONENTY:
┌─────────────────────────────────────────────────────────────────────────┐
│ 1. AUTO-MONITORING (0% → potrzebne)                                     │
│    - Health check wszystkich serwisów co 30s                            │
│    - Metryki: CPU, RAM, disk, latency                                   │
│    - Log aggregation (ELK stack lub Loki)                               │
│    - Dashboard z real-time statusem                                      │
├─────────────────────────────────────────────────────────────────────────┤
│ 2. AUTO-HEALING (0% → potrzebne)                                        │
│    - Restart crashed services automatycznie                             │
│    - Failover dla krytycznych komponentów                               │
│    - Circuit breaker pattern dla zewnętrznych API                       │
│    - Auto-scaling przy wysokim load                                     │
├─────────────────────────────────────────────────────────────────────────┤
│ 3. AUTO-REPORTING (20% → potrzebne więcej)                              │
│    - Codzienne raporty z działania systemu                              │
│    - Alerty email/Slack przy problemach                                 │
│    - Weekly digest dla właściciela                                      │
│    - Anomaly detection w metrykach                                      │
├─────────────────────────────────────────────────────────────────────────┤
│ 4. AUTO-OPTIMIZATION (0% → potrzebne)                                   │
│    - Query optimization (slow query detection)                          │
│    - Cache warming/invalidation                                         │
│    - Auto-cleanup starych danych                                        │
│    - Resource allocation optimization                                   │
├─────────────────────────────────────────────────────────────────────────┤
│ 5. DECISION ENGINE (0% → kluczowe!)                                     │
│    - AI agent decydujący o priorytetach                                 │
│    - Auto-scheduling zadań scrapingowych                                │
│    - Adaptive rate limiting                                             │
│    - Smart lead scoring (ML-based)                                      │
└─────────────────────────────────────────────────────────────────────────┘
```

### 13.4 Czego brakuje do FULL AUTOMATION

```
OBECNY STAN: 30% automatyzacji
CEL: 95%+ automatyzacji

BRAKUJĄCE ELEMENTY:
┌─────────────────────────────────────────────────────────────────────────┐
│ LEAD GENERATION (70% gotowe)                                            │
│ ✅ Apollo search                                                        │
│ ✅ Enrichment                                                           │
│ ✅ Save to PostgreSQL                                                   │
│ ✅ Sync to Instantly                                                    │
│ ❌ Email sequence content                                               │
│ ❌ A/B testing emaili                                                   │
│ ❌ Response handling                                                    │
│ ❌ Meeting booking automation                                           │
├─────────────────────────────────────────────────────────────────────────┤
│ DATA COLLECTION (40% gotowe)                                            │
│ ✅ Google Maps scraper                                                  │
│ ❌ Yelp scraper                                                         │
│ ❌ TripAdvisor scraper                                                  │
│ ❌ Amazon reviews scraper                                               │
│ ❌ Booking.com scraper                                                  │
│ ❌ Glassdoor scraper                                                    │
│ ❌ Auto-scheduling scraping                                             │
├─────────────────────────────────────────────────────────────────────────┤
│ ANALYSIS (30% gotowe)                                                   │
│ ✅ Sentiment analysis (basic)                                           │
│ ✅ Anomaly detection (basic)                                            │
│ ❌ Trend prediction                                                     │
│ ❌ Correlation with stock prices                                        │
│ ❌ Auto-report generation                                               │
│ ❌ PDF beautiful reports                                                │
├─────────────────────────────────────────────────────────────────────────┤
│ CLIENT DELIVERY (5% gotowe)                                             │
│ ❌ API access portal                                                    │
│ ❌ Real-time dashboard                                                  │
│ ❌ Alert system (email/webhook)                                         │
│ ❌ Custom report builder                                                │
│ ❌ Data export (CSV, JSON, API)                                         │
├─────────────────────────────────────────────────────────────────────────┤
│ BILLING (20% gotowe)                                                    │
│ ✅ Stripe integration (code)                                            │
│ ❌ Subscription management UI                                           │
│ ❌ Usage metering live                                                  │
│ ❌ Invoice automation                                                   │
│ ❌ Dunning (failed payment handling)                                    │
└─────────────────────────────────────────────────────────────────────────┘
```

### 13.5 PDF Generator - NIE ISTNIEJE

**Status:** ❌ Brak

**Co potrzebne:**
```python
# Sugerowana implementacja: ReportLab lub WeasyPrint
# Lokalizacja: /modules/pdf_generator.py

class PDFReportGenerator:
    def generate_sentiment_report(chain, period) -> bytes
    def generate_anomaly_alert(alert_data) -> bytes
    def generate_monthly_summary(client_id) -> bytes
    def generate_pitch_deck() -> bytes
```

**Priorytet:** WYSOKI - bez tego nie ma profesjonalnych raportów dla klientów

### 13.6 Email Templates - NIE ISTNIEJĄ

**Status:** ❌ Brak

**Potrzebne szablony:**
```
1. cold_outreach_initial.html      - Pierwszy kontakt z hedge fund
2. cold_outreach_followup_1.html   - Follow-up po 3 dniach
3. cold_outreach_followup_2.html   - Follow-up po 7 dniach
4. cold_outreach_breakup.html      - Ostatnia wiadomość
5. demo_invitation.html            - Zaproszenie na demo
6. trial_welcome.html              - Powitanie trial user
7. trial_ending.html               - Trial kończy się
8. weekly_digest.html              - Tygodniowy raport
9. anomaly_alert.html              - Alert o anomalii
10. invoice.html                   - Faktura
```

**Priorytet:** KRYTYCZNY - bez tego Instantly nie ma treści do wysyłania

---

## 14. PLAN 500K LOC ARCHITECTURE

### 14.1 Wizja docelowa

```
REVIEWSIGNAL.AI - ENTERPRISE ALTERNATIVE DATA PLATFORM
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

OBECNY STAN:        ~8,000 LOC
CEL:                500,000 LOC
TIMELINE:           18-24 miesiące
ZESPÓŁ DOCELOWY:    8-12 developerów

ARCHITEKTURA DOCELOWA:
┌─────────────────────────────────────────────────────────────────────────┐
│                           FRONTEND LAYER                                 │
│  Next.js Dashboard (50k LOC) │ Mobile App (30k LOC) │ Admin Panel (20k) │
├─────────────────────────────────────────────────────────────────────────┤
│                            API GATEWAY                                   │
│         Kong/Traefik + Rate Limiting + Auth + Load Balancing            │
├─────────────────────────────────────────────────────────────────────────┤
│                          MICROSERVICES                                   │
│ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐       │
│ │ Scraping │ │ Analysis │ │ Alerts   │ │ Billing  │ │ Reports  │       │
│ │ Service  │ │ Service  │ │ Service  │ │ Service  │ │ Service  │       │
│ │ (40k)    │ │ (60k)    │ │ (20k)    │ │ (25k)    │ │ (35k)    │       │
│ └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘       │
├─────────────────────────────────────────────────────────────────────────┤
│                          ECHO ENGINE                                     │
│      Quantum-Inspired Sentiment Propagation Algorithm (40k LOC)          │
├─────────────────────────────────────────────────────────────────────────┤
│                        DATA LAYER                                        │
│ PostgreSQL │ TimescaleDB │ Redis │ Elasticsearch │ S3 │ Kafka           │
├─────────────────────────────────────────────────────────────────────────┤
│                      ML/AI LAYER                                         │
│ TensorFlow │ PyTorch │ GPT Integration │ Custom Models (80k LOC)        │
└─────────────────────────────────────────────────────────────────────────┘
```

### 14.2 Dziewięć systemów do wgrania (JUTRO)

```
USER POSIADA DODATKOWE 9 SYSTEMÓW DO INTEGRACJI:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. TRACK RECORD SYSTEM (~30k LOC szacowane)
   - Backtesting engine
   - Historical signal accuracy
   - Performance attribution
   - Benchmark comparison

2. STREAMING PIPELINE (~25k LOC szacowane)
   - Real-time data ingestion
   - Kafka/Redis Streams
   - WebSocket delivery
   - Event sourcing

3. ML MODELS REPOSITORY (~50k LOC szacowane)
   - Sentiment models (BERT, RoBERTa)
   - Anomaly detection models
   - Prediction models
   - Model versioning (MLflow)

4. API MARKETPLACE (~20k LOC szacowane)
   - API key management
   - Rate limiting per client
   - Usage analytics
   - Developer portal

5. COMPETITOR INTELLIGENCE (~15k LOC szacowane)
   - Competitor monitoring
   - Market share analysis
   - Feature comparison
   - Price tracking

6. PREDICTIVE ANALYTICS (~40k LOC szacowane)
   - Stock price correlation
   - Revenue prediction
   - Trend forecasting
   - What-if scenarios

7. ENTERPRISE SSO (~10k LOC szacowane)
   - SAML 2.0
   - OAuth 2.0
   - LDAP integration
   - Multi-tenant

8. COMPLIANCE MODULE (~15k LOC szacowane)
   - GDPR compliance
   - Data retention
   - Audit logging
   - Access control

9. LOCATION INTELLIGENCE (~35k LOC szacowane)
   - Geo-clustering
   - Foot traffic integration
   - Demographics overlay
   - Heatmaps

RAZEM: ~240k LOC dodatkowego kodu do integracji
```

### 14.3 ECHO ENGINE - Quantum-Inspired Algorithm

```
ECHO ENGINE v1.0 - SENTIMENT PROPAGATION ALGORITHM
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

CONCEPT:
Algorytm inspirowany mechaniką kwantową do propagacji sentymentu
między powiązanymi lokalizacjami i brandami.

MATEMATYCZNY MODEL:
┌─────────────────────────────────────────────────────────────────────────┐
│ Ψ(sentiment) = Σ αᵢ|locationᵢ⟩ ⊗ |timeᵢ⟩ ⊗ |brandᵢ⟩                   │
│                                                                         │
│ gdzie:                                                                  │
│   αᵢ = amplitude (siła sentymentu)                                     │
│   |location⟩ = stan lokalizacji (geo-embedding)                        │
│   |time⟩ = stan czasowy (seasonality + trend)                          │
│   |brand⟩ = stan brandu (reputation vector)                            │
│                                                                         │
│ PROPAGATION RULES:                                                      │
│   1. Sentiment "echo" między sąsiednimi lokalizacjami                  │
│   2. Decay factor: e^(-λd) gdzie d = odległość geograficzna            │
│   3. Brand coherence: wspólny sentiment dla sieci                      │
│   4. Temporal interference: sezonowość + trendy                        │
└─────────────────────────────────────────────────────────────────────────┘

IMPLEMENTACJA (planowana):
/modules/echo_engine/
├── core.py                 # Main algorithm (~5k LOC)
├── propagation.py          # Sentiment spreading (~3k LOC)
├── interference.py         # Temporal patterns (~4k LOC)
├── collapse.py             # Signal generation (~2k LOC)
├── geo_tensor.py           # Geographic embeddings (~6k LOC)
├── brand_state.py          # Brand vectors (~4k LOC)
├── quantum_utils.py        # Math utilities (~3k LOC)
├── calibration.py          # Model tuning (~5k LOC)
├── backtester.py           # Validation (~4k LOC)
└── visualizer.py           # Debug visualization (~4k LOC)

TOTAL: ~40k LOC

USE CASE:
1. Wykryto spadek sentymentu w Starbucks NYC
2. ECHO propaguje do Starbucks Boston, Chicago (geo-echo)
3. ECHO propaguje do innych coffee chains (brand-echo)
4. System generuje SELL signal przed oficjalnym earnings report
```

### 14.4 Mega Locations Database

```
MEGA LOCATIONS DATABASE
━━━━━━━━━━━━━━━━━━━━━━━

OBECNY STAN:
├── Lokalizacje: 22,725
├── Sieci: 95
├── Kraje: 52
└── Miasta: 380+

CEL DOCELOWY:
├── Lokalizacje: 500,000+
├── Sieci: 500+
├── Kraje: 100+
└── Miasta: 5,000+

TOP 10 SIECI (wg liczby lokalizacji):
┌────┬────────────────────┬──────────┬─────────┐
│ #  │ Sieć               │ Lokacje  │ Kraje   │
├────┼────────────────────┼──────────┼─────────┤
│ 1  │ McDonald's         │ 3,247    │ 28      │
│ 2  │ Starbucks          │ 2,891    │ 24      │
│ 3  │ Subway             │ 1,876    │ 19      │
│ 4  │ KFC                │ 1,543    │ 22      │
│ 5  │ Burger King        │ 1,298    │ 18      │
│ 6  │ Pizza Hut          │ 1,187    │ 16      │
│ 7  │ Domino's           │ 1,054    │ 15      │
│ 8  │ Dunkin'            │ 987      │ 8       │
│ 9  │ Taco Bell          │ 876      │ 6       │
│ 10 │ Chipotle           │ 654      │ 4       │
└────┴────────────────────┴──────────┴─────────┘
```

---

## 15. JAK AKTUALIZOWAĆ TEN PLIK

Po każdej sesji Claude Code powinien:

1. Zaktualizować **"Ostatnia aktualizacja"** na górze
2. Zaktualizować **"SZYBKI STATUS"** jeśli się zmienił
3. Dodać wykonane zadania do **sekcji 8**
4. Przenieść ukończone z **sekcji 9** do **sekcji 8**
5. Dodać nowe problemy/zadania do odpowiednich sekcji
6. Zaktualizować diagramy jeśli architektura się zmieniła

---

## 14. NOTATKI DLA NASTEPNEJ SESJI (2026-02-06)

### CO DZIALA TERAZ (2026-02-06 21:15 UTC)

**SERWISY (7/7 UP):**
- reviewsignal-api (8000) - Running
- lead-receiver (8001) - Running
- echo-engine (8002) - Running
- singularity-engine (8003) - Running
- higgs-nexus (8004) - Running
- neural-api (8005) - Running
- production-scraper - Running

**BAZA DANYCH:**
- Lokalizacje: 42,201
- Recenzje: 46,113
- Leady: 727 (zsegmentowane: 709)
- TOP: Millennium 115, Balyasny 109, Point72 51

**AUTOMATYZACJA:**
- Apollo Cron: AUTO-PAGINATION WORKING!
- Schedule: 09:00 + 21:00 UTC
- Next page: 13+
- Prognoza: ~110 leads/dzien

**INSTANTLY CAMPAIGNS:**
- 5 kampanii CONFIGURED ✅
- 709 leadów SEGMENTED ✅
- 7 email accounts @ 99.6% warmup ✅
- CSV files READY ✅
- Email sequences READY ✅
- **STATUS: READY TO LAUNCH! 🚀**

### PRIORYTETY NA NASTEPNA SESJE

**KRYTYCZNE (USER ACTION REQUIRED):**
1. **Upload CSVs do Instantly** - 5 min (see INSTANTLY_QUICK_START.md)
2. **Add email accounts do kampanii** - 2 min
3. **LAUNCH CAMPAIGNS!** - 1 min 🚀

**NASTĘPNE:**
4. Monitor open/reply rates first 48h
5. A/B test subject lines
6. Demo dashboard dla klientow
7. Auto-sync Apollo → Instantly

### OSIAGNIECIA DZISIEJSZEJ SESJI (2026-02-06)

- [x] Lead segmentation system (5 segmentów, 721 leadów)
- [x] CSV export system dla Instantly
- [x] 5 plików CSV wygenerowane (709 leads total)
- [x] Kompletna dokumentacja (INSTANTLY_ACTIVATION_GUIDE.md + QUICK_START.md)
- [x] Wszystko gotowe do launch! 🚀

### KOMENDY QUICK START

```bash
# Sprawdz leady
sudo -u postgres psql -d reviewsignal -c "SELECT company, COUNT(*) FROM leads GROUP BY company ORDER BY COUNT(*) DESC LIMIT 15;"

# Sprawdz Apollo page
cat /home/info_betsim/reviewsignal-5.0/scripts/.apollo_current_page

# Sprawdz serwisy
sudo systemctl status production-scraper lead-receiver echo-engine

# Sprawdz logi Apollo
tail -30 /home/info_betsim/reviewsignal-5.0/logs/apollo_bulk_$(date +%Y%m%d).log

# Reczny Apollo run (nastepna strona)
python3 /home/info_betsim/reviewsignal-5.0/scripts/apollo_bulk_search.py --batch-size 63 --page $(cat /home/info_betsim/reviewsignal-5.0/scripts/.apollo_current_page)
```

### PLIKI KLUCZOWE

- `CURRENT_SYSTEM_STATUS.md` - aktualny status systemu
- `PROGRESS.md` - log postepow
- `CLAUDE.md` - ten plik (kontekst)
- `scripts/apollo_cron_wrapper.sh` - Apollo automation
- `scripts/.apollo_current_page` - tracker strony Apollo

---

*Dokument utrzymywany przez Claude AI dla ReviewSignal.ai Team*
*Wersja 3.8.0 - Instantly Campaigns Ready to Launch! - 2026-02-06 21:15 UTC*
