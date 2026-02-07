"""
ReviewSignal Test Configuration
Pytest fixtures and test setup
"""
import os
import pytest

# Set test environment variables before importing modules
os.environ.setdefault('JWT_SECRET', 'test-jwt-secret-minimum-32-characters-long-for-testing')
os.environ.setdefault('DB_HOST', 'localhost')
os.environ.setdefault('DB_PORT', '5432')
os.environ.setdefault('DB_NAME', 'reviewsignal_test')
os.environ.setdefault('DB_USER', 'reviewsignal')
os.environ.setdefault('DB_PASS', 'testpassword')
os.environ.setdefault('REDIS_URL', 'redis://localhost:6379/1')
os.environ.setdefault('GOOGLE_MAPS_API_KEY', 'test_key')
os.environ.setdefault('STRIPE_API_KEY', 'sk_test_dummy')
os.environ.setdefault('STRIPE_WEBHOOK_SECRET', 'whsec_test')
os.environ.setdefault('APOLLO_API_KEY', 'test_apollo_key')


@pytest.fixture
def sample_location_data():
    """Sample location data for testing"""
    return {
        "place_id": "ChIJN1t_tDeuEmsRUsoyG83frY4",
        "name": "Test Starbucks",
        "address": "123 Test Street, New York, NY 10001",
        "rating": 4.5,
        "review_count": 150,
        "latitude": 40.7128,
        "longitude": -74.0060,
        "chain": "Starbucks",
        "city": "New York",
        "country": "USA"
    }


@pytest.fixture
def sample_review_data():
    """Sample review data for testing"""
    return {
        "author_name": "Test User",
        "rating": 5,
        "text": "Great coffee and friendly service!",
        "time": "2026-01-15T10:30:00Z",
        "language": "en"
    }


@pytest.fixture
def sample_user_data():
    """Sample user data for testing"""
    return {
        "email": "test@example.com",
        "password": "SecurePassword123!",
        "name": "Test User",
        "company": "Test Hedge Fund",
        "role": "analyst"
    }
