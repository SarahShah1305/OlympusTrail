"""Regrid the retained historical THEMIS observations and package cave sources.

Run from the repository root with the project Python environment.  This is a
repeatable preparation step; original finite cells in Claude's base raster are
never overwritten.
"""
from __future__ import annotations

import csv
import hashlib
import json
import shutil
import zipfile
from pathlib import Path

import numpy as np
import rasterio
from rasterio.warp import Resampling, reproject

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "data/person1/arcadia_500m"
COMPLETE = ROOT / "data/person1_complete"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def prepare_thermal() -> dict:
    src_value = COMPLETE / "thermal_observations_k.tif"
    src_ids = COMPLETE / "thermal_observation_source_id.tif"
    dst_value = PKG / "thermal_observed_k.tif"
    dst_ids = PKG / "thermal_observed_source_id.tif"
    with rasterio.open(src_value) as sv, rasterio.open(src_ids) as si, rasterio.open(dst_value) as dv:
        if sv.shape != si.shape or sv.crs != si.crs or sv.transform != si.transform:
            raise ValueError("3 km value and source-ID rasters do not share a grid")
        if dv.crs is None:
            raise ValueError("Claude target raster has no CRS")
        base = dv.read(1).astype("float32")
        target_profile = dv.profile.copy()
        base_finite = np.isfinite(base)
        sv_arr, si_arr = sv.read(1), si.read(1)
        # Only calibrated additions (IDs > 0) may fill gaps. ID 0 is already
        # represented by the untouched Claude base and is never resampled.
        valid_addition = np.isfinite(sv_arr) & (si_arr > 0)
        add_values = np.where(valid_addition, sv_arr, np.nan).astype("float32")
        add_ids = np.where(valid_addition, si_arr, -1).astype("int16")
        warped_values = np.full(base.shape, np.nan, dtype="float32")
        warped_ids = np.full(base.shape, -1, dtype="int16")
        args = dict(src_transform=sv.transform, src_crs=sv.crs,
                    dst_transform=dv.transform, dst_crs=dv.crs,
                    resampling=Resampling.nearest, src_nodata=np.nan, dst_nodata=np.nan)
        reproject(add_values, warped_values, **args)
        reproject(add_ids, warped_ids, **{**args, "src_nodata": -1, "dst_nodata": -1})
    if dst_ids.exists():
        with rasterio.open(dst_ids) as did:
            if did.shape != base.shape or did.transform != target_profile["transform"] or did.crs != target_profile["crs"]:
                raise ValueError("existing target source-ID raster grid mismatch")
            ids = did.read(1).astype("int16")
    else:
        ids = np.full(base.shape, -1, dtype="int16")
    # A finite cell without provenance is inherited base data. Preserve all
    # already assigned provenance IDs when this script runs again.
    ids[base_finite & (ids < 0)] = 0
    fill = ~base_finite & np.isfinite(warped_values) & (warped_ids > 0)
    base[fill] = warped_values[fill]
    ids[fill] = warped_ids[fill]
    # Keep an existing positive ID if there is already a retained fill there.
    ids[~np.isfinite(base)] = -1
    outprof = target_profile.copy()
    outprof.update(dtype="float32", nodata=np.nan, count=1, compress="deflate", predictor=3)
    with rasterio.open(dst_value, "w", **outprof) as out:
        out.write(base.astype("float32"), 1)
        out.set_band_description(1, "Historical THEMIS PBT brightness temperature")
        out.update_tags(1, UNIT="K", DATA_CLASS="historical_observation_atlas", REGRID="nearest neighbor from 3 km; existing finite base cells preserved")
    idprof = target_profile.copy()
    idprof.update(dtype="int16", nodata=-1, count=1, compress="deflate", predictor=2)
    with rasterio.open(dst_ids, "w", **idprof) as out:
        out.write(ids, 1)
        out.set_band_description(1, "Observation source ID; 0=original base, positive=added PBT product, -1=unknown")
    source_prov = json.loads((COMPLETE / "thermal_provenance.json").read_text(encoding="utf-8"))
    mapping = {int(k): v for k, v in source_prov["source_id_mapping"].items()}
    mapping[0] = "Claude base THEMIS PBT observations (preserved)"
    mapping[-1] = "Unknown / no finite observation"
    hist = {str(int(k)): int(v) for k, v in zip(*np.unique(ids, return_counts=True))}
    prov = {
        "data_class": "historical_observation_atlas",
        "unit": "K",
        "method": "Nearest-neighbor reprojection from retained 3 km THEMIS observations onto the 500 m Claude grid; original finite Claude cells are preserved exactly; only missing cells are filled from calibrated source IDs > 0.",
        "input_raster": "data/person1_complete/thermal_observations_k.tif",
        "input_source_ids": "data/person1_complete/thermal_observation_source_id.tif",
        "input_provenance": "data/person1_complete/thermal_provenance.json",
        "input_sha256": {p.name: sha256(p) for p in (src_value, src_ids, COMPLETE / "thermal_provenance.json")},
        "output_finite_cells": int(np.isfinite(base).sum()),
        "output_total_cells": int(base.size),
        "output_coverage_fraction": float(np.isfinite(base).mean()),
        "original_finite_cells_preserved": int(np.count_nonzero(ids == 0)),
        "existing_finite_cells_preserved_this_run": int(base_finite.sum()),
        "total_retained_addition_cells": int(np.count_nonzero(ids > 0)),
        "newly_filled_cells_this_run": int(fill.sum()),
        "source_id_cell_counts": hist,
        "source_id_mapping": {str(k): v for k, v in mapping.items()},
        "source_observation_provenance": source_prov,
        "limitations": ["Historical acquisitions span different dates and local times; this is not a contemporaneous map.", "Nearest-neighbor reprojection to 500 m does not add measurement detail beyond the native approximately 3 km source grid.", "Unobserved target cells remain nodata; no model fill is applied."]
    }
    (PKG / "thermal_provenance.json").write_text(json.dumps(prov, indent=2) + "\n", encoding="utf-8")
    thermal_sources = PKG / "sources/thermal"
    thermal_sources.mkdir(parents=True, exist_ok=True)
    for p in (src_value, src_ids, COMPLETE / "thermal_provenance.json"):
        shutil.copy2(p, thermal_sources / p.name)
    for product in source_prov["products"]:
        if "header_sha256" not in product:
            continue
        header = ROOT/"work/downloads/thermal/headers"/(product["id"]+".header")
        target = thermal_sources/(product["id"]+".pds-header.bin")
        if header.exists():
            if sha256(header) != product["header_sha256"]:
                raise ValueError("Retained PDS header hash mismatch: " + product["id"])
            shutil.copy2(header, target)
    return {"finite": prov["output_finite_cells"], "total": int(base.size), "filled": int(fill.sum()), "coverage": prov["output_coverage_fraction"]}


