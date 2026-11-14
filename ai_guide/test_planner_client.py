"""Offline tests for the planner request adapter and mock responses."""

import asyncio
from types import SimpleNamespace

import httpx
import pytest

from ai_guide import planner_client
from ai_guide.planner_client import (
    build_route_request,
    call_planner,
    get_sites,
    to_ui_path,
)


def test_request_contains_only_allowed_fields():
    """Planner payload excludes parser and unknown fields."""
    parsed = SimpleNamespace(
        start=None,
        intent="route",
        goal_type="shelter",
        oxygen_hours=None,
        battery_wh=None,
        battery_pct=None,
        local_time_h=None,
        avoid=["steep", "radiation", "dust"],
        unsupported=["avoid_radiation"],
        confidence=0.9,
        question="ignore this",
        extra_backend_field="ignore this too",
    )
    request = build_route_request(parsed)
    assert set(request) == {
        "start", "goal_type", "oxygen_hours", "battery_wh", "reserve_fraction",
        "return_to_start", "local_time_h", "mode", "min_goal_distance_km", "avoid",
    }
    assert request["goal_type"] == "ice"
    assert request["avoid"] == ["steep", "dust"]


def test_battery_percentage_converts_to_wh():
    """A parsed percentage becomes a 1000 Wh capacity fraction."""
    request = build_route_request({"battery_pct": 40})
    assert request["battery_wh"] == 400


def test_map_start_becomes_lon_lat_pair():
    """Map coordinates are sent in the planner's lon/lat object format."""
    request = build_route_request({}, map_start={"lat": 52.5, "lon": -157.2})
    assert request["start"] == {"lon": -157.2, "lat": 52.5}
    assert "row" not in request["start"]
    assert "col" not in request["start"]


def test_default_start_uses_configured_grid_position(monkeypatch):
    """The default start is row 643, column 1226."""
    monkeypatch.delenv("DEFAULT_START_ROW", raising=False)
    monkeypatch.delenv("DEFAULT_START_COL", raising=False)
    request = build_route_request({})
    assert request["start"] == {"row": 643, "col": 1226}


def test_ui_path_starts_at_first_outbound_point():
    """UI path uses [lat, lon] and appends the return without duplication."""
    result = asyncio.run(call_planner({"oxygen_hours": 4}))
    path = to_ui_path(result)
    first = result["route"]["outbound"][0]
    assert path[0] == [first["lat"], first["lon"]]
    assert path == [
        [point["lat"], point["lon"]]
        for point in result["route"]["outbound"] + result["route"]["return_path"][1:]
    ]


def test_infeasible_result_has_empty_ui_path():
    """Under one hour selects the infeasible mock with no display path."""
    result = asyncio.run(call_planner({"oxygen_hours": 0.5}))
    assert result["status"] == "infeasible"
    assert result["_mock"] is True
    assert to_ui_path(result) == []


def test_unknown_fields_never_appear_in_request():
    """Explicitly reject all AI-only fields from the outgoing payload."""
    request = build_route_request(
        {
            "question": "find a route",
            "intent": "route",
            "unsupported": ["avoid_radiation"],
            "battery_pct": 55,
            "confidence": 0.7,
            "other": "unknown",
        }
    )
    for field in ("question", "intent", "unsupported", "battery_pct", "confidence", "other"):
        assert field not in request
    assert request["battery_wh"] == 550


def test_mock_mode_still_returns_mock_route(monkeypatch):
    """Explicit mock mode continues to return the sample route."""
    monkeypatch.setenv("USE_MOCK", "1")
    result = asyncio.run(call_planner({"oxygen_hours": 4}))
    assert result["status"] == "ok"
    assert result["_mock"] is True


def test_real_route_connection_error_raises_planner_error(monkeypatch):
    """Real mode reports a connection failure instead of returning mock data."""
    monkeypatch.setenv("USE_MOCK", "0")

    async def fail_connect(self, *args, **kwargs):
        raise httpx.ConnectError("offline")

    monkeypatch.setattr(httpx.AsyncClient, "post", fail_connect)
    with pytest.raises(planner_client.PlannerError) as error:
        asyncio.run(call_planner({"oxygen_hours": 4}))
    assert str(error.value) == "I could not reach the route planner. Please check that it is running."


def test_real_sites_connection_error_raises_planner_error(monkeypatch):
    """Real sites mode reports connection errors without a mock site list."""
    monkeypatch.setenv("USE_MOCK", "0")

    async def fail_connect(self, *args, **kwargs):
        raise httpx.ConnectError("offline")

    monkeypatch.setattr(httpx.AsyncClient, "get", fail_connect)
    with pytest.raises(planner_client.PlannerError) as error:
        asyncio.run(get_sites())
    assert str(error.value) == "I could not reach the route planner. Please check that it is running."


@pytest.fixture(autouse=True)
def use_mock_planner(monkeypatch):
    """Keep all tests offline by forcing the local mock responses."""
    monkeypatch.setenv("USE_MOCK", "1")
