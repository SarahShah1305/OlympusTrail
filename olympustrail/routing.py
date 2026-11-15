"""Resource-constrained A* on an undirected, static terrain cost grid.

Each cell retains nondominated (risk cost, time, battery) labels, so a cheap
but slow/energy-heavy arrival cannot erase a feasible alternative. Round trips
reserve the cost of reversing the outbound route, which is valid because every
edge uses symmetric slope, environment and resource calculations.
"""
from __future__ import annotations

import heapq
import math
from dataclasses import dataclass

import numpy as np

from .models import RouteRequest
from .terrain import TerrainGrid


@dataclass(frozen=True)
class Label:
    cell: tuple[int, int]
    cost: float
    hours: float
    energy: float
    distance: float
    parent: int | None


def dominates(a: Label, b: Label):
    return a.cost <= b.cost + 1e-9 and a.hours <= b.hours + 1e-10 and a.energy <= b.energy + 1e-8


def neighbors(grid, cell, valid):
    r, c = cell
    for dr, dc in ((-1, 0), (0, 1), (1, 0), (0, -1), (-1, -1), (-1, 1), (1, 1), (1, -1)):
        rr, cc = r+dr, c+dc
        if not (0 <= rr < grid.shape[0] and 0 <= cc < grid.shape[1] and valid[rr, cc]):
            continue
        # Do not squeeze diagonally between blocked orthogonal neighbors.
        if dr and dc and not (valid[r+dr, c] and valid[r, c+dc]):
            continue
        yield (rr, cc)


def edge_resources(grid, request, environment, a, b):
    params = request.parameters
    distance = grid.distance_m(a, b)
    if distance <= 0:
        raise ValueError("Grid contains coincident neighboring cell centers")
    grade = math.degrees(math.atan(abs(float(grid.layers["elevation"][b])-float(grid.layers["elevation"][a]))/distance))
    slope = max(grade, (float(grid.layers["slope"][a])+float(grid.layers["slope"][b]))/2)
    slope_limit = min(10.0, params.max_slope_deg) if "steep" in request.avoid else params.max_slope_deg
    if slope > slope_limit:
        return None
    dust = 0.0 if environment["dust"] is None else (float(environment["dust"][a])+float(environment["dust"][b]))/2
    speed = params.walking_speed_kmh / (1+slope/10.0+0.3*dust)
    hours = distance/1000.0/speed
    temperature = (float(environment["temperature"][a])+float(environment["temperature"][b]))/2
    power = params.base_power_w + params.cold_power_w_per_k*max(0, params.cold_reference_k-temperature)
    energy = hours*power + distance/1000.0*params.movement_energy_wh_km
    return distance, hours, energy


def reconstruct(labels, label_id):
    path = []
    while label_id is not None:
        label = labels[label_id]
        path.append(label.cell)
        label_id = label.parent
    return path[::-1]


def route_profile(grid, request, environment, path):
    hours = energy = distance = radiation = 0.0
    result = []
    previous = None
    for cell in path:
        if previous is not None:
            metrics = edge_resources(grid, request, environment, previous, cell)
            if metrics is None:
                raise RuntimeError("Reconstructed route contains an invalid segment")
            dd, dt, de = metrics
            distance += dd
            hours += dt
            energy += de
            if environment["radiation"] is not None:
                rate = (float(environment["radiation"][previous])+float(environment["radiation"][cell]))/2
                radiation += dt*rate
        result.append(dict(position=grid.position(cell), elapsed_hours=hours, distance_km=distance/1000,
                           oxygen_remaining_hours=request.oxygen_hours-hours,
                           battery_remaining_wh=request.battery_wh-energy))
        previous = cell
    return result, dict(hours=hours, battery_wh=energy, distance_km=distance/1000,
                        radiation_reference_msv=radiation if environment["radiation"] is not None else None)


