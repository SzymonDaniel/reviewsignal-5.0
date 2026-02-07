"""
Locust Load Tests for ReviewSignal API
Run with: locust -f tests/load/locustfile.py --host=http://localhost:8001
"""
from locust import HttpUser, task, between, events
import random
import json
from datetime import datetime


class LeadAPIUser(HttpUser):
    """Simulate user hitting Lead Receiver API"""

    # Wait 1-5 seconds between requests
    wait_time = between(1, 5)

    # Sample data for generating leads
    companies = ["Citadel", "Renaissance", "Bridgewater", "Two Sigma", "DE Shaw"]
    titles = ["Portfolio Manager", "Quantitative Analyst", "Head of Research", "CIO"]
    cities = ["New York", "London", "Chicago", "San Francisco", "Boston"]

    def on_start(self):
        """Called when a user starts"""
        self.client.verify = False  # Disable SSL verification for local testing

    @task(3)
    def health_check(self):
        """Health check endpoint (high frequency)"""
        with self.client.get("/health", catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Health check failed: {response.status_code}")

    @task(5)
    def create_lead(self):
        """Create single lead (medium frequency)"""
        lead_data = {
            "email": f"test_{random.randint(1000, 9999)}@{random.choice(['hedge', 'capital', 'investments'])}.com",
            "first_name": random.choice(["John", "Jane", "Michael", "Sarah", "David"]),
            "last_name": random.choice(["Smith", "Johnson", "Williams", "Brown", "Jones"]),
            "title": random.choice(self.titles),
            "company": random.choice(self.companies),
            "city": random.choice(self.cities),
            "lead_score": random.randint(50, 100),
            "priority": random.choice(["high", "medium", "low"])
        }

        with self.client.post(
            "/api/lead",
            json=lead_data,
            headers={"Content-Type": "application/json"},
            catch_response=True
        ) as response:
            if response.status_code == 201:
                response.success()
            elif response.status_code == 409:  # Duplicate email
                response.success()
            else:
                response.failure(f"Failed to create lead: {response.status_code}")

    @task(1)
    def get_stats(self):
        """Get stats endpoint (low frequency)"""
        with self.client.get("/api/stats", catch_response=True) as response:
            if response.status_code == 200:
                try:
                    data = response.json()
                    response.success()
                except json.JSONDecodeError:
                    response.failure("Invalid JSON response")
            else:
                response.failure(f"Stats endpoint failed: {response.status_code}")

    @task(1)
    def get_pending_leads(self):
        """Get pending leads (low frequency)"""
        with self.client.get("/api/leads/pending", catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Pending leads failed: {response.status_code}")

    @task(1)
    def bulk_create_leads(self):
        """Create bulk leads (low frequency, high load)"""
        leads = [
            {
                "email": f"bulk_{random.randint(10000, 99999)}@test.com",
                "first_name": f"User{i}",
                "last_name": "Test",
                "company": random.choice(self.companies)
            }
            for i in range(5)  # 5 leads per bulk request
        ]

        with self.client.post(
            "/api/leads/bulk",
            json={"leads": leads},
            headers={"Content-Type": "application/json"},
            catch_response=True
        ) as response:
            if response.status_code in [201, 207]:  # Created or Multi-status
                response.success()
            else:
                response.failure(f"Bulk create failed: {response.status_code}")


# Custom event handlers for reporting
@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Called when load test starts"""
    print("\n" + "="*70)
    print("🚀 REVIEWSIGNAL LOAD TEST STARTING")
    print("="*70)
    print(f"Start time: {datetime.now().isoformat()}")
    print(f"Target host: {environment.host}")
    print(f"Number of users: {environment.runner.target_user_count if hasattr(environment.runner, 'target_user_count') else 'N/A'}")
    print("="*70 + "\n")


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Called when load test stops"""
    print("\n" + "="*70)
    print("🏁 REVIEWSIGNAL LOAD TEST COMPLETED")
    print("="*70)
    print(f"End time: {datetime.now().isoformat()}")

    if environment.stats.total.num_requests > 0:
        print(f"\n📊 SUMMARY:")
        print(f"Total requests: {environment.stats.total.num_requests}")
        print(f"Total failures: {environment.stats.total.num_failures}")
        print(f"Failure rate: {environment.stats.total.fail_ratio * 100:.2f}%")
        print(f"Average response time: {environment.stats.total.avg_response_time:.2f}ms")
        print(f"Min response time: {environment.stats.total.min_response_time:.2f}ms")
        print(f"Max response time: {environment.stats.total.max_response_time:.2f}ms")
        print(f"Requests per second: {environment.stats.total.total_rps:.2f}")

        # Performance benchmarks
        print(f"\n🎯 PERFORMANCE BENCHMARKS:")
        avg_rt = environment.stats.total.avg_response_time

        if avg_rt < 100:
            print(f"✅ EXCELLENT: {avg_rt:.2f}ms (target: <100ms)")
        elif avg_rt < 500:
            print(f"✅ GOOD: {avg_rt:.2f}ms (target: <500ms)")
        elif avg_rt < 1000:
            print(f"⚠️  ACCEPTABLE: {avg_rt:.2f}ms (target: <1000ms)")
        else:
            print(f"❌ SLOW: {avg_rt:.2f}ms (needs optimization)")

    print("="*70 + "\n")


# Slow attack user (stress test)
class SlowAttackUser(HttpUser):
    """Slow, persistent attacker for stress testing"""

    wait_time = between(0.1, 0.5)  # Very fast requests

    @task
    def rapid_health_checks(self):
        """Rapid-fire health checks"""
        self.client.get("/health")


# For running different test scenarios
class ReadOnlyUser(HttpUser):
    """User that only reads data (for read performance testing)"""

    wait_time = between(0.5, 2)

    @task(5)
    def health_check(self):
        self.client.get("/health")

    @task(3)
    def get_stats(self):
        self.client.get("/api/stats")

    @task(2)
    def get_pending_leads(self):
        self.client.get("/api/leads/pending")


# Usage examples:
"""
# Basic load test (10 users, 2 users/sec spawn rate)
locust -f tests/load/locustfile.py --host=http://localhost:8001 --users=10 --spawn-rate=2 --run-time=60s

# Stress test (100 users)
locust -f tests/load/locustfile.py --host=http://localhost:8001 --users=100 --spawn-rate=10 --run-time=300s

# Read-only test
locust -f tests/load/locustfile.py --host=http://localhost:8001 --users=50 --spawn-rate=5 ReadOnlyUser

# Headless mode (no web UI)
locust -f tests/load/locustfile.py --host=http://localhost:8001 --users=20 --spawn-rate=2 --run-time=120s --headless

# With HTML report
locust -f tests/load/locustfile.py --host=http://localhost:8001 --users=20 --spawn-rate=2 --run-time=120s --headless --html=load_test_report.html
"""
