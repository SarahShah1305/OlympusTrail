from __future__ import annotations

import os
import math
import json
from pathlib import Path
from threading import RLock

import numpy as np
from fastapi import FastAPI, HTTPException, Query
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .models import RouteRequest, SiteRequest
from .routing import plan_route
from .terrain import TerrainGrid

ROOT = Path(__file__).resolve().parents[1]


def create_app(grid: TerrainGrid | None = None) -> FastAPI:
    app = FastAPI(title="OlympusTrail Person 1 API", version="0.1.0",
                  description="Regional Mars hackathon planner. Data classes and assumptions accompany every result.")
    app.state.grid = grid
    load_lock = RLock()

    @app.exception_handler(RequestValidationError)
    async def validation_error(_request, error):
        # Some JSON parsers accept nonstandard NaN/Infinity literals. Preserve a
        # validation response even when the rejected input is not JSON-finite.
        def finite_json(value):
            if isinstance(value, float) and not math.isfinite(value):
                return str(value)
            if isinstance(value, dict):
                return {key: finite_json(item) for key, item in value.items()}
            if isinstance(value, (list, tuple)):
                return [finite_json(item) for item in value]
            return value
        return JSONResponse(status_code=422, content=dict(detail=finite_json(jsonable_encoder(error.errors()))))
    origins = os.environ.get("OLYMPUSTRAIL_ALLOWED_ORIGINS",
                             "http://localhost:3000,http://localhost:5173,http://127.0.0.1:3000,http://127.0.0.1:5173")
    app.add_middleware(CORSMiddleware, allow_origins=[value.strip() for value in origins.split(",")],
                       allow_credentials=False, allow_methods=["GET", "POST"], allow_headers=["Content-Type"])

    def terrain():
        with load_lock:
            if app.state.grid is None:
                try:
                    app.state.grid = TerrainGrid.load(ROOT)
                except (OSError, ValueError, KeyError) as error:
                    raise HTTPException(status_code=503, detail="Terrain data not ready: " + str(error)) from error
            return app.state.grid

    def calculate(request):
        try:
            return plan_route(terrain(), request)
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @app.get("/health")
    def health():
        # Liveness/metadata only: loading every raster is a deep check, not a
        # prerequisite for a health probe or the first HTML request.
        current = app.state.grid
        if current is not None:
            dataset = current.metadata.get("dataset")
            region, shape, spacing = current.metadata.get("region", "Arcadia Planitia"), list(current.shape), current.pixel_m
        else:
            dataset = os.environ.get("OLYMPUSTRAIL_DATASET", "arcadia_500m")
            try:
                metadata_path = ROOT / ("data/person1/arcadia_500m/manifest.json" if dataset == "arcadia_500m" else "data/processed/grid.json")
                metadata = json.loads(metadata_path.read_text())
                region = metadata.get("region", "Arcadia Planitia")
                shape = [metadata["height"], metadata["width"]]
                spacing = abs(metadata["transform"][0]) if "transform" in metadata else metadata["pixel_size_m"]
            except (OSError, ValueError, KeyError) as error:
                raise HTTPException(status_code=503, detail="Terrain metadata not ready: " + str(error)) from error
        return dict(status="ok", region=region, dataset=dataset, grid_shape=shape,
                    grid_spacing_m=spacing,
                    scenario="mcd62_ls90" if dataset == "arcadia_500m" else "mcd62_ls90_noon",
                    mission_parameters_validated=False)

    @app.get("/data-status")
    def data_status():
        current = terrain()
        return dict(
            observations=current.disclosure("observations"), scenario=current.disclosure("scenario"),
            supplemental=current.metadata.get("manifest", current.metadata.get("supplemental", {})),
            coverage={key: float(np.isfinite(values).mean()) for key, values in current.layers.items()},
        )

    @app.get("/sites")
    def get_sites(limit: int = Query(5, ge=1, le=20),
                  min_separation_km: float = Query(15, ge=0, le=500),
                  max_slope_deg: float = Query(10, gt=0, le=45),
                  mode: str = Query("scenario", pattern="^(scenario|observations)$"),
                  edge_buffer_km: float = Query(5, ge=0, le=100),
                  shelter_reach_km: float = Query(5, ge=0, le=50)):
        return terrain().sites(SiteRequest(limit=limit, min_separation_km=min_separation_km,
                                          max_slope_deg=max_slope_deg, mode=mode,
                                          edge_buffer_km=edge_buffer_km, shelter_reach_km=shelter_reach_km))

    @app.get("/shelters")
    def shelters():
        current = terrain()
        return dict(type="FeatureCollection", features=current.metadata.get("shelters", []),
                    kind="unverified_terrain_obstruction_candidate",
                    verified_shelter_count=0, radiation_protection_validated=False,
                    cave_candidate_count=current.metadata.get("manifest", {}).get("caves", {}).get("count_40_58N", 0))

    @app.post("/sites")
    def post_sites(request: SiteRequest):
        return terrain().sites(request)

    @app.post("/route")
    def route(request: RouteRequest):
        return calculate(request)

    @app.post("/briefing-data")
    def briefing_data(request: RouteRequest):
        result = calculate(request)
        return dict(
            title="OlympusTrail EVA demo briefing",
            planning_status=result["status"],
            reason=result["reason"],
            departure_authorized=False,
            purpose="Hackathon planning demonstration; mission assumptions await team validation.",
            route=result["route"], metrics=result["metrics"], budgets=result["budget"],
            turn_back=result["turn_back"], data=result["data"],
            hazards=(dict(slope_deg=result["metrics"]["maximum_slope_deg"],
                          temperature_k=[result["metrics"]["minimum_temperature_k"],
                                         result["metrics"]["maximum_temperature_k"]],
                          dust_optical_depth=result["metrics"]["maximum_dust_optical_depth"],
                          radiation_reference_msv=result["metrics"]["radiation_reference_msv"])
                     if result["metrics"] is not None else None),
            shelter_candidates=(result["turn_back"] or {}).get("candidate_shelters", []),
            abort_points=(result["turn_back"] or {}).get("abort_points", []),
            local_time_h=result["request"]["local_time_h"],
            citations=terrain().metadata.get("supplemental", {}).get("citations", []) + [
                "https://pds-geosciences.wustl.edu/missions/mgs/mola.html",
                "https://pds-geosciences.wustl.edu/mgs/mgs-m-mola-5-megdr-l3-v1/mgsl_300x/meg128/",
                "https://swim.psi.edu/SWIM4MIMProducts.php",
                "https://www-mars.lmd.jussieu.fr/mcd_python/",
                "Guo et al. 2017, JGR Planets 122:329-341, doi:10.1002/2016JE005206",
                "https://themis-data.mars.asu.edu/",
                "https://pds.nasa.gov/",
                "https://www.nasa.gov/news-release/nasa-rover-results-include-first-age-measurement-on-mars-and-help-for-human-exploration/",
                "https://astrogeology.usgs.gov/search/map/mars_global_cave_candidate_catalog_v1_cushing",
            ],
            request=result["request"],
        )

    @app.get("/terrain")
    def terrain_costs(stride: int = Query(20, ge=1, le=100),
                      mode: str = Query("scenario", pattern="^(scenario|observations)$"),
                      local_time_h: int = Query(12)):
        if local_time_h not in (0, 6, 12, 18):
            raise HTTPException(status_code=422, detail="local_time_h must be 0, 6, 12 or 18")
        current = terrain()
        request = RouteRequest(start=dict(row=0, col=0), goal=dict(row=0, col=0), mode=mode,
                               local_time_h=local_time_h)
        costs, _, weights = current.risk_grid(request)
        sample = costs[::stride, ::stride]
        return dict(shape=list(current.shape), stride=stride,
                    rows=list(range(0, current.shape[0], stride)), cols=list(range(0, current.shape[1], stride)),
                    cost=[[float(value) if np.isfinite(value) else None for value in row] for row in sample],
                    crs=current.crs.to_string(), transform=list(current.transform)[:6],
                    risk_weights=weights, data=current.disclosure(mode, local_time_h))

    # Single-function deployments reuse these exact endpoint calculations.
    app.state.calculate = calculate
    app.state.terrain = terrain
    return app


app = create_app()
