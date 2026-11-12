#!/usr/bin/env python3
"""Clip/resample Mars source rasters onto one local metric grid.

Inputs are downloaded source GeoTIFFs; this script does not fabricate science data.
Requires rasterio and numpy. See data/README.md for the Arcadia Planitia inputs.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.warp import reproject
from rasterio.transform import from_origin

# Arcadia Planitia demo window, planetocentric latitude / east longitude.
# Centered on the shallow-ice region; use a local equirectangular Mars CRS.
WEST, SOUTH, EAST, NORTH = -173.0, 40.0, -157.0, 52.0
MARS_RADIUS_M = 3_396_190.0


def target_grid(pixel_m: int):
    lat0 = (SOUTH + NORTH) / 2
    x0 = np.deg2rad(WEST) * MARS_RADIUS_M * np.cos(np.deg2rad(lat0))
    x1 = np.deg2rad(EAST) * MARS_RADIUS_M * np.cos(np.deg2rad(lat0))
    y0 = np.deg2rad(NORTH) * MARS_RADIUS_M
    y1 = np.deg2rad(SOUTH) * MARS_RADIUS_M
    width = int(np.ceil((x1 - x0) / pixel_m))
    height = int(np.ceil((y0 - y1) / pixel_m))
    transform = from_origin(x0, y0, pixel_m, pixel_m)
    crs = (
        f"+proj=eqc +lat_ts={lat0} +lat_0=0 +lon_0=0 "
        f"+a={MARS_RADIUS_M} +b={MARS_RADIUS_M} +units=m +no_defs"
    )
    return crs, transform, width, height


def warp(src_path: Path, dst_path: Path, crs, transform, width, height,
         categorical=False):
    with rasterio.open(src_path) as src:
        data = np.full((height, width), np.nan, dtype="float32")
        reproject(
            source=rasterio.band(src, 1), destination=data,
            src_transform=src.transform, src_crs=src.crs,
            src_nodata=src.nodata, dst_transform=transform, dst_crs=crs,
            dst_nodata=np.nan,
            resampling=Resampling.nearest if categorical else Resampling.bilinear,
        )
    profile = {
        "driver": "GTiff", "height": height, "width": width, "count": 1,
        "dtype": "float32", "crs": crs, "transform": transform,
        "nodata": np.nan, "compress": "deflate", "predictor": 3,
        "tiled": True,
    }
    dst_path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(dst_path, "w", **profile) as out:
        out.write(data, 1)


def terrain_derivatives(dem_path: Path, outdir: Path):
    """Derive slope degrees and aspect degrees clockwise from north."""
    with rasterio.open(dem_path) as ds:
        z = ds.read(1).astype("float64")
        if ds.nodata is not None:
            z[z == ds.nodata] = np.nan
        px = abs(ds.transform.a)
        py = abs(ds.transform.e)
        dz_dy, dz_dx = np.gradient(z, py, px)
        slope = np.degrees(np.arctan(np.hypot(dz_dx, dz_dy)))
        # Array rows increase southward, so negate dz_dy to form the northward axis.
        aspect = (np.degrees(np.arctan2(-dz_dx, -dz_dy)) + 360) % 360
        aspect[np.isnan(z)] = np.nan
        prof = ds.profile.copy()
        prof.update(dtype="float32", compress="deflate", predictor=3, tiled=True,
                    nodata=np.nan)
        for name, arr in (("slope_deg", slope), ("aspect_deg", aspect)):
            with rasterio.open(outdir / f"{name}.tif", "w", **prof) as dst:
                dst.write(arr.astype("float32"), 1)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dem", required=True, type=Path, help="MOLA/HRSC elevation GeoTIFF")
    ap.add_argument("--ice", type=Path, help="SWIM ice-consistency GeoTIFF")
    ap.add_argument("--thermal", type=Path, help="optional THEMIS/TES temperature raster")
    ap.add_argument("--shelters", type=Path, help="optional shelter candidate GeoJSON")
    ap.add_argument("--out", type=Path, default=Path("data/processed"))
    ap.add_argument("--pixel-m", type=int, default=1000,
                    help="output spacing; 1000 m avoids implying source-scale detail")
    args = ap.parse_args()
    if args.pixel_m < 200:
        ap.error("pixel spacing below 200 m overstates the effective resolution of the ice data")
    crs, transform, width, height = target_grid(args.pixel_m)
    args.out.mkdir(parents=True, exist_ok=True)
    warp(args.dem, args.out / "elevation_m.tif", crs, transform, width, height)
    terrain_derivatives(args.out / "elevation_m.tif", args.out)
    if args.ice:
        warp(args.ice, args.out / "ice_consistency.tif", crs, transform, width, height)
    if args.thermal:
        warp(args.thermal, args.out / "surface_temperature_k.tif", crs, transform,
             width, height)
    if args.shelters:
        # Keep source coordinates intact and provide the target grid metadata alongside.
        (args.out / "shelter_candidates.geojson").write_bytes(args.shelters.read_bytes())
    metadata = {
        "region": "Arcadia Planitia", "bbox_lonlat_east_positive": [WEST, SOUTH, EAST, NORTH],
        "grid_crs": crs, "pixel_size_m": args.pixel_m, "width": width, "height": height,
        "layers": [p.name for p in sorted(args.out.glob("*.tif"))],
        "caveat": "Resampling aligns grids; it does not increase the source data resolution.",
    }
    (args.out / "grid.json").write_text(json.dumps(metadata, indent=2) + "\n")


if __name__ == "__main__":
    main()
