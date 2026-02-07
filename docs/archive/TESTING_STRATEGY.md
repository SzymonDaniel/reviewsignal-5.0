# TESTING & CI/CD STRATEGY - ReviewSignal 5.0

**Utworzono:** 2026-01-30
**Status:** Implementation Plan
**Cel:** 60-80% test coverage, automated CI/CD, production-ready quality

---

## 1. CURRENT STATE (Baseline)

### Test Coverage (Before)
| Module | LOC | Tests | Coverage | Status |
|--------|-----|-------|----------|--------|
| real_scraper.py | 726 | 0 | 0% | ❌ Not tested |
| ml_anomaly_detector.py | 500 | 3 tests | ~15% | ⚠️ Basic only |
| payment_processor.py | 600 | 0 | 0% | ❌ Not tested |
| user_manager.py | 650 | 0 | 0% | ❌ Not tested |
| database_schema.py | 700 | 0 | 0% | ❌ Not tested |
| lead_receiver.py | 200 | 0 | 0% | ❌ Not tested |
| **TOTAL** | **3,376** | **3** | **~5%** | **❌ Critical** |

### CI/CD Status
- ✅ GitHub Actions workflow exists (.github/workflows/ci.yml)
- ✅ PostgreSQL + Redis services configured
- ✅ Linting (Ruff) configured
- ✅ Type checking (mypy) configured
- ⚠️ Coverage reporting configured but no tests
- ❌ Pre-commit hooks missing
- ❌ Integration tests missing
- ❌ E2E tests missing
- ❌ Load tests missing

---

## 2. TARGET STATE (Goals)

### Test Coverage (Target)
| Module | Target Coverage | Priority | Test Types |
|--------|----------------|----------|------------|
| real_scraper.py | 70% | HIGH | Unit + Integration |
| ml_anomaly_detector.py | 80% | HIGH | Unit + Integration |
| payment_processor.py | 65% | MEDIUM | Unit (mocked Stripe) |
| user_manager.py | 80% | HIGH | Unit + Integration |
| database_schema.py | 60% | MEDIUM | Integration |
| lead_receiver.py | 75% | HIGH | Unit + Integration + E2E |
| **OVERALL TARGET** | **70%+** | - | - |

### CI/CD Goals
- ✅ All tests pass before merge
- ✅ Pre-commit hooks (linting + basic tests)
- ✅ Automated coverage reporting
- ✅ Integration tests in CI
- ✅ Load testing (separate workflow)
- ✅ Security scanning
- ✅ Deploy only if tests pass

---

## 3. TESTING STRATEGY

### 3.1 Unit Tests (60% of effort)

**Scope:** Test individual functions/classes in isolation

**Modules to test:**
1. **real_scraper.py** (Priority: HIGH)
   - Test GoogleMapsRealScraper class
   - Test RateLimiter
   - Test CacheManager
   - Test DataQualityCalculator
   - Mock all external API calls (Google Maps)

2. **ml_anomaly_detector.py** (Priority: HIGH)
   - Expand existing tests (3 → 20+ tests)
   - Test MLAnomalyDetector class
   - Test SentimentAnalyzer
   - Test statistical functions
   - Test edge cases (empty data, outliers)

3. **payment_processor.py** (Priority: MEDIUM)
   - Test PaymentProcessor class
   - Test subscription management
   - Test webhook handling
   - Mock Stripe API completely

4. **user_manager.py** (Priority: HIGH)
   - Test UserManager class
   - Test JWT token generation/validation
   - Test password hashing/verification
   - Test role-based access control (RBAC)
   - Test session management

5. **database_schema.py** (Priority: MEDIUM)
   - Test SQLAlchemy models
   - Test relationships
   - Test validation constraints

### 3.2 Integration Tests (30% of effort)

**Scope:** Test multiple components working together

**Test scenarios:**
1. **Database Integration**
   - Test real PostgreSQL operations (using test DB)
   - Test CRUD operations for all models
   - Test complex queries
   - Test transactions and rollbacks

2. **API Integration**
   - Test FastAPI endpoints (lead_receiver.py)
   - Test request/response flows
   - Test authentication middleware
   - Test error handling

3. **Cache Integration**
   - Test Redis caching in scraper
   - Test cache invalidation
   - Test cache TTL

4. **End-to-End Flows**
   - Test: Lead creation → Database → Instantly sync
   - Test: Scraping → Cache → Database
   - Test: User signup → JWT → API access

### 3.3 E2E Tests (5% of effort)

**Scope:** Test entire system workflows

**Test scenarios:**
1. Complete lead pipeline (Apollo → n8n → API → DB → Instantly)
2. Complete scraping workflow (API call → scraping → caching → DB)
3. Complete auth flow (signup → login → token → API call)

