# Testing Quick Start - ReviewSignal 5.0

**Status:** Phase 1 Complete - 40% coverage achieved
**Goal:** 70% coverage

---

## ⚡ 1-Minute Quick Start

```bash
# Go to project
cd ~/reviewsignal-5.0

# Run passing tests
python3 -m pytest tests/unit/test_user_manager.py -v

# See coverage
python3 -m pytest tests/unit/test_user_manager.py --cov=modules/user_manager --cov-report=html

# Open coverage report
xdg-open htmlcov/index.html  # Linux
open htmlcov/index.html       # macOS
```

---

## 📊 Current Status

| What | Status | Details |
|------|--------|---------|
| Tests Created | 160 tests | user_manager (60), real_scraper (50), api (40), load (3) |
| Tests Passing | 95 tests | user_manager: 60/60, real_scraper: 25/50 |
| Coverage | 40% | Target: 70% |
| user_manager.py | ✅ 80% | COMPLETE |
| real_scraper.py | ⚠️ 30% | Needs API fixes |
| Other modules | ❌ 0-15% | Need tests |

---

## 🚀 What You Can Do Right Now

### Run Tests
```bash
# All unit tests
pytest tests/unit/ -v

# Specific module
pytest tests/unit/test_user_manager.py -v

# With coverage
pytest tests/unit/ --cov=modules --cov-report=html

# Fast tests only (skip slow ones)
pytest -m "not slow" -v
```

### Check Coverage
```bash
# Generate HTML report
pytest tests/unit/ --cov=modules --cov-report=html

# View report
xdg-open htmlcov/index.html
```

### Setup Pre-commit Hooks
```bash
# Install
pip install pre-commit

# Setup hooks
pre-commit install

# Run manually
pre-commit run --all-files
```

---

## 🔧 What Needs Work

### 1. Fix Failing Tests (PRIORITY 1)
```bash
# The issue: test_real_scraper.py has API mismatches
# Fix: Read actual API and adjust tests

# Read real implementation
cat modules/real_scraper.py | grep "class RateLimiter" -A 20

# Edit tests to match
nano tests/unit/test_real_scraper.py

# Re-run
pytest tests/unit/test_real_scraper.py -v
```

### 2. Run Integration Tests
```bash
# Start API server first
cd api/
uvicorn lead_receiver:app --port 8001

# In another terminal, run tests
pytest tests/integration/test_api_endpoints.py -v
```

### 3. Create Missing Tests
Need tests for:
- ❌ payment_processor.py (0 tests)
- ❌ database_schema.py (0 tests)
- ⚠️ ml_anomaly_detector.py (10 tests, needs 20 more)

---

## 📈 Progress Roadmap

```
Week 1 (NOW):
├─ Day 1: ✅ Infrastructure setup (DONE)
├─ Day 2: ⏳ Fix real_scraper tests (TODO)
├─ Day 3: ⏳ Integration tests (TODO)
└─ Day 4: ⏳ 60% coverage (TODO)

Week 2:
├─ Day 5: Create payment_processor tests
├─ Day 6: Create database_schema tests
├─ Day 7: E2E tests
└─ Day 8: Load tests

Result: 70% coverage ✅
```

---

## 🎯 Quick Commands Reference

### Running Tests
```bash
# All tests
pytest

# Unit tests only
pytest tests/unit/

# Integration tests
pytest tests/integration/

# Specific file
pytest tests/unit/test_user_manager.py

# Specific test
pytest tests/unit/test_user_manager.py::TestPasswordHasher::test_hash_password_returns_string

# With coverage
pytest --cov=modules --cov-report=html

# Parallel (faster)
pytest -n auto

# Show print statements
pytest -s

# Very verbose
pytest -vv
```

### Load Testing
```bash
# Install locust
pip install locust

# Run load test (web UI)
locust -f tests/load/locustfile.py --host=http://localhost:8001

# Headless mode
locust -f tests/load/locustfile.py \
  --host=http://localhost:8001 \
  --users=20 --spawn-rate=2 \
  --run-time=120s --headless \
  --html=report.html
```

### Pre-commit
```bash
# Install
pip install pre-commit

# Setup
pre-commit install

# Run manually
pre-commit run --all-files

# Skip for one commit
git commit --no-verify

# Update hooks
pre-commit autoupdate
```

---

## 📁 File Organization

```
reviewsignal-5.0/
├── tests/
│   ├── unit/                      # ✅ Ready
│   │   ├── test_user_manager.py   # 60 tests ✅
│   │   ├── test_real_scraper.py   # 50 tests ⚠️
│   │   └── test_ml_anomaly_detector.py # 10 tests
│   │
│   ├── integration/               # ✅ Ready
│   │   └── test_api_endpoints.py  # 40 tests (to run)
│   │
│   └── load/                      # ✅ Ready
│       └── locustfile.py
│
├── pytest.ini                     # ✅ Configured
├── .coveragerc                    # ✅ Configured
├── .pre-commit-config.yaml        # ✅ Configured
├── requirements-dev.txt           # ✅ Created
│
└── docs/
    ├── TESTING_STRATEGY.md        # Complete plan
    ├── TESTING.md                 # User guide
    └── TESTING_IMPLEMENTATION_SUMMARY.md  # Progress
```

---

## 💡 Tips

### Debugging Failed Tests
```bash
# Drop into debugger on failure
pytest --pdb

# Show local variables
pytest -l

# Run failed tests only
pytest --lf

# Run failed first, then rest
pytest --ff
```

### Performance
```bash
# Show slowest tests
pytest --durations=10

# Run in parallel
pytest -n auto

# Skip slow tests
pytest -m "not slow"
```

### Coverage
```bash
# Generate report
pytest --cov=modules --cov-report=term-missing

# HTML report
pytest --cov=modules --cov-report=html

# XML (for CI)
pytest --cov=modules --cov-report=xml

# Fail if < 60%
pytest --cov=modules --cov-fail-under=60
```

---

## 🆘 Common Issues

### Import Errors
```bash
# Add to PYTHONPATH
export PYTHONPATH=/home/info_betsim/reviewsignal-5.0:$PYTHONPATH
```

### Database Connection Errors
```bash
# Check PostgreSQL is running
sudo systemctl status postgresql

# Use test database
export DB_NAME=reviewsignal_test
```

### Redis Connection Errors
```bash
# Check Redis is running
sudo systemctl status redis

# Or use fakeredis (for unit tests)
pip install fakeredis
```

---

## 📚 Documentation

- **TESTING_STRATEGY.md** - Complete testing strategy (6k lines)
- **TESTING.md** - Comprehensive user guide (500 lines)
- **TESTING_IMPLEMENTATION_SUMMARY.md** - Progress summary (400 lines)
- **This file** - Quick reference

---

## 🎉 What's Working

✅ **60 tests passing for user_manager.py**
✅ **80% coverage for authentication/JWT**
✅ **Infrastructure fully configured**
✅ **CI/CD pipeline ready**
✅ **Load tests created**
✅ **Pre-commit hooks configured**

---

## 🔜 Next Session

1. Fix real_scraper tests (25 failing → 5 failing)
2. Run integration tests
3. Add more ml_anomaly_detector tests
4. Push coverage to 60%

**Timeline:** 2-3 hours to 60% coverage

---

**Questions?** Read TESTING.md for detailed guide.
