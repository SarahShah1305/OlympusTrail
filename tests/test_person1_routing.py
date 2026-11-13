"""Behavioral regression cases for resource feasibility and honest failures."""
import numpy as np
import pytest
from rasterio.crs import CRS
from rasterio.transform import from_origin

from olympustrail.models import RouteRequest
from olympustrail.routing import edge_resources, plan_route
from olympustrail.terrain import TerrainGrid


def grid(shape=(3, 3)):
    zero = np.zeros(shape, dtype=float)
    return TerrainGrid(
        layers=dict(elevation=zero.copy(), slope=zero.copy(), aspect=zero.copy(),
                    ice=np.ones(shape), observed_temperature=np.full(shape, 270.),
                    scenario_temperature=np.full(shape, 270.), dust=zero.copy(),
                    sunlight=np.full(shape, 450.), radiation=np.full(shape, 0.67/24)),
        transform=from_origin(0, shape[0]*1000, 1000, 1000),
        crs=CRS.from_string("+proj=eqc +lat_ts=0 +a=3396190 +b=3396190 +units=m"),
        metadata={},
    )


def request(**kwargs):
    base = dict(start=dict(row=1, col=0), goal=dict(row=1, col=1),
                oxygen_hours=4, battery_wh=1000, reserve_fraction=0)
    return RouteRequest(**(base | kwargs))


def test_round_trip_reserves_both_legs_and_profile_reconciles():
    terrain = grid()
    planned = plan_route(terrain, request())
    assert planned["status"] == "ok"
    route = planned["route"]
    assert route["outbound"] == route["return_path"][::-1]
    assert route["profile"][-1]["position"] == route["profile"][0]["position"]
    assert planned["metrics"]["hours"] == pytest.approx(2/3, rel=1e-5)
    assert planned["metrics"]["oxygen_remaining_hours"] == pytest.approx(route["profile"][-1]["oxygen_remaining_hours"])
    assert planned["metrics"]["battery_remaining_wh"] == pytest.approx(route["profile"][-1]["battery_remaining_wh"])


def test_outbound_feasible_but_return_is_not():
    terrain = grid()
    assert plan_route(terrain, request(oxygen_hours=.6, return_to_start=False))["status"] == "ok"
    failure = plan_route(terrain, request(oxygen_hours=.6, return_to_start=True))
    assert failure["status"] == "infeasible"
    assert failure["route"] is None
    assert failure["turn_back"]["action"] == "do_not_depart_for_requested_goal"


def test_battery_and_reserve_are_independent_constraints():
    terrain = grid()
    assert plan_route(terrain, request(battery_wh=50, return_to_start=False))["status"] == "ok"
    assert plan_route(terrain, request(battery_wh=50, return_to_start=True))["status"] == "infeasible"
    assert plan_route(terrain, request(oxygen_hours=.8, reserve_fraction=.2))["status"] == "infeasible"


def test_diagonal_cannot_cut_between_blocked_cells():
    terrain = grid((2, 2))
    terrain.layers["slope"][0, 1] = 90
    terrain.layers["slope"][1, 0] = 90
    result = plan_route(terrain, request(start=dict(row=0, col=0), goal=dict(row=1, col=1)))
    assert result["status"] == "infeasible"


def test_segment_grade_is_checked_even_when_cell_slope_is_flat():
    terrain = grid((1, 2))
    terrain.layers["elevation"][0, 1] = 1000
    result = plan_route(terrain, request(start=dict(row=0, col=0), goal=dict(row=0, col=1)))
    assert result["status"] == "infeasible"


def test_hazard_summary_includes_segment_grade():
    terrain = grid((1, 2))
    terrain.layers["elevation"][0, 1] = 87
    result = plan_route(terrain, request(start=dict(row=0, col=0), goal=dict(row=0, col=1)))
    assert result["status"] == "ok"
    assert 4 < result["metrics"]["maximum_slope_deg"] < 6


def test_nondominated_energy_arrival_survives_cheaper_exhausted_arrival():
    terrain = grid((3, 7))
    terrain.layers["slope"][2, :] = 90
    terrain.layers["slope"][0, 5:] = 90
    terrain.layers["scenario_temperature"][1, 1:4] = 160
    planned = plan_route(terrain, request(
        goal=dict(row=1, col=6), oxygen_hours=10, battery_wh=730, return_to_start=False,
        weights=dict(slope=1, temperature=0, dust=0, radiation=0),
        parameters=dict(cold_power_w_per_k=10, movement_energy_wh_km=0),
    ))
    assert planned["status"] == "ok"
    assert any(point["row"] == 0 for point in planned["route"]["outbound"])
    assert planned["metrics"]["battery_wh"] <= 730
    assert planned["metrics"]["distance_km"] > 6


def test_edges_are_symmetric_as_required_for_reversed_return():
    terrain = grid()
    terrain.layers["elevation"][1, 1] = 25
    terrain.layers["scenario_temperature"][1, 1] = 190
    terrain.layers["dust"][1, 1] = .7
    req = request()
    env = terrain.environment(req.mode)
    assert edge_resources(terrain, req, env, (1, 0), (1, 1)) == pytest.approx(
        edge_resources(terrain, req, env, (1, 1), (1, 0)))


def test_search_exhaustion_is_not_reported_as_proven_infeasibility():
    terrain = grid((3, 20))
    result = plan_route(terrain, request(goal=dict(row=1, col=19), oxygen_hours=100,
                                       battery_wh=100000, max_search_labels=10))
    assert result["status"] == "search_limit"
    assert result["reason"] == "search_limit"
    assert result["route"] is None


def test_unknown_observed_temperature_is_blocked():
    terrain = grid()
    terrain.layers["observed_temperature"][1, 1] = np.nan
    result = plan_route(terrain, request(mode="observations"))
    assert result["status"] == "infeasible"
    assert result["reason"] == "no_eligible_goal"


def test_outside_position_is_not_clamped_to_the_grid():
    with pytest.raises(ValueError, match="outside"):
        plan_route(grid(), request(goal=dict(row=999, col=1)))