### 3.4 Load Tests (5% of effort)

**Scope:** Test system under load

**Tools:** Locust or k6

**Test scenarios:**
1. Lead API endpoint (/api/lead)
   - Target: 100 req/sec
   - Duration: 5 minutes
   - Expected: <500ms p95 latency

2. Scraping system
   - Target: 50 concurrent scraping tasks
   - Expected: No crashes, stable memory

3. Database queries
   - Target: 1000 concurrent queries
   - Expected: <200ms p95 latency

---

## 4. IMPLEMENTATION PLAN

### Phase 1: Unit Tests Foundation (Week 1)
**Tasks:**
- [ ] Create test infrastructure
  - [ ] Update conftest.py with comprehensive fixtures
  - [ ] Create test utilities (mocks, factories)
  - [ ] Setup pytest.ini configuration

- [ ] Write unit tests (target: 40% coverage)
  - [ ] tests/test_user_manager.py (20+ tests)
  - [ ] tests/test_real_scraper.py (25+ tests)
  - [ ] Expand tests/test_ml_anomaly_detector.py (15+ more tests)

- [ ] Configure coverage reporting
  - [ ] pytest-cov configuration
  - [ ] HTML coverage reports
  - [ ] Coverage badges

**Success criteria:** 40%+ coverage, all tests passing

### Phase 2: Integration Tests (Week 1-2)
**Tasks:**
- [ ] Setup test database
  - [ ] Create reviewsignal_test database
  - [ ] Migration scripts for test DB
  - [ ] Fixtures for sample data

- [ ] Write integration tests
  - [ ] tests/integration/test_database.py
  - [ ] tests/integration/test_api_endpoints.py
  - [ ] tests/integration/test_cache.py

- [ ] Write E2E tests
  - [ ] tests/e2e/test_lead_pipeline.py
  - [ ] tests/e2e/test_auth_flow.py

**Success criteria:** 60%+ coverage, integration tests passing

### Phase 3: CI/CD Enhancement (Week 2)
**Tasks:**
- [ ] Fix CI/CD pipeline
  - [ ] Test GitHub Actions workflow
  - [ ] Fix any failing jobs
  - [ ] Add test database seeding

- [ ] Add pre-commit hooks
  - [ ] Install pre-commit framework
  - [ ] Configure hooks (ruff, mypy, pytest)
  - [ ] Create .pre-commit-config.yaml

- [ ] Enhance CI workflow
  - [ ] Add test result comments on PRs
  - [ ] Add coverage change reports
  - [ ] Add performance regression tests

**Success criteria:** CI passing, pre-commit working

### Phase 4: Load Testing (Week 2)
**Tasks:**
- [ ] Choose tool (Locust vs k6)
  - [ ] Research and evaluate
  - [ ] Install and configure

- [ ] Create load tests
  - [ ] tests/load/locustfile.py (if Locust)
  - [ ] tests/load/k6-script.js (if k6)

- [ ] Run baseline tests
  - [ ] Document current performance
  - [ ] Identify bottlenecks
  - [ ] Set performance budgets

**Success criteria:** Load tests running, baseline established

### Phase 5: Documentation & Monitoring (Week 2)
**Tasks:**
- [ ] Document testing
  - [ ] Update README with testing instructions
  - [ ] Create TESTING.md guide
  - [ ] Add code examples

- [ ] Setup test monitoring
  - [ ] Track test execution time
  - [ ] Track flaky tests
  - [ ] Setup alerts for failing tests

**Success criteria:** Documentation complete, monitoring active

---

## 5. TESTING TOOLS & FRAMEWORKS

### Core Testing
- **pytest** (9.0.2) - Test framework
- **pytest-cov** - Coverage reporting
- **pytest-asyncio** - Async test support
- **pytest-mock** - Mocking utilities

### Integration Testing
- **httpx** - API testing client
- **pytest-postgresql** - PostgreSQL fixtures
- **fakeredis** - Redis mocking

### Load Testing
- **Locust** (recommended) - Python-based, easy to integrate
- **k6** (alternative) - JavaScript-based, powerful

### Mocking & Fixtures
- **factory-boy** - Test data factories
- **faker** - Fake data generation
- **responses** - Mock HTTP requests
- **freezegun** - Mock datetime

### Code Quality
- **ruff** - Fast Python linter
- **mypy** - Static type checker
- **coverage** - Coverage measurement

---

## 6. TEST ORGANIZATION

