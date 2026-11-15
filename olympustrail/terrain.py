from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path
from collections.abc import MutableMapping
from threading import RLock

import numpy as np
import rasterio
from rasterio.crs import CRS
from rasterio.transform import rowcol, xy
from rasterio.warp import transform as project

from .models import Position, RouteRequest, SiteRequest

MARS_GEOGRAPHIC = CRS.from_string("+proj=longlat +a=3396190 +b=3396190 +no_defs")
LOCAL_TIMES = (0, 6, 12, 18)


class RasterLayers(MutableMapping):
    """Read aligned source rasters only when used; retain source float32 precision."""
    def __init__(self, paths, geometry):
        self.paths = paths
        self.geometry = geometry
        self.cache = {}
        self.lock = RLock()

    def __getitem__(self, name):
        with self.lock:
            if name not in self.cache:
                path = self.paths[name]
                for loaded, values in self.cache.items():
                    if self.paths.get(loaded) == path:
                        self.cache[name] = values
                        return values
                with rasterio.Env(GDAL_CACHEMAX=16 * 1024 * 1024), rasterio.open(path) as src:
                    if (src.shape, src.transform, src.crs) != self.geometry or src.count != 1:
                        raise ValueError(f"Misaligned or multiband layer: {path}")
                    # Source values are float32. Arithmetic that affects ranking
                    # or route decisions is explicitly promoted to float64 below.
                    dtype = "float64" if src.dtypes[0] == "float64" else "float32"
                    self.cache[name] = src.read(1, masked=True).astype(dtype).filled(np.nan)
            return self.cache[name]

    def __setitem__(self, name, value):
        self.cache[name] = value

    def __delitem__(self, name):
        self.cache.pop(name, None)
        self.paths.pop(name, None)

    def __iter__(self):
        return iter(dict.fromkeys([*self.paths, *self.cache]))

    def __len__(self):
        return len(set(self.paths) | self.cache.keys())

    def __contains__(self, name):
        return name in self.paths or name in self.cache


