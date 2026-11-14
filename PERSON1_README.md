# Person 1 terrain and route API

This note covers the Person 1 API and terrain engine. The existing project `README.md` is unchanged.

The API loads the **500 m Arcadia grid** (40–58°N, 173–157°W) in `data/person1/arcadia_500m/` by default. It fills the gaps in the 3 km handoff: finer terrain, the northern ice extension, time-of-day temperatures, a uniform off-region Gale RAD reference dose, and a geometric sky-obstruction layer for display. The radiation reference is not adjusted for local pressure or horizon geometry and does not validate radiation protection. See that folder's `README.md` for sources and caveats. Person 2's `data/processed/` files are unchanged; set `OLYMPUSTRAIL_DATASET=regional_3km` before starting the server to use them instead.

## Setup and run on Windows

The project `.venv` is already prepared on this PC. From the repository root in PowerShell, install or update the required packages with:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-person1-dev.txt
```

The development requirements include the repository requirements, FastAPI, Uvicorn, HTTPX, and pytest. Start the local API with:

```powershell
.\.venv\Scripts\python.exe -m uvicorn olympustrail.api:app --host 127.0.0.1 --port 8000
```

Open the interactive API reference at [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs). Run tests without pytest's cache plugin using:

```powershell
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider
```

## Endpoints

- `GET /health` returns service status, region, grid dimensions, scenario ID, and whether mission parameters have been validated.
- `GET /data-status` reports coverage per input layer, the scenario metadata, the partial observation coverage, and data caveats.
- `GET /sites` ranks candidate sites. Query parameters include `limit`, `min_separation_km`, `max_slope_deg`, `mode`, `edge_buffer_km` (default 5, keeps sites off the map edge) and `shelter_reach_km` (retained for API compatibility; unused in scoring). `POST /sites` accepts those options as JSON instead. Each site has its row/column and longitude/latitude, score components (ice, flatness, and sunlight where available), ice consistency, slope, and separate `shielding` and `nearest_shelter` compatibility fields. `shielding` is always `null` and excluded from scoring weights; geometric sky obstruction is display-only and is not evidence of radiation protection or a usable shelter.
- `POST /route` computes a route under slope, temperature, time, oxygen, battery, and reserve constraints. `local_time_h` (0, 6, 12 or 18; default 12) selects the climate scenario. Its response includes the normalized request, data notes, search counts, route status/reason, route and return path, per-step profile, GeoJSON line, resource metrics, and turn-back instructions. For round trips, `turn_back.abort_points` lists checkpoints at 25/50/75/100 % of the outbound time with the oxygen and battery left if the crew turned back there, and `turn_back.candidate_shelters` lists unverified terrain-obstruction candidates within 3 km of the route. An infeasible response includes the last reachable point and a candidate return path; it does not imply the requested goal was reached.
- `POST /briefing-data` wraps the route result with a briefing title, hazards, abort points, unverified terrain-obstruction candidates, local time, citations, and a fixed `departure_authorized: false` field. It is a planning demo output, not an authorization.
- `GET /shelters` is a compatibility endpoint that returns geometric terrain-obstruction candidates as GeoJSON points. Each is labeled `kind: unverified_terrain_obstruction_candidate`, `verified_shelter: false`, and `radiation_protection_validated: false`; sky obstruction alone does not establish shelter or radiation protection.
- `GET /terrain` returns a downsampled risk-cost surface. `stride` controls the sampling interval (1–100, default 20); `mode` selects `scenario` or `observations`; `local_time_h` selects the scenario time. The response contains original grid `shape`, sampled `rows` and `cols`, a nested `cost` matrix (`null` means blocked or unavailable), CRS, affine transform, risk weights, and data notes. Use a larger stride for smaller responses.

Positions accept either integer `row`/`col` grid indices or a `lon`/`lat` pair, but not both. Longitudes may be signed (for example, `-157`) or east-positive in the 0–360 convention (for example, `203`); latitude is in degrees. API distance fields are kilometres, raster spacing and transform are metres, oxygen/time budgets are Earth hours, battery capacity and energy are Wh, temperatures are K, slope is degrees, dust optical depth is dimensionless, and radiation reference dose is mSv.

## Runnable PowerShell route demo

For `goal_type: "ice"`, if the start already meets the ice threshold and `min_goal_distance_km` is omitted, the planner requires a goal at least 2 km away. An explicit distance, including 0, overrides this default; coordinate goals are unaffected.

With the server running, this discovers the highest-ranked scenario site at runtime and requests an ice goal at least 3 km away at dawn. The selected site and route results depend on the current data and mission parameters; always inspect `status`, `reason`, and `turn_back`.

```powershell
$base = 'http://127.0.0.1:8000'
$sites = Invoke-RestMethod "$base/sites?limit=1&min_separation_km=0&mode=scenario"
$start = $sites.sites[0].position

