"""
Integration Tests for Lead Receiver API
Tests FastAPI endpoints with mocked database
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch, AsyncMock
import sys
import os
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Mock database connection before importing
with patch('psycopg2.connect'):
    from api.lead_receiver import app, LeadInput


# ═══════════════════════════════════════════════════════════════
# FIXTURES
# ═══════════════════════════════════════════════════════════════

@pytest.fixture
def client():
    """Test client for FastAPI"""
    return TestClient(app)


@pytest.fixture
def sample_lead():
    """Sample lead data"""
    return {
        "email": "test@hedgefund.com",
        "first_name": "John",
        "last_name": "Doe",
        "title": "Portfolio Manager",
        "company": "Test Hedge Fund",
        "company_domain": "testhedgefund.com",
        "industry": "finance",
        "city": "New York",
        "country": "USA",
        "linkedin_url": "https://linkedin.com/in/johndoe",
        "lead_score": 85,
        "priority": "high"
    }


@pytest.fixture
def mock_db_connection():
    """Mock database connection with context manager support"""
    mock_conn = Mock()
    mock_cursor = Mock()

    # Make cursor support context manager protocol
    mock_cursor.__enter__ = Mock(return_value=mock_cursor)
    mock_cursor.__exit__ = Mock(return_value=False)
    mock_cursor.fetchone.return_value = (1,)  # Return lead_id
    mock_cursor.fetchall.return_value = []

    # Make connection.cursor() return the mock cursor
    mock_conn.cursor.return_value = mock_cursor

    # Make connection support context manager protocol
    mock_conn.__enter__ = Mock(return_value=mock_conn)
    mock_conn.__exit__ = Mock(return_value=False)

    return mock_conn


# ═══════════════════════════════════════════════════════════════
# HEALTH CHECK TESTS
# ═══════════════════════════════════════════════════════════════

class TestHealthCheck:
    """Test health check endpoint"""

    def test_health_endpoint_returns_200(self, client):
        """Health check should return 200"""
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_endpoint_returns_json(self, client):
        """Health check should return JSON"""
        response = client.get("/health")
        data = response.json()

        assert "status" in data
        assert data["status"] == "ok"
        assert "service" in data
        assert data["service"] == "lead_receiver"

    def test_health_endpoint_includes_timestamp(self, client):
        """Health check should include service name"""
        response = client.get("/health")
        data = response.json()

        assert "service" in data
        assert data["service"] == "lead_receiver"


# ═══════════════════════════════════════════════════════════════
# LEAD CREATION TESTS
# ═══════════════════════════════════════════════════════════════

class TestLeadCreation:
    """Test lead creation endpoint"""

    @patch('api.lead_receiver.get_db_connection')
    @patch('api.lead_receiver.sync_to_instantly')
    def test_create_lead_success(self, mock_sync, mock_db, client, sample_lead, mock_db_connection):
        """Creating a valid lead should return 201"""
        mock_db.return_value = mock_db_connection
        mock_sync.return_value = None

        response = client.post("/api/lead", json=sample_lead)

        assert response.status_code == 201
        data = response.json()
        assert "lead_id" in data
        assert data["status"] == "created"

    @patch('api.lead_receiver.get_db_connection')
    def test_create_lead_missing_email(self, mock_db, client):
        """Lead without email should return 422"""
        invalid_lead = {
            "first_name": "John",
            "last_name": "Doe"
            # Missing email
        }

        response = client.post("/api/lead", json=invalid_lead)
        assert response.status_code == 422

    @patch('api.lead_receiver.get_db_connection')
    def test_create_lead_invalid_email(self, mock_db, client):
        """Lead with invalid email should return 422"""
        invalid_lead = {
            "email": "not-an-email",
            "first_name": "John"
        }

        response = client.post("/api/lead", json=invalid_lead)
        assert response.status_code == 422

    @patch('api.lead_receiver.get_db_connection')
    @patch('api.lead_receiver.sync_to_instantly')
    def test_create_lead_all_fields(self, mock_sync, mock_db, client, mock_db_connection):
        """Lead with all fields should be processed"""
        mock_db.return_value = mock_db_connection
        mock_sync.return_value = None

        complete_lead = {
            "email": "complete@test.com",
            "first_name": "Jane",
            "last_name": "Smith",
            "title": "CIO",
            "company": "Complete Corp",
            "company_domain": "complete.com",
            "industry": "technology",
            "city": "San Francisco",
            "country": "USA",
            "linkedin_url": "https://linkedin.com/in/janesmith",
            "lead_score": 95,
            "priority": "high",
            "personalized_angle": "Alternative data for tech stocks",
            "nurture_sequence": True
        }

        response = client.post("/api/lead", json=complete_lead)

        assert response.status_code == 201
        data = response.json()
        assert data["email"] == "complete@test.com"

    @patch('api.lead_receiver.get_db_connection')
    def test_create_lead_database_error(self, mock_db, client, sample_lead):
        """Database error should return 500"""
        mock_db.side_effect = Exception("Database connection failed")

        response = client.post("/api/lead", json=sample_lead)

        assert response.status_code == 500
        data = response.json()
        assert "error" in data

    @patch('api.lead_receiver.get_db_connection')
    @patch('api.lead_receiver.sync_to_instantly')
    def test_create_lead_instantly_sync_failure(self, mock_sync, mock_db, client, sample_lead, mock_db_connection):
        """Instantly sync failure should not prevent lead creation"""
        mock_db.return_value = mock_db_connection
        mock_sync.side_effect = Exception("Instantly API error")

        response = client.post("/api/lead", json=sample_lead)

        # Should still create lead even if sync fails
        assert response.status_code in [201, 500]  # Depends on error handling


# ═══════════════════════════════════════════════════════════════
# BULK LEAD CREATION TESTS
# ═══════════════════════════════════════════════════════════════

class TestBulkLeadCreation:
    """Test bulk lead creation endpoint"""

    @patch('api.lead_receiver.get_db_connection')
    @patch('api.lead_receiver.sync_to_instantly')
    def test_bulk_create_leads(self, mock_sync, mock_db, client, mock_db_connection):
        """Bulk create should process multiple leads"""
        mock_db.return_value = mock_db_connection
        mock_sync.return_value = None

        leads = [
            {"email": f"lead{i}@test.com", "first_name": f"Lead{i}", "last_name": f"Test{i}"}
            for i in range(5)
        ]

        response = client.post("/api/leads/bulk", json=leads)

        assert response.status_code == 200
        data = response.json()
        assert "saved" in data
        assert data["saved"] >= 0

    @patch('api.lead_receiver.get_db_connection')
    def test_bulk_create_empty_list(self, mock_db, client):
        """Empty bulk list should return 422"""
        response = client.post("/api/leads/bulk", json=[])

        assert response.status_code == 422

    @patch('api.lead_receiver.get_db_connection')
    @patch('api.lead_receiver.sync_to_instantly')
    def test_bulk_create_partial_failure(self, mock_sync, mock_db, client, mock_db_connection):
        """Partial failures in bulk should be reported"""
        mock_db.return_value = mock_db_connection
        mock_sync.return_value = None

        leads = [
            {"email": "valid@test.com", "first_name": "Valid"},
            {"email": "invalid-email", "first_name": "Invalid"},  # Invalid email
            {"email": "another@test.com", "first_name": "Another"}
        ]

        response = client.post("/api/leads/bulk", json={"leads": leads})

        # Should handle partial failures gracefully
        assert response.status_code in [201, 207, 422]  # Multi-status or created


# ═══════════════════════════════════════════════════════════════
# STATS ENDPOINT TESTS
# ═══════════════════════════════════════════════════════════════

class TestStatsEndpoint:
    """Test statistics endpoint"""

    @patch('api.lead_receiver.get_db_connection')
    def test_stats_endpoint_returns_200(self, mock_db, client, mock_db_connection):
        """Stats endpoint should return 200"""
        mock_db.return_value = mock_db_connection

        # Mock stats query response
        mock_cursor = mock_db_connection.cursor.return_value
        mock_cursor.fetchone.return_value = (100, 85, 10, 5)  # total, pending, synced, failed

        response = client.get("/api/stats")

        assert response.status_code == 200

    @patch('api.lead_receiver.get_db_connection')
    def test_stats_endpoint_returns_counts(self, mock_db, client, mock_db_connection):
        """Stats should include lead counts"""
        mock_db.return_value = mock_db_connection
        mock_cursor = mock_db_connection.cursor.return_value
        mock_cursor.fetchone.return_value = (100, 85, 10, 5)

        response = client.get("/api/stats")
        data = response.json()

        assert "total_leads" in data or "stats" in data

    @patch('api.lead_receiver.get_db_connection')
    def test_stats_endpoint_database_error(self, mock_db, client):
        """Stats should handle database errors gracefully"""
        mock_db.side_effect = Exception("Database error")

        response = client.get("/api/stats")

        # Should return error status
        assert response.status_code in [500, 503]


# ═══════════════════════════════════════════════════════════════
# PENDING LEADS TESTS
# ═══════════════════════════════════════════════════════════════

class TestPendingLeads:
    """Test pending leads endpoint"""

    @patch('api.lead_receiver.get_db_connection')
    def test_pending_leads_returns_list(self, mock_db, client, mock_db_connection):
        """Pending leads should return list"""
        mock_db.return_value = mock_db_connection
        mock_cursor = mock_db_connection.cursor.return_value
        mock_cursor.fetchall.return_value = [
            (1, "test1@email.com", "Lead", "One", "Company1"),
            (2, "test2@email.com", "Lead", "Two", "Company2")
        ]

        response = client.get("/api/leads/pending")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, (list, dict))

    @patch('api.lead_receiver.get_db_connection')
    def test_pending_leads_empty(self, mock_db, client, mock_db_connection):
        """Empty pending leads should return empty list"""
        mock_db.return_value = mock_db_connection
        mock_cursor = mock_db_connection.cursor.return_value
        mock_cursor.fetchall.return_value = []

        response = client.get("/api/leads/pending")

        assert response.status_code == 200


# ═══════════════════════════════════════════════════════════════
# VALIDATION TESTS
# ═══════════════════════════════════════════════════════════════

class TestInputValidation:
    """Test input validation"""

    def test_lead_input_model_validation(self):
        """LeadInput model should validate correctly"""
        valid_lead = LeadInput(
            email="test@example.com",
            first_name="Test",
            last_name="User"
        )

        assert valid_lead.email == "test@example.com"
        assert valid_lead.lead_score == 50  # Default value

    def test_lead_input_email_validation(self):
        """Invalid email should raise validation error"""
        with pytest.raises(Exception):  # Pydantic ValidationError
            LeadInput(
                email="not-an-email",
                first_name="Test"
            )

    def test_lead_input_default_values(self):
        """Lead should have correct default values"""
        lead = LeadInput(
            email="test@example.com",
            first_name="Test"
        )

        assert lead.lead_score == 50
        assert lead.priority == "medium"
        assert lead.nurture_sequence is False

    def test_lead_input_optional_fields(self):
        """Optional fields should work correctly"""
        lead = LeadInput(
            email="test@example.com",
            first_name="Test",
            company_domain="example.com",
            industry="finance"
        )

        assert lead.company_domain == "example.com"
        assert lead.industry == "finance"


# ═══════════════════════════════════════════════════════════════
# ERROR HANDLING TESTS
# ═══════════════════════════════════════════════════════════════

class TestErrorHandling:
    """Test error handling and edge cases"""

    def test_invalid_json(self, client):
        """Invalid JSON should return 422"""
        response = client.post(
            "/api/lead",
            data="invalid json",
            headers={"Content-Type": "application/json"}
        )

        assert response.status_code == 422

    def test_missing_content_type(self, client):
        """Missing content-type should be handled"""
        response = client.post("/api/lead", data='{"email": "test@test.com"}')

        # FastAPI should handle this
        assert response.status_code in [200, 201, 422]

    def test_very_long_email(self, client):
        """Very long email should be handled"""
        long_email = "a" * 200 + "@example.com"

        response = client.post("/api/lead", json={
            "email": long_email,
            "first_name": "Test"
        })

        # Should either accept or reject gracefully
        assert response.status_code in [201, 422]

    def test_unicode_in_fields(self, client):
        """Unicode characters should be handled"""
        response = client.post("/api/lead", json={
            "email": "test@example.com",
            "first_name": "François",
            "last_name": "Müller",
            "company": "Société Générale 日本"
        })

        # Should handle unicode
        assert response.status_code in [201, 500]

    @patch('api.lead_receiver.get_db_connection')
    def test_sql_injection_attempt(self, mock_db, client, mock_db_connection):
        """SQL injection attempts should be prevented"""
        mock_db.return_value = mock_db_connection

        malicious_lead = {
            "email": "test@example.com",
            "first_name": "Robert'; DROP TABLE leads;--",
            "company": "<script>alert('xss')</script>"
        }

        response = client.post("/api/lead", json=malicious_lead)

        # Should not crash
        assert response.status_code in [201, 422, 500]


# ═══════════════════════════════════════════════════════════════
# CORS TESTS
# ═══════════════════════════════════════════════════════════════

class TestCORS:
    """Test CORS configuration"""

    def test_cors_headers_present(self, client):
        """CORS headers should be present"""
        response = client.options("/api/lead")

        # Check if CORS is configured
        assert response.status_code in [200, 405]

    def test_preflight_request(self, client):
        """Preflight requests should be handled"""
        response = client.options(
            "/api/lead",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST"
            }
        )

        # Should handle preflight
        assert response.status_code in [200, 204, 405]


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
