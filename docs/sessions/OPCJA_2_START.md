# OPCJA 2: Payment Processor Tests

**Start:** Gotowe do rozpoczęcia w nowym czacie
**Cel:** +15% coverage (42.75% → 58%)
**Czas:** 2-3 godziny

---

## 🚀 QUICK START DLA NOWEGO CZATU

### 1. Sprawdź obecny stan:
```bash
cd ~/reviewsignal-5.0
python3 -m pytest tests/unit/ --cov=modules --cov-report=term -q

# Powinno pokazać:
# - 110 passing tests
# - Coverage: 42.75%
# - payment_processor.py: 33.81%
```

### 2. Przeczytaj dokumentację:
```bash
cat TODO_NEXT_SESSION.md
tail -100 PROGRESS.md
```

### 3. Zbadaj moduł payment_processor:
```bash
head -200 modules/payment_processor.py
grep "^class " modules/payment_processor.py
grep "def " modules/payment_processor.py | head -30
```

---

## 📋 ZADANIE

**Stwórz:** `tests/unit/test_payment_processor.py`

**Zawartość:** ~25-30 testów dla:
1. **StripeManager** (Stripe integration)
   - test_initialization()
   - test_create_customer()
   - test_create_subscription()
   - test_cancel_subscription()
   - test_update_payment_method()

2. **PaymentProcessor** (payment processing)
   - test_process_payment()
   - test_refund_payment()
   - test_handle_failed_payment()
   - test_retry_payment()

3. **SubscriptionManager** (subscription management)
   - test_upgrade_subscription()
   - test_downgrade_subscription()
   - test_cancel_subscription()
   - test_renew_subscription()
   - test_handle_trial_end()

4. **InvoiceGenerator** (if exists)
   - test_generate_invoice()
   - test_send_invoice_email()

5. **WebhookHandler** (Stripe webhooks)
   - test_handle_payment_succeeded()
   - test_handle_payment_failed()
   - test_handle_subscription_updated()

---

## 🎯 SUCCESS CRITERIA

- [ ] Stworzono tests/unit/test_payment_processor.py
- [ ] Minimum 25 testów passing
- [ ] Payment processor coverage: 33.81% → 60%+
- [ ] Total coverage: 42.75% → 58%+
- [ ] Wszystkie testy stabilne (pytest -v)
- [ ] Mock Stripe API (nie używaj prawdziwych wywołań)

---

## 📚 WZORCE TESTOWANIA

Użyj tych wzorców z istniejących testów:

```python
import pytest
from unittest.mock import Mock, patch, MagicMock
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from modules.payment_processor import (
    StripeManager,
    PaymentProcessor,
    SubscriptionManager
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
        mock_customer.create.return_value = Mock(id='cus_test123')
        mock_subscription.create.return_value = Mock(id='sub_test123')
        mock_payment.create.return_value = Mock(id='pi_test123', status='succeeded')

        yield {
            'customer': mock_customer,
            'subscription': mock_subscription,
            'payment': mock_payment
        }

# ═══════════════════════════════════════════════════════════════
# TESTS
# ═══════════════════════════════════════════════════════════════

class TestStripeManager:
    def test_create_customer(self, mock_stripe):
        """Should create Stripe customer"""
        manager = StripeManager(api_key="test_key")
        customer = manager.create_customer(
            email="test@example.com",
            name="Test User"
        )

        assert customer is not None
        assert customer.id == 'cus_test123'
        mock_stripe['customer'].create.assert_called_once()
```

---

## 🔧 KOMENDY POMOCNICZE

```bash
# Uruchom tylko payment processor tests
python3 -m pytest tests/unit/test_payment_processor.py -v

# Coverage dla payment_processor
python3 -m pytest tests/unit/test_payment_processor.py \
  --cov=modules.payment_processor \
  --cov-report=term-missing

# Total coverage po dodaniu testów
python3 -m pytest tests/unit/ --cov=modules --cov-report=term

# Debug konkretnego testu
python3 -m pytest tests/unit/test_payment_processor.py::TestStripeManager::test_create_customer -v -s
```

---

## ⚠️ WAŻNE PRZYPOMNIENIA

1. **Mock all external APIs** - nie używaj prawdziwych kluczy Stripe
2. **Test edge cases** - empty input, invalid data, API errors
3. **Test error handling** - what happens when Stripe API fails?
4. **Descriptive test names** - should do something when something
5. **Update documentation** - PROGRESS.md po zakończeniu

---

## 📊 EXPECTED RESULTS

Po zakończeniu OPCJI 2:

```
Coverage: 58%+ (było 42.75%)
Tests: ~135+ passing (było 110)
payment_processor.py: 60%+ (było 33.81%)

Modules:
  ✅ ml_anomaly_detector.py: 84.95%
  ✅ payment_processor.py: 60%+
  ⚠️ user_manager.py: 50.48%
  ⚠️ real_scraper.py: 46.61%
  ❌ database_schema.py: 0.00%
```

---

## 🎯 CO DALEJ? (OPCJA 3)

Po zakończeniu OPCJI 2, w kolejnym czacie:
- **OPCJA 3:** Real Scraper Extension (+10% → 68%)
- **OPCJA 4:** User Manager Extension (+5% → 73%)

---

**Powodzenia! 🚀**

*Plik stworzony: 2026-01-31 09:12 UTC*
*Poprzednia opcja: OPCJA 1 ✅ (struktura testów naprawiona)*
