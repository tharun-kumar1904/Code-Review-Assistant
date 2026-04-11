"""
Tests for the /health endpoint and basic FastAPI app setup.
Skips gracefully if optional production dependencies (asyncpg, prometheus, etc.) are not installed.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

# Guard: skip all tests if production dependencies aren't installed
try:
    from main import app
    from fastapi.testclient import TestClient
    client = TestClient(app)
    HAS_DEPS = True
except ImportError as e:
    HAS_DEPS = False
    SKIP_REASON = f"Missing production dependency: {e}"

skip_if_no_deps = pytest.mark.skipif(not HAS_DEPS, reason="Missing production dependencies (run in Docker or install all deps)")


@skip_if_no_deps
class TestHealthEndpoint:
    def test_health_returns_200(self):
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_response_body(self):
        response = client.get("/health")
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "ai-code-review-assistant"


@skip_if_no_deps
class TestAppSetup:
    def test_app_title(self):
        assert app.title == "AI Code Review Assistant"

    def test_app_version(self):
        assert app.version == "1.0.0"

    def test_api_routes_registered(self):
        route_paths = [route.path for route in app.routes]
        assert "/health" in route_paths
        assert "/api/analyze-pr" in route_paths
        assert "/api/webhook/github" in route_paths