### Directory Structure
```
reviewsignal-5.0/
├── tests/
│   ├── __init__.py
│   ├── conftest.py                    # Shared fixtures
│   ├── test_config.py                 # Config tests
│   │
│   ├── unit/                          # Unit tests (isolated)
│   │   ├── __init__.py
│   │   ├── test_real_scraper.py       # Scraper unit tests
│   │   ├── test_ml_anomaly_detector.py # ML unit tests
│   │   ├── test_payment_processor.py   # Payment unit tests
│   │   ├── test_user_manager.py        # Auth unit tests
│   │   └── test_database_schema.py     # Model unit tests
│   │
│   ├── integration/                    # Integration tests
│   │   ├── __init__.py
│   │   ├── test_database.py           # DB integration
│   │   ├── test_api_endpoints.py      # API integration
│   │   ├── test_cache.py              # Redis integration
│   │   └── test_scraping_flow.py      # Scraper → DB flow
│   │
│   ├── e2e/                           # End-to-end tests
│   │   ├── __init__.py
│   │   ├── test_lead_pipeline.py      # Full lead flow
│   │   └── test_auth_flow.py          # Auth flow
│   │
│   ├── load/                          # Load tests
│   │   ├── __init__.py
│   │   ├── locustfile.py              # Locust tests
│   │   └── README.md                  # Load test docs
│   │
│   └── fixtures/                      # Test data
│       ├── __init__.py
│       ├── sample_reviews.json
│       ├── sample_locations.json
│       └── sample_users.json
│
├── pytest.ini                         # Pytest configuration
├── .pre-commit-config.yaml            # Pre-commit hooks
└── .coveragerc                        # Coverage configuration
```

---

## 7. KEY METRICS TO TRACK

### Code Quality Metrics
- **Test Coverage:** 70%+ (critical paths: 80%+)
- **Test Count:** 150+ tests
- **Test Execution Time:** <2 minutes for full suite
- **Flaky Tests:** 0 (must be 100% deterministic)

### CI/CD Metrics
- **Build Time:** <5 minutes
- **Success Rate:** >95%
- **Deploy Frequency:** Multiple per day (when tests pass)

### Performance Metrics (from load tests)
- **API Latency (p95):** <500ms
- **Database Query Time (p95):** <200ms
- **Scraper Success Rate:** >95%
- **Memory Usage:** <500MB per service

---

## 8. RISK MITIGATION

### Common Testing Pitfalls
1. **Flaky tests** → Use deterministic mocks, avoid time-based tests
2. **Slow tests** → Mock external APIs, use in-memory databases for unit tests
3. **Brittle tests** → Test behavior, not implementation
4. **Test pollution** → Isolate tests, clean up after each test
5. **Incomplete coverage** → Focus on critical paths first

### CI/CD Risks
1. **Tests passing locally but failing in CI** → Use same Python version
2. **Database state issues** → Always use fresh test database
3. **Secrets in logs** → Never log sensitive data in tests
4. **Resource exhaustion** → Limit concurrent test jobs

---

## 9. SUCCESS CRITERIA

### Minimum Viable Testing (MVT)
- ✅ 60%+ test coverage
- ✅ All critical modules tested (user_manager, real_scraper, lead_receiver)
- ✅ CI/CD passing consistently
- ✅ Pre-commit hooks working
- ✅ Integration tests for database and API

### Production-Ready Testing
- ✅ 80%+ test coverage
- ✅ All modules tested (including edge cases)
- ✅ Load tests running and passing
- ✅ Performance regression detection
- ✅ E2E tests for all critical flows
- ✅ Automated deployment on test success

---

## 10. TIMELINE

| Week | Focus | Deliverables | Coverage Goal |
|------|-------|--------------|---------------|
| Week 1 Day 1-3 | Unit tests | 3 test files, pytest config | 40% |
| Week 1 Day 4-5 | Integration tests | 3 integration test files | 60% |
| Week 2 Day 1-2 | CI/CD fixes | Pre-commit, workflow fixes | 60% |
| Week 2 Day 3-4 | Load testing | Locust setup, baseline tests | 60% |
| Week 2 Day 5 | Documentation | TESTING.md, README updates | 70%+ |

**Total time:** 10-12 days (assuming full-time focus)

---

## 11. NEXT ACTIONS (Prioritized)

### IMMEDIATE (Today)
1. ✅ Create TESTING_STRATEGY.md (this file)
2. [ ] Install additional testing dependencies
3. [ ] Create pytest.ini configuration
4. [ ] Write first comprehensive test file (test_user_manager.py)

### THIS WEEK
1. [ ] Complete Phase 1 (Unit tests → 40% coverage)
2. [ ] Complete Phase 2 (Integration tests → 60% coverage)
3. [ ] Fix CI/CD pipeline

### NEXT WEEK
1. [ ] Complete Phase 3 (Pre-commit hooks)
2. [ ] Complete Phase 4 (Load testing)
3. [ ] Complete Phase 5 (Documentation)

---

**Status:** Ready to implement
**Next step:** Install testing dependencies and create pytest.ini

