from __future__ import annotations

import json

import numpy as np
import pytest
from fastapi.testclient import TestClient

from olympustrail.api import create_app
from olympustrail.terrain import TerrainGrid


@pytest.fixture(scope="module")
def grid():
    return TerrainGrid.load(create_app.__globals__["ROOT"])


@pytest.fixture(scope="module")
def client(grid):
    return TestClient(create_app(grid))


def cell_where(grid, predicate):
    rows, cols = np.where(predicate)
    assert len(rows), "fixture data should contain a matching grid cell"
    return int(rows[0]), int(cols[0])


def route_payload(start, goal=None, **extra):
    return {"start": {"row": start[0], "col": start[1]},
            "goal": {"row": (goal or start)[0], "col": (goal or start)[1]}, **extra}


def test_health_reports_loaded_grid(client, grid):
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["grid_shape"] == list(grid.shape)
    assert body["mission_parameters_validated"] is False


def test_sites_returns_spaced_candidates_without_shielding_claims(client, grid):
    response = client.get("/sites")
    assert response.status_code == 200
    body = response.json()
    sites = body["sites"]
    assert len(sites) == 5
    assert "shielding" in body["excluded_components"]
    assert all(site.get("shielding") is None for site in sites)
    positions = [site["position"] for site in sites]
    assert len({(p["row"], p["col"]) for p in positions}) == len(positions)
    for index, a in enumerate(positions):
        for b in positions[index+1:]:
            assert grid.distance_m((a["row"], a["col"]), (b["row"], b["col"])) >= 15000


def test_data_status_separates_partial_observations_from_full_scenario(client):
    response = client.get("/data-status")
    assert response.status_code == 200
    body = response.json()
    assert body["observations"]["mode"] == "observations"
    assert body["scenario"]["mode"] == "scenario"
    assert body["coverage"]["observed_temperature"] == pytest.approx(0.05676, abs=0.001)
    assert body["coverage"]["scenario_temperature"] == pytest.approx(1.0)
    assert body["scenario"]["shielding_available"] is False


@pytest.mark.parametrize("position", [
    {"row": 0},
    {"row": 0, "col": 0, "lon": 0, "lat": 0},
    {"row": 0, "col": 0, "extra": "forbidden"},
    {"lon": float("nan"), "lat": 45},
])
def test_invalid_coordinate_pairs_and_fields_return_422(client, position):
    payload = {"start": position, "goal": {"row": 0, "col": 0}}
    # Raw JSON lets the server reject NaN through Pydantic; HTTPX's json= encoder
    # rejects non-finite values client-side before FastAPI can validate them.
    response = client.post("/route", content=json.dumps(payload),
                           headers={"Content-Type": "application/json"})
    assert response.status_code == 422


def test_out_of_grid_coordinate_returns_422(client, grid):
    response = client.post("/route", json=route_payload((grid.shape[0], 0)))
    assert response.status_code == 422


def test_same_cell_route_and_briefing_succeed_with_budget_fields(client, grid):
    slope = grid.layers["slope"]
    start = cell_where(grid, np.isfinite(grid.layers["elevation"]) &
                       np.isfinite(slope) & (slope <= 10))
    payload = route_payload(start, oxygen_hours=3.0, battery_wh=600.0,
                            reserve_fraction=0.25)

    route_response = client.post("/route", json=payload)
    assert route_response.status_code == 200
    route = route_response.json()
    assert route["status"] == "ok"
    assert route["metrics"] is not None
    assert route["budget"]["oxygen_hours"] == 3.0
    assert route["budget"]["battery_wh"] == 600.0

    briefing_response = client.post("/briefing-data", json=payload)
    assert briefing_response.status_code == 200
    briefing = briefing_response.json()
    assert briefing["planning_status"] == "ok"
    assert briefing["departure_authorized"] is False
    assert briefing["budgets"]["reserve_fraction"] == 0.25


def test_observations_route_rejects_start_with_missing_thermal_data(client, grid):
    missing = cell_where(grid, ~np.isfinite(grid.layers["observed_temperature"]))
    response = client.post("/route", json=route_payload(missing, mode="observations"))
    assert response.status_code == 422


def test_observations_mode_rejects_dust_avoidance(client, grid):
    slope = grid.layers["slope"]
    start = cell_where(grid, np.isfinite(grid.layers["observed_temperature"]) &
                       np.isfinite(slope) & (slope <= 10))
    response = client.post("/route", json=route_payload(start, mode="observations", avoid=["dust"]))
    assert response.status_code == 422


def test_terrain_serializes_blocked_costs_as_json_null(client):
    response = client.get("/terrain?stride=1&mode=observations")
    assert response.status_code == 200
    costs = response.json()["cost"]
    assert any(value is None for row in costs for value in row)
    assert all(value is None or np.isfinite(value) for row in costs for value in row)


def test_nearest_ice_route_succeeds_when_start_already_meets_ice_threshold(client, grid):
    ice = grid.layers["ice"]
    slope = grid.layers["slope"]
    start = cell_where(grid, np.isfinite(ice) & (ice >= 0.75) &
                       np.isfinite(slope) & (slope <= 10))
    response = client.post("/route", json={
        "start": {"row": start[0], "col": start[1]},
        "goal_type": "ice",
        "ice_min_consistency": 0.75,
    })
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["route"]["outbound"][0]["row"] == start[0]
    assert body["route"]["outbound"][0]["col"] == start[1]
    assert body["metrics"]["distance_km"] == pytest.approx(0)


def test_signed_and_east_positive_longitudes_resolve_to_the_same_grid_cell(client, grid):
    position = grid.position((5, 5))
    destinations = []
    for lon in (position["lon"], position["lon"] % 360):
        point = dict(lon=lon, lat=position["lat"])
        response = client.post("/route", json=dict(start=point, goal=point))
        assert response.status_code == 200
        destinations.append(response.json()["route"]["destination"])
    assert destinations[0] == destinations[1]
    assert (destinations[0]["row"], destinations[0]["col"]) == (5, 5)
