from __future__ import annotations

import os
import math
from pathlib import Path

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
        current = terrain()
        return dict(status="ok", region="Arcadia Planitia", grid_shape=list(current.shape),
                    scenario="mcd62_ls90_noon", mission_parameters_validated=False)

    @app.get("/data-status")
    def data_status():
        current = terrain()
        return dict(
            observations=current.disclosure("observations"), scenario=current.disclosure("scenario"),
            supplemental=current.metadata.get("supplemental", {}),
            coverage={key: float(np.isfinite(values).mean()) for key, values in current.layers.items()},
        )

    @app.get("/sites")
    def get_sites(limit: int = Query(5, ge=1, le=20),
                  min_separation_km: float = Query(15, ge=0, le=500),
                  max_slope_deg: float = Query(10, gt=0, le=45),
                  mode: str = Query("scenario", pattern="^(scenario|observations)$")):
        return terrain().sites(SiteRequest(limit=limit, min_separation_km=min_separation_km,
                                          max_slope_deg=max_slope_deg, mode=mode))

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
            shelter_candidates=[],
            citations=terrain().metadata.get("supplemental", {}).get("citations", []) + [
                "https://pds-geosciences.wustl.edu/missions/mgs/mola.html",
                "https://swim.psi.edu/SWIM4MIMProducts.php",
                "https://pds.nasa.gov/",
            ],
            request=result["request"],
        )

    @app.get("/terrain")
    def terrain_costs(stride: int = Query(5, ge=1, le=50),
                      mode: str = Query("scenario", pattern="^(scenario|observations)$")):
        current = terrain()
        request = RouteRequest(start=dict(row=0, col=0), goal=dict(row=0, col=0), mode=mode)
        costs, _, weights = current.risk_grid(request)
        sample = costs[::stride, ::stride]
        return dict(shape=list(current.shape), stride=stride,
                    rows=list(range(0, current.shape[0], stride)), cols=list(range(0, current.shape[1], stride)),
                    cost=[[float(value) if np.isfinite(value) else None for value in row] for row in sample],
                    crs=current.crs.to_string(), transform=list(current.transform)[:6],
                    risk_weights=weights, data=current.disclosure(mode))

    return app


app = create_app()