def prepare_caves() -> dict:
    src = ROOT / "work/downloads/caves"
    out = PKG / "sources/caves"
    out.mkdir(parents=True, exist_ok=True)
    zip_path = (src if (src/"mars_cave_catalog.zip").exists() else out) / "mars_cave_catalog.zip"
    csv_path = (src if (src/"Mars_Cave_Catalog_shapefile.csv").exists() else out) / "Mars_Cave_Catalog_shapefile.csv"
    inventory_path = ROOT / "work/cave-inventory.json"
    for p in (zip_path, csv_path, src / "usgs-catalog-landing.html", inventory_path):
        target = out / ("cave-inventory.json" if p == inventory_path else p.name)
        if p.exists() and p.resolve() != target.resolve():
            shutil.copy2(p, target)
    rows = []
    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if not {"longitude", "latitude"}.issubset(reader.fieldnames or []):
            raise ValueError("companion catalog CSV lacks unambiguous longitude/latitude columns")
        for row in reader:
            lon, lat = float(row["longitude"]), float(row["latitude"])
            if not (np.isfinite(lon) and np.isfinite(lat) and 0 <= lon <= 360 and -90 <= lat <= 90):
                raise ValueError("Invalid cave catalog coordinate")
            if 187 <= lon <= 203 and 40 <= lat <= 58:
                rows.append({"type": "Feature", "geometry": {"type": "Point", "coordinates": [lon, lat]}, "properties": {k: v for k, v in row.items() if k not in ("longitude", "latitude")}})
    collection = {"type": "FeatureCollection", "name": "USGS Mars Global Cave Candidate Catalog v1; inclusive 40-58N, 187-203E filter", "features": rows}
    (PKG / "cave_candidates.geojson").write_text(json.dumps(collection, indent=2) + "\n", encoding="utf-8")
    with zipfile.ZipFile(zip_path) as zf:
        members = zf.namelist()
    check = {
        "catalog_title": "Mars Global Cave Candidate Catalog v1 (Cushing)",
        "source_url": "https://astrogeology.usgs.gov/ckan/dataset/c2960f77-ee20-4cc6-ac85-abbecc0fc7f6/resource/ccd54fb2-9a50-46bf-8971-80c241bb2f40/download/mars_cave_catalog.zip",
        "landing_page": "https://astrogeology.usgs.gov/search/map/mars_global_cave_candidate_catalog_v1_cushing",
        "zip_sha256": sha256(zip_path),
        "companion_csv_sha256": sha256(csv_path),
        "catalog_total": sum(1 for _ in csv.DictReader(csv_path.open("r", encoding="utf-8-sig", newline=""))),
        "region_bounds_inclusive": {"longitude_east_deg": [187, 203], "latitude_north_deg": [40, 58]},
        "longitude_convention": "0-360 degrees east, matching explicit companion CSV longitude column",
        "count_40_58N": len(rows),
        "checked_40_58N": True,
        "checked_52_58N": True,
        "candidate_geojson": "../../cave_candidates.geojson",
        "zip_members": members,
        "interpretation": "Candidate cave entrances from orbital imagery only; no confirmed accessible or safe shelters. A zero regional count is an actual filter result from the coordinate-explicit companion CSV, not a parse failure."
    }
    (out / "catalog_check.json").write_text(json.dumps(check, indent=2) + "\n", encoding="utf-8")
    return check


def prepare() -> dict:
    """Run both repeatable preparation steps and return compact count summary."""
    return {"thermal": prepare_thermal(), "caves": prepare_caves()}


if __name__ == "__main__":
    print(json.dumps(prepare(), indent=2))
