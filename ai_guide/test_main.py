"""Offline FastAPI tests for the Ask-the-Map service."""

import pytest
import httpx
from fastapi.testclient import TestClient

from ai_guide import main
from ai_guide.planner_client import PlannerError


@pytest.fixture(autouse=True)
def offline_settings(monkeypatch):
    """Force parser fallback and local planner mocks for every test."""
    monkeypatch.setenv("USE_MOCK", "1")
    monkeypatch.setenv("LLM_PROVIDER", "none")


@pytest.fixture
def client():
    """Create an in-process API client."""
    return TestClient(main.app)


def test_health_reports_ok_without_api_key(client):
    """Health includes public configuration only."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "llm_provider": "none",
        "use_mock": True,
    }
    assert "GEMINI_API_KEY" not in response.text


def test_demo_question_returns_mock_route_and_warnings(client):
    """No-destination route uses assumed nearest ice and mock result."""
    response = client.post(
        "/ask", json={"question": "What's the safest route with 4 hours of oxygen?"}
    )
    body = response.json()
    assert response.status_code == 200
    assert body["route"]["status"] == "ok"
    assert body["route"]["path"]
    assert "No destination was given, so I assumed the nearest ice." in body["warnings"]
    assert "Using sample data, not live planner results." in body["warnings"]


def test_nearest_ice_returns_path(client):
    """An explicit ice destination produces a route path."""
    body = client.post("/ask", json={"question": "Take me to the nearest ice."}).json()
    assert body["route"]["status"] == "ok"
    assert body["route"]["path"]


def test_shelter_route_is_unsupported_without_planner_call(client, monkeypatch):
    """Shelter destinations are rejected before the planner is called."""
    async def fail_if_called(request):
        raise AssertionError("planner should not be called")

    monkeypatch.setattr(main, "call_planner", fail_if_called)
    body = client.post(
        "/ask", json={"question": "How do I get from the base to the closest shelter?"}
    ).json()
    assert body["route"]["status"] == "unsupported"
    assert body["route"]["path"] == []
    assert "supports ice only" in body["explanation"]


def test_radiation_request_adds_warning(client):
    """Unsupported radiation avoidance is disclosed in response warnings."""
    body = client.post(
        "/ask", json={"question": "Find a route to ice that avoids radiation."}
    ).json()
    assert body["route"]["status"] == "ok"
    assert "The planner cannot avoid radiation; radiation is a uniform reference value." in body["warnings"]


def test_battery_percentage_adds_conversion_warning(client):
    """Battery percentage is converted to planner Wh and disclosed."""
    body = client.post(
        "/ask",
        json={
            "question": "I only have 2 hours of oxygen and 40% battery. Can I reach ice?"
        },
    ).json()
    assert body["route"]["status"] == "ok"
    assert "Battery percentage converted to Wh assuming a 1000 Wh full battery." in body["warnings"]


def test_base_site_question_returns_sites_explanation(client):
    """Site intent returns the best base position without a route path."""
    body = client.post("/ask", json={"question": "Where should we build the base?"}).json()
    assert body["route"]["status"] == "sites"
    assert body["route"]["path"] == []
    assert body["route"]["planner"]["sites"][0]["position"] == {
        "row": 643,
        "col": 1226,
    }
    assert "best base candidate" in body["explanation"]


def test_non_navigation_question_returns_unknown(client, monkeypatch):
    """Unknown intent returns an explanation without calling the planner."""
    async def fail_if_called(request):
        raise AssertionError("planner should not be called")

    monkeypatch.setattr(main, "call_planner", fail_if_called)
    body = client.post(
        "/ask", json={"question": "What's the weather on Earth today?"}
    ).json()
    assert body["route"]["status"] == "unknown"
    assert body["route"]["path"] == []
    assert body["route"]["planner"] is None


def test_empty_question_is_rejected(client):
    """Empty questions fail request validation with HTTP 422."""
    response = client.post("/ask", json={"question": ""})
    assert response.status_code == 422


def test_planner_error_returns_error_status_not_http_500(client, monkeypatch):
    """Planner errors are returned as a friendly JSON response."""
    async def fail_planner(request):
        raise PlannerError("The planner's terrain data is temporarily unavailable.")

    monkeypatch.setattr(main, "call_planner", fail_planner)
    response = client.post("/ask", json={"question": "Take me to ice."})
    assert response.status_code == 200
    assert response.json()["route"]["status"] == "error"
    assert response.json()["route"]["path"] == []
    assert response.json()["explanation"] == "The planner's terrain data is temporarily unavailable."


def test_real_planner_connection_error_returns_error_without_mock(client, monkeypatch):
    """A real-mode connection failure becomes a friendly error response, not a mock."""
    monkeypatch.setenv("USE_MOCK", "0")

    async def fail_connect(self, *args, **kwargs):
        raise httpx.ConnectError("offline")

    monkeypatch.setattr(httpx.AsyncClient, "post", fail_connect)
    response = client.post("/ask", json={"question": "Take me to ice."})
    body = response.json()
    assert response.status_code == 200
    assert body["route"]["status"] == "error"
    assert body["route"]["path"] == []
    assert body["route"]["planner"] is None
    assert body["explanation"] == "I could not reach the route planner. Please check that it is running."
    assert "_mock" not in response.text


def test_question_length_over_500_is_rejected(client):
    """Questions above the requested size limit fail request validation."""
    response = client.post("/ask", json={"question": "a" * 501})
    assert response.status_code == 422