$body = @{
    start = @{ row = $start.row; col = $start.col }
    goal_type = 'ice'
    min_goal_distance_km = 3
    local_time_h = 6
    oxygen_hours = 4
    battery_wh = 1000
    reserve_fraction = 0.2
    return_to_start = $true
    mode = 'scenario'
} | ConvertTo-Json -Depth 8

$route = Invoke-RestMethod -Method Post -Uri "$base/route" `
    -ContentType 'application/json' -Body $body
$route | ConvertTo-Json -Depth 12
```

An ice target at least 3 km from the start can be unreachable or exceed the round-trip resource budget. Check `status`, `reason`, and `turn_back`; do not treat an infeasible request as a successful mission.

## Modes, assumptions, and limits

The API exposes two distinct data modes:

- `scenario` uses full-grid Mars Climate Database v6.2 samples for northern summer (`Ls=90°`) at 00, 06, 12 or 18 h local time, plus dust and sunlight. Radiation is a uniform Gale RAD off-region reference of 0.67 mSv per 24 Earth hours (0.0279167 mSv/h), linked to the [NASA Gale RAD report](https://www.nasa.gov/news-release/nasa-rover-results-include-first-age-measurement-on-mars-and-help-for-human-exploration/). It is not an Arcadia measurement: there is no local pressure or horizon adjustment, no absorbed-Gy-to-Sv conversion, and no solar-particle-event model. Sky obstruction is display-only; radiation protection is not validated. This mode supplies spatially complete scenario rasters; it does not mean regional measurements are complete.
- `observations` uses THEMIS brightness-temperature observations from the original 3 km atlas plus 14 additional scenes. They are regridded to 500 m by nearest neighbour and fill only cells still missing a value. Coverage is 24.00% of the expanded grid; remaining cells stay unknown. The observations come from different dates and are not a coherent temperature field. Cells without required temperature are blocked for routing. Dust and radiation are unavailable in this mode, and their risk terms are excluded. Do not fill observation gaps with scenario values or describe the partial historical layer as a complete measurement.

The scenario is a static model sample, not a forecast or changing weather along the trip. Slope, dust, and sunlight are regional-grid inputs and do not confirm local traversability, dust trafficability, or annual solar availability. The `sky_blocked_fraction` layer is geometric sky obstruction within 6 km, retained for display and unverified terrain-obstruction candidates only. The full USGS catalog was filtered across the expanded region: zero listed candidates among 1,062 records. This does not rule out undiscovered caves. Mission walking, energy, temperature, slope, and dust limits in `models.py` are illustrative defaults pending Person 5 validation.

Routes use static symmetric edge costs. When `return_to_start` is true, the planner reserves the outbound route's resource cost again and models return as reversing that same path. It does not discover a separate return route or a shelter destination. The multi-label search tracks nondominated risk cost, time, and energy labels; `max_search_labels` limits its work and can produce a `search_limit` result.

For integration, send signed or 0–360 east-positive longitude in degrees with latitude in degrees, or grid row/column indices. Preserve the API's units: time in Earth hours and energy in Wh. Treat the returned GeoJSON as a display geometry for the regional grid, not a verified vehicle trajectory.
