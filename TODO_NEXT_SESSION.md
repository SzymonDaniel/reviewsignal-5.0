# TODO - NASTĘPNA SESJA (TESTY)

**Ostatnia aktualizacja:** 2026-01-31 09:45 UTC
**Obecny coverage:** 63.04% (cel: 70% - PRAWIE OSIĄGNIĘTE! 🎉)
**✅ OPCJA 1 ZAKOŃCZONA:** Struktura testów naprawiona (+11.26% coverage)
**✅ OPCJA 2 ZAKOŃCZONA:** Payment Processor Tests (+8.08% coverage, 79% module)
**✅ OPCJA 3 ZAKOŃCZONA:** Real Scraper Extension (+8.33% coverage, 83% module!)
**✅ OPCJA 4 ZAKOŃCZONA:** User Manager Extension (+3.88% coverage, 70% module!)

---

## 🎯 QUICK START

```bash
# Sprawdź obecny stan
cd ~/reviewsignal-5.0
python3 -m pytest tests/unit/ --cov=modules --cov-report=term -q

# Powinno pokazać:
# - 110 passing tests ✅
# - Coverage: 42.75%
```

**✅ Co zostało zrobione (OPCJA 1):**
- Przeniesiono `test_ml_anomaly_detector_extended.py` do `tests/unit/`
- Coverage wzrósł z 31.49% → 42.75% (+11.26%)
- ML module: 84.95% (prawie kompletny!)
- 110 testów passing

---

## 🚀 NASTĘPNY PRIORYTET: OPCJA 2 - PAYMENT PROCESSOR TESTS (+15% coverage)

### Dlaczego to priorytet?
- Obecny coverage: 33.81% (najniższy z głównych modułów)
- Potencjalny wzrost: +15% total coverage
- Czas: ~2-3 godziny
- **Impact: 42.75% → 58% total coverage!**
- **Nowy czat:** Otwórz nowy czat dla tej opcji (unikanie wyczerpania kontekstu)

### Co zrobić:

1. **Stwórz plik testowy:**
```bash
touch tests/unit/test_payment_processor.py
```

2. **Struktura testów (25 testów minimum):**

```python
"""
Unit Tests for Payment Processor Module
Tests Stripe integration, subscriptions, and billing
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from modules.payment_processor import (
    StripeManager,
    PaymentProcessor,
    SubscriptionManager,
    # ... other imports
)


# ═══════════════════════════════════════════════════════════════
# FIXTURES
# ═══════════════════════════════════════════════════════════════

@pytest.fixture
def mock_stripe():
    """Mock Stripe client"""
    with patch('stripe.Customer') as mock_customer, \
         patch('stripe.Subscription') as mock_subscription, \
         patch('stripe.PaymentIntent') as mock_payment:
        yield {
            'customer': mock_customer,
            'subscription': mock_subscription,
            'payment': mock_payment
        }


# ═══════════════════════════════════════════════════════════════
# STRIPE MANAGER TESTS
# ═══════════════════════════════════════════════════════════════

class TestStripeManager:
    """Test Stripe integration"""

    def test_initialization(self):
        """Should initialize with API key"""
        # TODO: Implement
        pass

    def test_create_customer(self, mock_stripe):
        """Should create Stripe customer"""
        # TODO: Implement
        pass

    def test_create_subscription(self, mock_stripe):
        """Should create subscription"""
        # TODO: Implement
        pass

    # ... więcej testów


# ═══════════════════════════════════════════════════════════════
# PAYMENT PROCESSOR TESTS
# ═══════════════════════════════════════════════════════════════

class TestPaymentProcessor:
    """Test payment processing"""

    def test_process_payment(self, mock_stripe):
        """Should process payment"""
        # TODO: Implement
        pass

    # ... więcej testów


# ═══════════════════════════════════════════════════════════════
# SUBSCRIPTION MANAGER TESTS
# ═══════════════════════════════════════════════════════════════

class TestSubscriptionManager:
    """Test subscription management"""

    def test_upgrade_subscription(self):
        """Should upgrade subscription tier"""
        # TODO: Implement
        pass

    def test_cancel_subscription(self):
        """Should cancel subscription"""
        # TODO: Implement
        pass

    # ... więcej testów
```

3. **Przeczytaj najpierw kod:**
```bash
# Zrozum API przed pisaniem testów
head -200 modules/payment_processor.py
grep "^class " modules/payment_processor.py
grep "def " modules/payment_processor.py | head -30
```

4. **Uruchom testy:**
```bash
python3 -m pytest tests/unit/test_payment_processor.py -v
python3 -m pytest tests/unit/test_payment_processor.py --cov=modules.payment_processor --cov-report=term-missing
```

5. **Sprawdź total coverage:**
```bash
python3 -m pytest tests/unit/ tests/test_ml_anomaly_detector*.py --cov=modules --cov-report=term
# Powinno pokazać ~58% (było 42.68%)
```

---

## 📋 OPCJONALNE (jeśli zostanie czas):

### 2. Real Scraper Extension (+10% coverage)

**Uncovered funkcje (patrz PROGRESS.md linie 515-537):**
- GoogleMapsRealScraper.__init__() (linia 271-287)
- search_places() (linia 315-375)
- get_place_details() (linia 388-401)
- scrape_chain() (linia 441-483)

