# ReviewSignal 5.0 - Testing Guide

**Last Updated:** 2026-01-30
**Test Coverage Target:** 70%+

---

## Quick Start

### Install Dependencies
```bash
cd ~/reviewsignal-5.0
pip install -r requirements-dev.txt
```

### Run All Tests
```bash
pytest
```

### Run with Coverage
```bash
pytest --cov=modules --cov=api --cov-report=html
```

### View Coverage Report
```bash
# Open in browser
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux
```

---

## Test Organization

```
tests/
├── unit/                    # Unit tests (isolated components)
│   ├── test_user_manager.py       # ~60 tests
│   ├── test_real_scraper.py       # ~50 tests
│   └── test_ml_anomaly_detector.py # ~10 tests
│
├── integration/             # Integration tests (multiple components)
│   ├── test_api_endpoints.py      # ~40 tests
│   ├── test_database.py           # (to be added)
│   └── test_cache.py              # (to be added)
│
├── e2e/                     # End-to-end tests
│   └── test_lead_pipeline.py      # (to be added)
│
└── load/                    # Load tests
    └── locustfile.py              # Locust scenarios
```

---

## Running Tests

### By Type
```bash
# Unit tests only
pytest tests/unit/

# Integration tests only
pytest tests/integration/

# Specific test file
pytest tests/unit/test_user_manager.py

# Specific test class
pytest tests/unit/test_user_manager.py::TestPasswordHasher

# Specific test function
pytest tests/unit/test_user_manager.py::TestPasswordHasher::test_hash_password_returns_string
```

### By Markers
```bash
# Fast tests only (exclude slow tests)
pytest -m "not slow"

# Integration tests only
pytest -m integration

# Tests requiring database
pytest -m requires_db

# Skip tests requiring external APIs
pytest -m "not requires_api"
```

### Parallel Execution
```bash
# Run tests in parallel (faster)
pytest -n auto

# Run tests on 4 cores
pytest -n 4
```

### Verbose Output
```bash
# Show test names
pytest -v

# Show stdout/print statements
pytest -s

# Show local variables on failure
pytest -l

# Combination
pytest -vsl
```

---

## Coverage

### Generate Coverage Report
```bash
# HTML report
pytest --cov=modules --cov=api --cov-report=html

# Terminal report
pytest --cov=modules --cov=api --cov-report=term-missing

# XML report (for CI)
pytest --cov=modules --cov=api --cov-report=xml

# Fail if coverage < 60%
pytest --cov=modules --cov-fail-under=60
```

### Coverage Targets

| Module | Current | Target | Priority |
|--------|---------|--------|----------|
| user_manager.py | ~80% | 80% | ✅ HIGH |
| real_scraper.py | ~70% | 70% | ✅ HIGH |
| lead_receiver.py | ~75% | 75% | ✅ HIGH |
| ml_anomaly_detector.py | ~15% | 80% | ⚠️ TODO |
| payment_processor.py | 0% | 65% | ⚠️ TODO |
| database_schema.py | 0% | 60% | ⚠️ TODO |

---

## Pre-commit Hooks

### Setup
```bash
# Install pre-commit
pip install pre-commit

# Install git hooks
pre-commit install

# Run manually on all files
pre-commit run --all-files
```

### What Gets Checked
- ✅ Code formatting (Black, isort)
- ✅ Linting (Ruff)
- ✅ Type checking (mypy)
- ✅ Security (Bandit)
- ✅ Fast tests (pytest -m "not slow")

### Skip Hooks (if needed)
```bash
# Skip all hooks
git commit --no-verify

# Skip specific hook
SKIP=pytest-fast git commit -m "message"
```

---

## Load Testing

### Install Locust
```bash
pip install locust
```

### Run Load Tests

#### Web UI Mode
```bash
locust -f tests/load/locustfile.py --host=http://localhost:8001
```
Then open: http://localhost:8089

#### Headless Mode
```bash
# 20 users, 2 users/sec spawn rate, 2 minutes
locust -f tests/load/locustfile.py \
  --host=http://localhost:8001 \
  --users=20 \
  --spawn-rate=2 \
  --run-time=120s \
  --headless
```

#### Stress Test
```bash
# 100 users, 10 users/sec, 5 minutes
locust -f tests/load/locustfile.py \
  --host=http://localhost:8001 \
  --users=100 \
  --spawn-rate=10 \
  --run-time=300s \
  --headless \
  --html=stress_test_report.html
```

#### Read-Only Test
```bash
locust -f tests/load/locustfile.py \
  --host=http://localhost:8001 \
  --users=50 \
  --spawn-rate=5 \
  ReadOnlyUser
```