def checkpoints(profile, outbound_len, request, fractions=(0.25, 0.5, 0.75, 1.0)):
    """Abort checkpoints on the outbound leg.

    The return reverses the outbound path, so walking back from outbound
    step i costs exactly the time/energy already spent to reach it. The
    margin is what would be left at the start if the crew turned back there.
    """
    outbound = profile[:outbound_len]
    if len(outbound) < 2:
        return []
    total = outbound[-1]["elapsed_hours"]
    picked, seen = [], set()
    for fraction in fractions:
        target = total * fraction
        index = next(i for i, p in enumerate(outbound) if p["elapsed_hours"] >= target - 1e-9)
        if index in seen or index == 0:
            continue
        seen.add(index)
        p = outbound[index]
        hours_back = p["elapsed_hours"]
        energy_used = request.battery_wh - p["battery_remaining_wh"]
        picked.append(dict(
            fraction_of_outbound=fraction, position=p["position"], elapsed_hours=p["elapsed_hours"],
            distance_km=p["distance_km"], hours_to_return=hours_back,
            oxygen_left_if_abort_hours=request.oxygen_hours - 2*hours_back,
            battery_left_if_abort_wh=request.battery_wh - 2*energy_used,
        ))
    return picked


def shelters_near(grid, path, max_km=3.0, limit=3):
    """Terrain shelter candidates within max_km of any route cell."""
    found = []
    for feature in grid.metadata.get("shelters", []):
        props = feature["properties"]
        cell = (props["row"], props["col"])
        nearest = min(path, key=lambda c: (c[0]-cell[0])**2 + (c[1]-cell[1])**2)
        d = grid.distance_m(nearest, cell) / 1000
        if d <= max_km:
            found.append(dict(position=grid.position(cell), distance_from_route_km=d,
                              nearest_route_point=grid.position(nearest),
                              sky_blocked_fraction=props["sky_blocked_fraction"], kind=props["kind"],
                              verified_shelter=False, radiation_protection_validated=False,
                              note="Terrain wall that hides part of the sky; not a cave or verified shelter."))
    return sorted(found, key=lambda f: f["distance_from_route_km"])[:limit]