**Jak dodać:**
```bash
# Rozszerz istniejący plik
nano tests/unit/test_real_scraper.py

# Dodaj nowe klasy testów:
class TestGoogleMapsRealScraper:
    def test_initialization(self):
        # Test __init__ with/without Redis
        pass

    def test_search_places(self):
        # Mock googlemaps.Client
        pass

    # ... etc
```

### 3. User Manager Extension (+5% coverage)

**Uncovered klasy:**
- UserManager.create_user() (główna metoda!)
- SessionManager (cała klasa)

---

## 📊 PROGRESS TRACKING

### ✅ OPCJA 2 ZAKOŃCZONA (2026-01-31 09:30):
```
Coverage: 42.75% → 50.83% (+8.08%) ✅
Passing tests: 110 → 154 (+44) ✅
Duration: 40 minut
payment_processor.py: 33.81% → 79.36% (+45.55%!) 🚀

Modules status:
  ✅ ml_anomaly_detector.py: 84.62% (EXCELLENT!)
  ✅ payment_processor.py: 79.36% (EXCELLENT!) ← NOWE!
  ⚠️ user_manager.py: 50.48%
  ⚠️ real_scraper.py: 46.61% ← NASTĘPNY PRIORYTET (OPCJA 3)
  ❌ database_schema.py: 0.00%
```

### ✅ OPCJA 1 ZAKOŃCZONA (2026-01-31 09:10):
```
Coverage: 31.49% → 42.75% (+11.26%) ✅
Passing tests: 85 → 110 (+25) ✅
Duration: 15 minut
```

### Przed OPCJĄ 1:
```
Coverage: 31.49%
Passing tests: 85
ML module: 25.75%
Problem: test_ml_anomaly_detector_extended.py w złym katalogu
```

### Cel OPCJI 2 (następny czat):
```
Coverage: 58%+ (payment processor tests)
Passing tests: 135+
Target: payment_processor.py 70%+
Estimated time: 2-3 godziny
```

### Cel OPCJI 3 (kolejny czat):
```
Coverage: 68%+ (real scraper extension)
Passing tests: 150+
Target: real_scraper.py 70%+
Estimated time: 1-2 godziny
```

### Cel OPCJI 4 (ostatni czat):
```
Coverage: 73%+ (user manager extension)
Passing tests: 160+
Target: user_manager.py 70%+
Estimated time: 1 godzina
```

### Cel końcowy (za 2-3 sesje):
```
Coverage: 70%+
Passing tests: 180+
```

---

## 🔧 KOMENDY PRZYPOMNIENIE

```bash
# Sprawdź stan
python3 -m pytest tests/unit/ -q --tb=no

# Coverage szczegółowy
python3 -m pytest tests/unit/ --cov=modules --cov-report=term-missing

# HTML report (wizualizacja)
python3 -m pytest tests/unit/ --cov=modules --cov-report=html
firefox htmlcov/index.html

# Test konkretnego modułu
python3 -m pytest tests/unit/test_payment_processor.py -v

# Tylko failed (debugging)
python3 -m pytest tests/unit/ -x --tb=short

# Parallel execution (szybciej)
python3 -m pytest tests/unit/ -n auto
```

---

## 📚 POMOCNE ZASOBY

**Przeczytaj przed kodowaniem:**
1. `PROGRESS.md` (linie 1-600) - pełna historia
2. `modules/payment_processor.py` (głownie klasy i metody)
3. `tests/unit/test_real_scraper.py` (przykłady dobrych testów)
4. `tests/test_ml_anomaly_detector_extended.py` (comprehensive tests)

**Wzorce testowania:**
- Używaj fixtures dla mock objects
- Testuj edge cases (empty input, invalid data)
- Mock external APIs (Stripe, Redis, etc.)
- Sprawdzaj return values i exceptions
- Używaj descriptive test names

---

## ✅ SUCCESS CRITERIA

### OPCJA 1 - ZAKOŃCZONA ✅
- [x] Przeniesiono test_ml_anomaly_detector_extended.py do tests/unit/
- [x] 110 testów passing
- [x] ML coverage > 80% (osiągnięto 84.95%)
- [x] Total coverage > 40% (osiągnięto 42.75%)
- [x] Wszystkie testy stabilne

### OPCJA 2 - ZAKOŃCZONA ✅
Osiągnięcia:
- [x] Stworzono tests/unit/test_payment_processor.py (850+ linii!)
- [x] 44 testy passing (payment processor) - PRZEKROCZONO CEL!
- [x] Payment processor coverage 79.36% - ZNACZNIE PRZEKROCZONO (cel: 60%)
- [x] Total coverage 50.83% (cel: 55% - prawie!)
- [x] Wszystkie testy stabilne (zero flaky tests)
- [x] Dokumentacja zaktualizowana

### OPCJA 3 - NASTĘPNA
Cel sesji:
- [ ] Rozszerz tests/unit/test_real_scraper.py
- [ ] +15-20 nowych testów
- [ ] Real scraper coverage > 65%
- [ ] Total coverage > 58%
- [ ] Focus: search_places(), get_place_details(), scrape_chain()

---

**Good luck! 🚀**