### Performance Benchmarks

| Metric | Target | Acceptable | Needs Work |
|--------|--------|------------|------------|
| Avg Response Time | <100ms | <500ms | >500ms |
| P95 Response Time | <200ms | <1000ms | >1000ms |
| Requests/sec | >100 | >50 | <50 |
| Error Rate | <1% | <5% | >5% |

---

## CI/CD Testing

### GitHub Actions

Tests run automatically on:
- Every push to `main` or `develop`
- Every pull request to `main`

### Workflow Steps
1. ✅ Setup Python + PostgreSQL + Redis
2. ✅ Install dependencies
3. ✅ Lint with Ruff
4. ✅ Type check with mypy
5. ✅ Run tests with coverage
6. ✅ Upload coverage to Codecov
7. ✅ Security scan with Trivy

### View CI Results
- GitHub Actions: `.github/workflows/ci.yml`
- Coverage: Codecov (if configured)

---

## Writing Tests

### Test Structure
```python
import pytest

class TestMyFeature:
    """Test my feature"""

    def test_basic_functionality(self):
        """Test should do something"""
        result = my_function()
        assert result == expected

    @pytest.mark.slow
    def test_slow_operation(self):
        """Slow test (marked)"""
        # Test code

    @pytest.fixture
    def sample_data(self):
        """Fixture for test data"""
        return {"key": "value"}

    def test_with_fixture(self, sample_data):
        """Test using fixture"""
        assert sample_data["key"] == "value"
```

### Mocking
```python
from unittest.mock import Mock, patch

def test_with_mock():
    """Test with mocked dependency"""
    with patch('module.external_api_call') as mock_api:
        mock_api.return_value = {"status": "success"}

        result = my_function_that_calls_api()
        assert result["status"] == "success"
        mock_api.assert_called_once()
```

### Async Tests
```python
@pytest.mark.asyncio
async def test_async_function():
    """Test async function"""
    result = await my_async_function()
    assert result is not None
```

---

## Debugging Tests

### Run Failed Tests Only
```bash
# Run only tests that failed last time
pytest --lf

# Run failed tests first, then others
pytest --ff
```

### Drop into Debugger
```bash
# Drop into pdb on failure
pytest --pdb

# Drop into pdb on first failure
pytest -x --pdb
```

### Show Print Statements
```bash
# Show all output
pytest -s

# Show output only for failed tests
pytest --capture=no
```

### Increase Verbosity
```bash
# Very verbose
pytest -vv

# Show full diff
pytest -vv --tb=long
```

---

## Test Data

### Fixtures
Common fixtures are in `tests/conftest.py`:
- `sample_location_data` - Sample location from Google Maps
- `sample_review_data` - Sample review
- `sample_user_data` - Sample user

### Factories
Use factory-boy for generating test data:
```python
from factory import Factory

class UserFactory(Factory):
    class Meta:
        model = User

    email = "test@example.com"
    name = "Test User"
```

### Faker
Use Faker for random test data:
```python
from faker import Faker

fake = Faker()
email = fake.email()
name = fake.name()
```

---

## Common Issues

### Import Errors
```bash
# Add project root to PYTHONPATH
export PYTHONPATH=/home/info_betsim/reviewsignal-5.0:$PYTHONPATH
```

### Database Connection Errors
- Ensure PostgreSQL is running
- Check credentials in conftest.py
- Use test database: `reviewsignal_test`

### Redis Connection Errors
- Ensure Redis is running
- Use Redis database 1 for tests (not 0)
- Or use fakeredis for unit tests

### Slow Tests
```bash
# Run only fast tests
pytest -m "not slow"

# Show slowest 10 tests
pytest --durations=10
```

---

## Continuous Improvement

### Coverage Goals
- Week 1: 40% coverage
- Week 2: 60% coverage
- Week 3: 70% coverage
- Month 1: 80% coverage

### Adding Tests
1. Identify untested module
2. Write unit tests first (isolated)
3. Add integration tests (with dependencies)
4. Add E2E tests (full workflow)
5. Run coverage: `pytest --cov`
6. Repeat until target coverage reached

### Test Maintenance
- Fix flaky tests immediately
- Update tests when code changes
- Remove obsolete tests
- Keep tests fast (<2 min total)

---

## Resources

- [pytest documentation](https://docs.pytest.org/)
- [pytest-cov documentation](https://pytest-cov.readthedocs.io/)
- [Locust documentation](https://docs.locust.io/)
- [Pre-commit documentation](https://pre-commit.com/)
- [Coverage.py documentation](https://coverage.readthedocs.io/)

---

**Questions?** Check `TESTING_STRATEGY.md` for detailed strategy and implementation plan.
