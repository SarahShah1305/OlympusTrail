from __future__ import annotations

import json
import math
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path

import numpy as np
import rasterio
from rasterio.crs import CRS
from rasterio.transform import rowcol, xy
from rasterio.warp import transform as project

from .models import Position, RouteRequest, SiteRequest

MARS_GEOGRAPHIC = CRS.from_string("+proj=longlat +a=3396190 +b=3396190 +no_defs")


@dataclass
class TerrainGrid:
    layers: dict[str, np.ndarray]
    transform: object
    crs: CRS
    metadata: dict

    @classmethod
    def load(cls, root: Path):
        processed = root / "data/processed"
        supplemental = root / "data/person1"
        manifest = json.loads((supplemental / "manifest.json").read_text())
        grid_metadata = json.loads((processed / "grid.json").read_text())
        paths = {
            "elevation": processed / "elevation_m.tif",
            "slope": processed / "slope_deg.tif",
            "aspect": processed / "aspect_deg.tif",
            "ice": processed / "ice_consistency.tif",
            "observed_temperature": processed / "thermal_brightness_temperature_k.tif",
            "scenario_temperature": supplemental / "temperature_model_k.tif",
            "dust": supplemental / "dust_model_optical_depth.tif",
            "sunlight": supplemental / "sunlight_model_w_m2.tif",
            "radiation": supplemental / "radiation_reference_msv_h.tif",
        }
        arrays = {}
        geometry = None
        for name, path in paths.items():
            with rasterio.open(path) as src:
                signature = (src.shape, src.transform, src.crs)
                if geometry is None:
                    geometry = signature
                if signature != geometry or src.count != 1:
                    raise ValueError(f"Misaligned or multiband layer: {path}")
                arrays[name] = src.read(1, masked=True).filled(np.nan).astype("float64")
        shape, affine, crs = geometry
        if shape != (grid_metadata["height"], grid_metadata["width"]):
            raise ValueError("Raster dimensions disagree with original grid.json")
        return cls(arrays, affine, crs, dict(grid=grid_metadata, supplemental=manifest))

    @property
    def shape(self):
        return self.layers["elevation"].shape

    @property
    def pixel_m(self):
        return abs(self.transform.a)

    @cached_property
    def lonlat(self):
        rows, cols = np.indices(self.shape)
        xs, ys = xy(self.transform, rows.ravel(), cols.ravel())
        lon, lat = project(self.crs, MARS_GEOGRAPHIC, xs, ys)
        return np.deg2rad(np.array(lon).reshape(self.shape)), np.deg2rad(np.array(lat).reshape(self.shape))

    def cell(self, position: Position) -> tuple[int, int]:
        if position.row is not None:
            cell = (position.row, position.col)
        else:
            lon = (position.lon + 180) % 360 - 180
            xs, ys = project(MARS_GEOGRAPHIC, self.crs, [lon], [position.lat])
            cell = tuple(int(v) for v in rowcol(self.transform, xs[0], ys[0]))
        if not (0 <= cell[0] < self.shape[0] and 0 <= cell[1] < self.shape[1]):
            raise ValueError("Position is outside the analysis grid")
        return cell

    def position(self, cell: tuple[int, int]) -> dict:
        x, y = xy(self.transform, *cell)
        lon, lat = project(self.crs, MARS_GEOGRAPHIC, [x], [y])
        return dict(row=int(cell[0]), col=int(cell[1]), lon=float(lon[0]), lat=float(lat[0]))

    def environment(self, mode: str):
        return dict(
            temperature=self.layers["scenario_temperature" if mode == "scenario" else "observed_temperature"],
            dust=self.layers["dust"] if mode == "scenario" else None,
            radiation=self.layers["radiation"] if mode == "scenario" else None,
            sunlight=self.layers["sunlight"] if mode == "scenario" else None,
        )

    def disclosure(self, mode: str):
        return dict(
            mode=mode, grid_spacing_m=self.pixel_m,
            scenario=self.metadata.get("supplemental", {}).get("scenario") if mode == "scenario" else None,
            thermal_observation_coverage=float(np.isfinite(self.layers["observed_temperature"]).mean()),
            radiation_source="uniform Gale reference assumption" if mode == "scenario" else "unavailable",
            shielding_available=False, shelter_candidate_count=0,
            assumptions=[
                "Regional grid, not astronaut-scale obstacle or shelter verification.",
                "Static climate scenario; no changing weather along the trip." if mode == "scenario" else
                "Partial historical thermal observations; cells without temperature are blocked.",
                "Arcadia radiation and shielding measurements are unavailable.",
                "Walking and battery parameters are illustrative, pending Person 5 validation.",
            ],
            excluded_risk_components=[] if mode == "scenario" else ["dust", "radiation"],
        )

    def risk_grid(self, request: RouteRequest):
        env = self.environment(request.mode)
        params = request.parameters
        slope = self.layers["slope"]
        valid = np.isfinite(self.layers["elevation"]) & np.isfinite(slope) & np.isfinite(env["temperature"])
        valid &= (slope >= 0) & (slope <= params.max_slope_deg)
        if request.mode == "scenario":
            valid &= np.isfinite(env["dust"]) & np.isfinite(env["radiation"])
        if "steep" in request.avoid:
            valid &= slope <= min(10.0, params.max_slope_deg)
        if "dust" in request.avoid:
            if env["dust"] is None:
                raise ValueError("Dust avoidance cannot be evaluated in observations mode")
            valid &= env["dust"] <= params.max_dust_optical_depth
        if "cold" in request.avoid:
            valid &= env["temperature"] >= params.cold_reference_k
        if "unknown_thermal" in request.avoid:
            valid &= np.isfinite(self.layers["observed_temperature"])
        components = dict(
            slope=np.clip(slope / params.max_slope_deg, 0, 1),
            temperature=np.clip((params.cold_reference_k - env["temperature"]) / 70.0, 0, 1),
        )
        if env["dust"] is not None:
            components["dust"] = np.clip(env["dust"], 0, 1)
        if env["radiation"] is not None:
            components["radiation"] = np.clip(env["radiation"] / 0.03, 0, 1)
        weights = request.weights.model_dump()
        total = sum(weights[key] for key in components)
        if total <= 0:
            raise ValueError("All selected risk weights refer to unavailable layers")
        normalized = {key: weights[key] / total for key in components}
        risk = sum(normalized[key] * values for key, values in components.items())
        return np.where(valid, 1.0 + 4.0 * risk, np.inf), env, normalized

    def sites(self, request: SiteRequest):
        env = self.environment(request.mode)
        slope, ice = self.layers["slope"], self.layers["ice"]
        valid = (np.isfinite(ice) & np.isfinite(slope) & np.isfinite(self.layers["elevation"]) &
                 np.isfinite(env["temperature"]) & (slope >= 0) & (slope <= request.max_slope_deg))
        components = dict(ice=np.clip(ice, 0, 1), flatness=1-np.clip(slope/request.max_slope_deg, 0, 1))
        raw_weights = dict(ice=0.45, flatness=0.30, sunlight=0.15, shielding=0.10)
        if env["sunlight"] is not None:
            valid &= np.isfinite(env["sunlight"])
            components["sunlight"] = np.clip(env["sunlight"]/600.0, 0, 1)
        denom = sum(raw_weights[key] for key in components)
        weights = {key: raw_weights[key]/denom for key in components}
        scores = sum(weights[key]*value for key, value in components.items())
        candidates = np.flatnonzero(valid)
        # Stable ordering keeps equal-score results deterministic.
        ordered = candidates[np.argsort(-scores.ravel()[candidates], kind="stable")]
        chosen = []
        for index in ordered:
            cell = tuple(int(v) for v in np.unravel_index(index, self.shape))
            if any(self.distance_m(cell, item["cell"]) < request.min_separation_km*1000 for item in chosen):
                continue
            chosen.append(dict(cell=cell, position=self.position(cell), score=float(scores[cell]),
                               components={key: float(value[cell]) for key, value in components.items()},
                               ice_consistency=float(ice[cell]), slope_deg=float(slope[cell]),
                               shielding=None))
            if len(chosen) >= request.limit:
                break
        for item in chosen:
            item.pop("cell")
        return dict(sites=chosen, weights=weights, excluded_components=["shielding"] +
                    (["sunlight"] if env["sunlight"] is None else []),
                    data=self.disclosure(request.mode))

    def distance_m(self, a, b):
        # Great-circle distance avoids treating the equirectangular grid's
        # longitude scale as a true distance at every latitude.
        lon, lat = self.lonlat
        dlon, dlat = lon[b]-lon[a], lat[b]-lat[a]
        h = math.sin(dlat/2)**2 + math.cos(lat[a])*math.cos(lat[b])*math.sin(dlon/2)**2
        return 2*3396190.0*math.asin(math.sqrt(min(1.0, max(0.0, h))))