def plan_route(grid: TerrainGrid, request: RouteRequest):
    costs, environment, used_weights = grid.risk_grid(request)
    valid = np.isfinite(costs)
    start = grid.cell(request.start)
    if not valid[start]:
        raise ValueError("Start is blocked by missing data, slope limit, or an avoid constraint")
    if (request.goal_type == "ice" and
            "min_goal_distance_km" not in request.model_fields_set and
            np.isfinite(grid.layers["ice"][start]) and
            grid.layers["ice"][start] >= request.ice_min_consistency):
        # An omitted distance should produce an excursion from an icy base.
        # Preserve explicit distances, including an intentional zero.
        request = request.model_copy(update={"min_goal_distance_km": 2.0})
    goal = grid.cell(request.goal) if request.goal is not None else None
    if goal is not None:
        goals = np.zeros(grid.shape, dtype=bool)
        goals[goal] = True
    else:
        goals = np.isfinite(grid.layers["ice"]) & (grid.layers["ice"] >= request.ice_min_consistency)
        if request.min_goal_distance_km > 0:
            # Use the same spherical distances as budget calculations.
            goals &= grid.distances_from(start) >= request.min_goal_distance_km*1000
    goals &= valid
    factor = 2 if request.return_to_start else 1
    max_hours = request.oxygen_hours*(1-request.reserve_fraction)/factor
    max_energy = request.battery_wh*(1-request.reserve_fraction)/factor
    common = dict(
        request=request.model_dump(), data=grid.disclosure(request.mode, request.local_time_h), risk_weights=used_weights,
        budget=dict(oxygen_hours=request.oxygen_hours, battery_wh=request.battery_wh,
                    reserve_fraction=request.reserve_fraction, return_to_start=request.return_to_start),
        algorithm="multi-label resource-constrained A*" if goal is not None else
                  "multi-label resource-constrained Dijkstra",
        route_model="symmetric static edges; round-trip return reverses outbound path",
    )

    def estimate(cell):
        return grid.distance_m(cell, goal) if goal is not None else 0.0

    labels = [Label(start, 0, 0, 0, 0, None)]
    fronts = {start: [0]}
    active = {0}
    heap = [(estimate(start), 0)]
    closest = 0
    expanded = 0
    result = None
    limited = False
    if not np.any(goals):
        heap = []
    while heap:
        _, index = heapq.heappop(heap)
        if index not in active:
            continue
        label = labels[index]
        expanded += 1
        if goals[label.cell]:
            result = index
            break
        if estimate(label.cell) < estimate(labels[closest].cell):
            closest = index
        for cell in neighbors(grid, label.cell, valid):
            resources = edge_resources(grid, request, environment, label.cell, cell)
            if resources is None:
                continue
            dd, dt, de = resources
            hours, energy = label.hours+dt, label.energy+de
            if hours > max_hours+1e-10 or energy > max_energy+1e-8:
                continue
            new = Label(cell, label.cost + dd*(costs[label.cell]+costs[cell])/2,
                        hours, energy, label.distance+dd, index)
            front = fronts.get(cell, [])
            if any(dominates(labels[old], new) for old in front):
                continue
            survivors = []
            for old in front:
                if dominates(new, labels[old]):
                    active.discard(old)
                else:
                    survivors.append(old)
            if len(labels) >= request.max_search_labels:
                limited = True
                break
            new_index = len(labels)
            labels.append(new)
            survivors.append(new_index)
            fronts[cell] = survivors
            active.add(new_index)
            heapq.heappush(heap, (new.cost+estimate(cell), new_index))
        if limited:
            break
    common["search"] = dict(expanded_labels=expanded, created_labels=len(labels))
    if result is None:
        outbound = reconstruct(labels, closest)
        return_cells = outbound[::-1]
        _, metrics = route_profile(grid, request, environment, outbound+return_cells[1:])
        reason = "search_limit" if limited else ("no_eligible_goal" if not np.any(goals) else "no_feasible_route")
        return dict(**common, status="search_limit" if limited else "infeasible", reason=reason,
                    route=None, metrics=None,
                    turn_back=dict(action="do_not_depart_for_requested_goal",
                                   explanation="The requested goal was not reached within the search and configured constraints.",
                                   last_reachable=grid.position(outbound[-1]),
                                   candidate_outbound=[grid.position(cell) for cell in outbound],
                                   return_path=[grid.position(cell) for cell in return_cells],
                                   candidate_round_trip=metrics,
                                   return_is_reserved=request.return_to_start))
    outbound = reconstruct(labels, result)
    return_cells = outbound[::-1] if request.return_to_start else []
    mission_path = outbound + return_cells[1:] if return_cells else outbound
    profile, metrics = route_profile(grid, request, environment, mission_path)
    coordinates = [[item["position"]["lon"], item["position"]["lat"]] for item in profile]
    if len(coordinates) == 1:
        coordinates = coordinates*2
    destination = outbound[-1]
    temperatures = [float(environment["temperature"][cell]) for cell in mission_path]
    dust = [float(environment["dust"][cell]) for cell in mission_path] if environment["dust"] is not None else None
    traversed_slopes = [float(grid.layers["slope"][cell]) for cell in mission_path]
    traversed_slopes += [math.degrees(math.atan(abs(float(grid.layers["elevation"][b])-float(grid.layers["elevation"][a])) /
                                               grid.distance_m(a, b)))
                         for a, b in zip(mission_path, mission_path[1:])]
    abort_points = checkpoints(profile, len(outbound), request) if request.return_to_start else []
    shelters = shelters_near(grid, mission_path)
    return dict(**common, status="ok", reason=None,
                route=dict(outbound=[grid.position(cell) for cell in outbound],
                           return_path=[grid.position(cell) for cell in return_cells],
                           destination=grid.position(destination), profile=profile,
                           geojson=dict(type="Feature", properties=dict(mode=request.mode),
                                        geometry=dict(type="LineString", coordinates=coordinates))),
                metrics=dict(**metrics, weighted_cost=labels[result].cost*factor,
                             oxygen_remaining_hours=request.oxygen_hours-metrics["hours"],
                             battery_remaining_wh=request.battery_wh-metrics["battery_wh"],
                             maximum_slope_deg=max(traversed_slopes),
                             minimum_temperature_k=min(temperatures), maximum_temperature_k=max(temperatures),
                             maximum_dust_optical_depth=max(dust) if dust is not None else None),
                turn_back=dict(action="reverse_outbound_path" if request.return_to_start else "return_not_budgeted",
                               return_is_reserved=request.return_to_start,
                               turnaround=grid.position(destination),
                               candidate_shelters=shelters,
                               abort_points=abort_points,
                               oxygen_reserve_hours=request.oxygen_hours*request.reserve_fraction,
                               battery_reserve_wh=request.battery_wh*request.reserve_fraction))