@dataclass
class TerrainGrid:
    layers: dict[str, np.ndarray]
    transform: object
    crs: CRS
    metadata: dict

    @classmethod
    def load(cls, root: Path, dataset: str | None = None):
        """Load the Person 1 analysis grid.

        ``arcadia_500m`` (default) is the 500 m, 40-58N grid built by
        scripts/prepare_person1_hires.py. ``regional_3km`` is Person 2's
        original 3 km handoff plus the noon-only MCD layers, kept for
        comparison. Set OLYMPUSTRAIL_DATASET to choose without code changes.
        """
        dataset = dataset or os.environ.get("OLYMPUSTRAIL_DATASET", "arcadia_500m")
        if dataset == "regional_3km":
            return cls._load_regional(root)
        if dataset != "arcadia_500m":
            raise ValueError(f"Unknown dataset {dataset!r}")
        folder = root / "data/person1/arcadia_500m"
        manifest = json.loads((folder / "manifest.json").read_text())
        files = dict(
            elevation="elevation_m", slope="slope_deg", aspect="aspect_deg", ice="ice_consistency",
            observed_temperature="thermal_observed_k", dust="dust_optical_depth",
            sunlight="sunlight_mean_w_m2", radiation="radiation_msv_h",
            sky_blocked="sky_blocked_fraction", pressure="pressure_pa",
            **{f"temperature_lt{lt:02d}": f"temperature_lt{lt:02d}_k" for lt in LOCAL_TIMES},
            **{f"sunlight_lt{lt:02d}": f"sunlight_lt{lt:02d}_w_m2" for lt in LOCAL_TIMES},
        )
        if (folder/"thermal_observed_source_id.tif").exists():
            files["thermal_observation_source_id"] = "thermal_observed_source_id"
        arrays, geometry = cls._read_aligned({key: folder / f"{name}.tif" for key, name in files.items()})
        arrays.paths["scenario_temperature"] = arrays.paths["temperature_lt12"]
        shape, affine, crs = geometry
        if shape != (manifest["height"], manifest["width"]):
            raise ValueError("Raster dimensions disagree with manifest.json")
        shelters = json.loads((folder / manifest["shelters"]["file"]).read_text())["features"]
        return cls(arrays, affine, crs, dict(dataset=dataset, manifest=manifest, shelters=shelters,
                                             region=manifest["region"]))

    @classmethod
    def _load_regional(cls, root: Path):
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
        arrays, geometry = cls._read_aligned(paths)
        shape, affine, crs = geometry
        if shape != (grid_metadata["height"], grid_metadata["width"]):
            raise ValueError("Raster dimensions disagree with original grid.json")
        return cls(arrays, affine, crs, dict(dataset="regional_3km", grid=grid_metadata,
                                             supplemental=manifest, shelters=[],
                                             region="Arcadia Planitia"))

    @staticmethod
    def _read_aligned(paths):
        with rasterio.open(paths["elevation"]) as src:
            geometry = (src.shape, src.transform, src.crs)
        return RasterLayers(paths, geometry), geometry

    @property
    def shape(self):
        return self.layers.geometry[0] if isinstance(self.layers, RasterLayers) else self.layers["elevation"].shape

    @property
    def pixel_m(self):
        return abs(self.transform.a)

    @cached_property
    def lonlat(self):
        # Chunk projection to avoid millions of Python coordinate objects and
        # several full-grid temporaries alive at once. Keep float64 coordinates.
        lon = np.empty(self.shape, dtype=np.float64)
        lat = np.empty(self.shape, dtype=np.float64)
        for first in range(0, self.shape[0], 32):
            last = min(first + 32, self.shape[0])
            rows, cols = np.indices((last - first, self.shape[1]))
            xs, ys = xy(self.transform, (rows + first).ravel(), cols.ravel())
            longitude, latitude = project(self.crs, MARS_GEOGRAPHIC, xs, ys)
            lon[first:last] = np.deg2rad(np.asarray(longitude).reshape(last - first, -1))
            lat[first:last] = np.deg2rad(np.asarray(latitude).reshape(last - first, -1))
        return lon, lat

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

    def environment(self, mode: str, local_time_h: int = 12):
        """Layers used for routing. Scenario temperature/sunlight follow the
        requested local time when the grid has per-time layers."""
        layers = self.layers
        if mode == "observations":
            return dict(temperature=layers["observed_temperature"], dust=None, radiation=None, sunlight=None)
        key = f"{local_time_h:02d}"
        return dict(
            temperature=layers["temperature_lt" + key] if "temperature_lt" + key in layers else layers["scenario_temperature"],
            dust=layers["dust"], radiation=layers["radiation"],
            sunlight=layers["sunlight_lt" + key] if "sunlight_lt" + key in layers else layers["sunlight"],
        )

    @property
    def has_shielding(self):
        # Geometric horizon obstruction does not establish dose attenuation.
        return False

    def disclosure(self, mode: str, local_time_h: int = 12):
        dataset = self.metadata.get("dataset", "synthetic")
        hires = dataset == "arcadia_500m"
        if hires:
            scenario = dict(id="mcd62_ls90", season_ls_deg=90, local_time_h=local_time_h,
                            available_local_times_h=list(LOCAL_TIMES),
                            dust="MCD climatology average solar")
        else:
            scenario = self.metadata.get("supplemental", {}).get("scenario")
        radiation_source = "uniform Gale RAD reference assumption, extrapolated to Arcadia"
        shelters = self.metadata.get("shelters", [])
        return dict(
            mode=mode, dataset=dataset, grid_spacing_m=self.pixel_m,
            scenario=scenario if mode == "scenario" else None,
            thermal_observation_coverage=float(np.isfinite(self.layers["observed_temperature"]).mean()),
            radiation_source=radiation_source if mode == "scenario" else "unavailable",
            shielding_available=self.has_shielding,
            shielding_kind=None, terrain_obstruction_available="sky_blocked" in self.layers,
            radiation_protection_validated=False, regional_radiation_measurements_available=False,
            shelter_candidate_count=len(shelters), verified_shelter_count=0,
            cave_candidate_count=self.metadata.get("manifest", {}).get("caves", {}).get("count_40_58N", 0),
            assumptions=[
                ("500 m MOLA grid: resolves km-scale craters and scarps, not boulders or rover-scale hazards."
                 if hires else "Regional 3 km grid, not astronaut-scale obstacle or shelter verification."),
                ("Static MCD climate scenario at the requested local time; conditions do not change during the trip."
                 if mode == "scenario" else
                 "Partial historical thermal observations; cells without temperature are blocked."),
                "Radiation uses a uniform Gale dose-equivalent reference; no Arcadia calibration, terrain attenuation or solar particle events.",
                "Blocked sky fraction measures DEM geometry and is not converted into radiation protection or a shielding score.",
                "Ice consistency is SWIM's ~3 km product resampled; it is not finer than 3 km.",
                "Terrain shelter candidates are walls that hide part of the sky, not caves or verified shelters.",
                "Walking and battery parameters are illustrative, pending Person 5 validation.",
            ],
            excluded_risk_components=[] if mode == "scenario" else ["dust", "radiation"],
        )

    def risk_grid(self, request: RouteRequest):
        env = self.environment(request.mode, request.local_time_h)
        params = request.parameters
        slope = self.layers["slope"].astype(np.float64, copy=False)
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
            temperature=np.clip((params.cold_reference_k - env["temperature"].astype(np.float64, copy=False)) / 70.0, 0, 1),
        )
        if env["dust"] is not None:
            components["dust"] = np.clip(env["dust"].astype(np.float64, copy=False), 0, 1)
        if env["radiation"] is not None:
            # Normalize the uniform reference for the demo risk scale. This
            # term supplies no spatial radiation or shielding information.
            components["radiation"] = np.clip(env["radiation"].astype(np.float64, copy=False) / 0.035, 0, 1)
        weights = request.weights.model_dump()
        total = sum(weights[key] for key in components)
        if total <= 0:
            raise ValueError("All selected risk weights refer to unavailable layers")
        normalized = {key: weights[key] / total for key in components}
        risk = sum(normalized[key] * values for key, values in components.items())
        return np.where(valid, 1.0 + 4.0 * risk, np.inf), env, normalized

    def sites(self, request: SiteRequest):
        env = self.environment(request.mode)
        slope, ice = (self.layers[name].astype(np.float64, copy=False) for name in ("slope", "ice"))
        valid = (np.isfinite(ice) & np.isfinite(slope) & np.isfinite(self.layers["elevation"]) &
                 np.isfinite(env["temperature"]) & (slope >= 0) & (slope <= request.max_slope_deg))
        if request.edge_buffer_km > 0:
            buffer = int(math.ceil(request.edge_buffer_km * 1000 / self.pixel_m))
            inner = np.zeros(self.shape, dtype=bool)
            inner[buffer:self.shape[0]-buffer, buffer:self.shape[1]-buffer] = True
            valid &= inner
        components = dict(ice=np.clip(ice, 0, 1), flatness=1-np.clip(slope/request.max_slope_deg, 0, 1))
        raw_weights = dict(ice=0.45, flatness=0.30, sunlight=0.15, shielding=0.10)
        sunlight = self.layers["sunlight"].astype(np.float64, copy=False) if request.mode == "scenario" else None
        if sunlight is not None:
            valid &= np.isfinite(sunlight)
            # Relative within the region: the mean-flux layer is a 4-sample proxy.
            lo, hi = np.nanmin(sunlight), np.nanmax(sunlight)
            components["sunlight"] = (sunlight - lo) / (hi - lo) if hi > lo else np.ones(self.shape)
        # Exclude unvalidated shielding from scores and renormalize the weights.
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
                               shielding=(float(components["shielding"][cell]) if "shielding" in components else None),
                               nearest_shelter=self.nearest_shelter(cell)))
            if "sky_blocked" in self.layers:
                chosen[-1]["terrain_obstruction_fraction"] = float(self.layers["sky_blocked"][cell])
            if len(chosen) >= request.limit:
                break
        for item in chosen:
            item.pop("cell")
        excluded = [key for key in raw_weights if key not in components]
        return dict(sites=chosen, weights=weights, excluded_components=excluded,
                    data=self.disclosure(request.mode))

    def nearest_shelter(self, cell, max_km: float | None = None):
        best = None
        for feature in self.metadata.get("shelters", []):
            props = feature["properties"]
            d = self.distance_m(cell, (props["row"], props["col"])) / 1000
            if (max_km is None or d <= max_km) and (best is None or d < best["distance_km"]):
                best = dict(position=self.position((props["row"], props["col"])), distance_km=d,
                            sky_blocked_fraction=props["sky_blocked_fraction"], kind=props["kind"],
                            verified_shelter=False, radiation_protection_validated=False)
        return best

    def distances_from(self, cell):
        """Great-circle distance (m) from one cell to every cell, vectorized."""
        lon, lat = self.lonlat
        dlon, dlat = lon - lon[cell], lat - lat[cell]
        h = np.sin(dlat/2)**2 + np.cos(lat[cell])*np.cos(lat)*np.sin(dlon/2)**2
        return 2*3396190.0*np.arcsin(np.sqrt(np.clip(h, 0.0, 1.0)))

    def distance_m(self, a, b):
        # Great-circle distance avoids treating the equirectangular grid's
        # longitude scale as a true distance at every latitude.
        lon, lat = self.lonlat
        dlon, dlat = lon[b]-lon[a], lat[b]-lat[a]
        h = math.sin(dlat/2)**2 + math.cos(lat[a])*math.cos(lat[b])*math.sin(dlon/2)**2
        return 2*3396190.0*math.asin(math.sqrt(min(1.0, max(0.0, h))))
