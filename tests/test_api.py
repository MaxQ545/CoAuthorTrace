"""
Tests for API endpoints.
"""
import pytest
from fastapi.testclient import TestClient

from src.api.main import create_app
from src.database.models import init_database, get_engine, Base


@pytest.fixture(scope="module")
def test_client():
    """Create test client with PostgreSQL test database."""
    import os
    os.environ["COAUTHOR_DATABASE__POSTGRES_URL"] = "postgresql://coauthor:coauthor@localhost:5432/coauthor_test"
    os.environ["COAUTHOR_DATABASE__REDIS_ENABLED"] = "false"

    # Reset cached engine/session so new settings take effect
    import src.database.models as _models
    _models._engine = None
    _models._SessionLocal = None

    # Create tables in test database
    engine = init_database()

    app = create_app()

    with TestClient(app) as client:
        yield client

    # Cleanup: drop all tables after tests
    Base.metadata.drop_all(engine)
    _models._engine = None
    _models._SessionLocal = None


class TestRootEndpoints:
    """Tests for root endpoints."""

    def test_root(self, test_client):
        """Test root endpoint."""
        response = test_client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Coauthor Tracing API"
        assert "version" in data

    def test_health(self, test_client):
        """Test health endpoint."""
        response = test_client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"


class TestSystemEndpoints:
    """Tests for system endpoints."""

    def test_status(self, test_client):
        """Test status endpoint."""
        response = test_client.get("/api/v1/system/status")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "database" in data
        assert "crawl" in data

    def test_config(self, test_client):
        """Test config endpoint."""
        response = test_client.get("/api/v1/system/config")
        assert response.status_code == 200
        data = response.json()
        assert "scope" in data
        assert "crawler" in data
        assert "analysis" in data


class TestAuthorEndpoints:
    """Tests for author endpoints."""

    def test_search_empty(self, test_client):
        """Test search with no results."""
        response = test_client.get("/api/v1/authors/search?q=nonexistent")
        assert response.status_code == 200
        data = response.json()
        assert data["results"] == []
        assert data["total"] == 0

    def test_search_validation(self, test_client):
        """Test search input validation."""
        # Empty query should fail
        response = test_client.get("/api/v1/authors/search?q=")
        assert response.status_code == 422

    def test_get_author_not_found(self, test_client):
        """Test getting non-existent author."""
        response = test_client.get("/api/v1/authors/A0000000000")
        assert response.status_code == 404

    def test_top_relations_not_found(self, test_client):
        """Test top relations for non-existent author."""
        response = test_client.get("/api/v1/authors/A0000000000/top-relations")
        assert response.status_code == 404

    def test_top_relations_invalid_score_type(self, test_client):
        """Test top relations with invalid score type."""
        response = test_client.get(
            "/api/v1/authors/A0000000000/top-relations?score_type=invalid"
        )
        assert response.status_code == 422


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
