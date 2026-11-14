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


def _planner_result(status):
    """Make a small result with the real planner response shape."""
    result = {
        "status": status,
        "reason": None if status == "ok" else "no_feasible_route",
        "_mock": False,
        "route": None,
        "metrics": None,
    }
    if status == "ok":
        result["route"] = {
            "outbound": [{"lat": 46.0, "lon": -165.0}],
            "return_path": [],
        }
        result["metrics"] = {
            "distance_km": 6.0,
            "hours": 1.0,
            "oxygen_remaining_hours": 1.0,
            "battery_remaining_wh": 600.0,
            "battery_wh": 400.0,
        }
    return result


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


@pytest.mark.parametrize("first_status", ["infeasible", "search_limit"])
def test_map_start_failure_retries_from_default_start(client, monkeypatch, first_status):
    """Infeasible map-point routes retry once from the configured demo start."""
    monkeypatch.setenv("USE_MOCK", "0")
    monkeypatch.setenv("DEFAULT_START_ROW", "643")
    monkeypatch.setenv("DEFAULT_START_COL", "1226")
    requests = []
    results = [_planner_result(first_status), _planner_result("ok")]

    async def planner(request):
        requests.append(request)
        return results.pop(0)

    monkeypatch.setattr(main, "call_planner", planner)
    response = client.post(
        "/ask",
        json={
            "question": "I have 2 hours of oxygen and 40% battery. Go to ice and avoid dust.",
            "map_start": {"lon": -165.18, "lat": 46.32},
        },
    )
    body = response.json()
    assert response.status_code == 200
    assert len(requests) == 2
    assert requests[0]["start"] == {"lon": -165.18, "lat": 46.32}
    assert requests[1]["start"] == {"row": 643, "col": 1226}
    assert {key: value for key, value in requests[0].items() if key != "start"} == {
        key: value for key, value in requests[1].items() if key != "start"
    }
    assert body["route"]["status"] == "ok"
    assert body["route"]["planner"]["status"] == "ok"
    assert body["route"]["path"] == [[46.0, -165.0]]
    assert "No route was found from the map point, so I used the demo start instead. The route does not start at point A." in body["warnings"]


def test_map_start_retry_warning_is_returned(client, monkeypatch):
    """The demo-start warning is included when retrying the planner succeeds."""
    monkeypatch.setenv("USE_MOCK", "0")
    results = [_planner_result("infeasible"), _planner_result("ok")]

    async def planner(request):
        return results.pop(0)

    monkeypatch.setattr(main, "call_planner", planner)
    body = client.post(
        "/ask",
        json={"question": "Take me to ice.", "map_start": {"lon": -165.18, "lat": 46.32}},
    ).json()
    assert "No route was found from the map point, so I used the demo start instead. The route does not start at point A." in body["warnings"]


def test_ok_map_start_result_does_not_retry(client, monkeypatch):
    """A successful map-point route is used directly."""
    monkeypatch.setenv("USE_MOCK", "0")
    calls = []

    async def planner(request):
        calls.append(request)
        return _planner_result("ok")

    monkeypatch.setattr(main, "call_planner", planner)
    body = client.post(
        "/ask",
        json={"question": "Take me to ice.", "map_start": {"lon": -165.18, "lat": 46.32}},
    ).json()
    assert len(calls) == 1
    assert body["route"]["status"] == "ok"
    assert not any("used the demo start" in warning for warning in body["warnings"])


def test_infeasible_without_map_start_does_not_retry(client, monkeypatch):
    """A failed request without a supplied map point is not retried."""
    monkeypatch.setenv("USE_MOCK", "0")
    calls = []

    async def planner(request):
        calls.append(request)
        return _planner_result("infeasible")

    monkeypatch.setattr(main, "call_planner", planner)
    body = client.post("/ask", json={"question": "Take me to ice."}).json()
    assert len(calls) == 1
    assert body["route"]["status"] == "infeasible"
    assert not any("used the demo start" in warning for warning in body["warnings"])


def test_planner_error_with_map_start_does_not_retry(client, monkeypatch):
    """Connection failures remain errors and do not trigger a demo-start retry."""
    monkeypatch.setenv("USE_MOCK", "0")
    calls = []

    async def planner(request):
        calls.append(request)
        raise PlannerError("I could not reach the route planner. Please check that it is running.")

    monkeypatch.setattr(main, "call_planner", planner)
    response = client.post(
        "/ask",
        json={"question": "Take me to ice.", "map_start": {"lon": -165.18, "lat": 46.32}},
    )
    assert len(calls) == 1
    assert response.json()["route"]["status"] == "error"
    assert response.json()["explanation"] == "I could not reach the route planner. Please check that it is running."


def test_mock_mode_does_not_retry_map_start_failure(client, monkeypatch):
    """Mock mode uses one planner result and never retries with a demo start."""
    monkeypatch.setenv("USE_MOCK", "1")
    calls = []

    async def planner(request):
        calls.append(request)
        return _planner_result("infeasible")

    monkeypatch.setattr(main, "call_planner", planner)
    body = client.post(
        "/ask",
        json={"question": "Take me to ice.", "map_start": {"lon": -165.18, "lat": 46.32}},
    ).json()
    assert len(calls) == 1
    assert body["route"]["status"] == "infeasible"
