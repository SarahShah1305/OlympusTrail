# Person 1 terrain and route API

This note covers the Person 1 API and terrain engine. The existing project `README.md` is unchanged.

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
- `GET /sites` ranks candidate sites. Query parameters include `limit`, `min_separation_km`, `max_slope_deg`, and `mode`. `POST /sites` accepts those options as JSON instead. The response includes each site's row/column and longitude/latitude, score components, ice consistency, slope, and `shielding: null`; it also lists excluded components and data notes.
- `POST /route` computes a route under slope, temperature, time, oxygen, battery, and reserve constraints. Its response includes the normalized request, data notes, search counts, route status/reason, route and return path, per-step profile, GeoJSON line, resource metrics, and turn-back instructions. An infeasible response includes the last reachable point and a candidate return path; it does not imply the requested goal was reached.
- `POST /briefing-data` wraps the route result with a briefing title, hazards, cave candidates, citations, and a fixed `departure_authorized: false` field. It is a planning demo output, not an authorization.
- `GET /terrain` returns a downsampled risk-cost surface. `stride` controls the sampling interval (1–50); `mode` selects `scenario` or `observations`. The response contains original grid `shape`, sampled `rows` and `cols`, a nested `cost` matrix (`null` means blocked or unavailable), CRS, affine transform, risk weights, and data notes. Use a larger stride for smaller responses.

Positions accept either integer `row`/`col` grid indices or a `lon`/`lat` pair, but not both. Longitudes may be signed (for example, `-157`) or east-positive in the 0–360 convention (for example, `203`); latitude is in degrees. API distance fields are kilometres, raster spacing and transform are metres, oxygen/time budgets are Earth hours, battery capacity and energy are Wh, temperatures are K, slope is degrees, dust optical depth is dimensionless, and radiation reference dose is mSv.

## Runnable PowerShell route demo

With the server running, this gets the highest-ranked scenario site and requests an ice goal at least 3 km away. The current top site is cell `(7, 219)`. This request has been checked against the current data and returned `status: ok`, with a 6 km round trip, about 2.19 Earth hours, and about 279 Wh used. Results can change with the data or mission parameters; always inspect `status`, `reason`, and `turn_back`.

```powershell
$base = 'http://127.0.0.1:8000'
$sites = Invoke-RestMethod "$base/sites?limit=1&min_separation_km=0&mode=scenario"
$start = $sites.sites[0].position

$body = @{
    start = @{ row = $start.row; col = $start.col }
    goal_type = 'ice'
    min_goal_distance_km = 3
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

- `scenario` uses the full-grid Mars Climate Database v6.2 sample for northern summer (`Ls=90°`), local noon, plus dust and sunlight scenarios. Radiation is a uniform Gale reference value, not an Arcadia measurement. This mode supplies spatially complete scenario rasters; it does not mean regional measurements are complete.
- `observations` uses the existing THEMIS brightness-temperature observations. Only about 5.7% of grid cells have a thermal observation; cells without required temperature are blocked for routing. Dust and radiation are unavailable in this mode, and their risk terms are excluded. Do not fill the gaps with scenario values or describe the partial observation layer as a complete measurement.

The scenario is a static model sample, not a forecast or changing weather along the trip. Slope, dust, and sunlight are regional-grid inputs and do not confirm local traversability, dust trafficability, or annual solar availability. There are zero cave candidates in the project region and no shielding layer, so the API reports no known shelters and does not infer shelter or shielding protection. Mission walking, energy, temperature, slope, and dust limits in `models.py` are illustrative defaults pending Person 5 validation.

Routes use static symmetric edge costs. When `return_to_start` is true, the planner reserves the outbound route's resource cost again and models return as reversing that same path. It does not discover a separate return route or a shelter destination. The multi-label search tracks nondominated risk cost, time, and energy labels; `max_search_labels` limits its work and can produce a `search_limit` result.

For integration, send signed or 0–360 east-positive longitude in degrees with latitude in degrees, or grid row/column indices. Preserve the API's units: time in Earth hours and energy in Wh. Treat the returned GeoJSON as a display geometry for the regional grid, not a verified vehicle trajectory.
