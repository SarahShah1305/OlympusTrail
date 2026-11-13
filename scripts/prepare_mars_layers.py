#!/usr/bin/env python3
"""Clip/resample Mars source rasters onto one local metric grid.

Inputs are downloaded source GeoTIFFs; this script does not fabricate science data.
Requires rasterio and numpy. See data/README.md for the Arcadia Planitia inputs.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import tempfile
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


def source_summary(path: Path | None):
    if path is None:
        return None
    with rasterio.open(path) as src:
        return {
            "file": path.name,
            "driver": src.driver,
            "width": src.width,
            "height": src.height,
            "band_count": src.count,
            "dtype": list(src.dtypes),
            "crs": src.crs.to_string() if src.crs else None,
            "bounds": [src.bounds.left, src.bounds.bottom, src.bounds.right, src.bounds.top],
            "pixel_size": list(src.res),
            "nodata": src.nodata,
        }


def warp(src_path: Path, dst_path: Path, crs, transform, width, height,
         categorical=False, source_nodata=None, unit=None, description=None):
    with rasterio.open(src_path) as src:
        data = np.full((height, width), np.nan, dtype="float32")
        nodata = src.nodata if source_nodata is None else source_nodata
        reproject(
            source=rasterio.band(src, 1), destination=data,
            src_transform=src.transform, src_crs=src.crs,
            src_nodata=nodata, dst_transform=transform, dst_crs=crs,
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
        if description:
            out.set_band_description(1, description)
        if unit:
            out.update_tags(1, UNIT=unit)


def convert_legacy_pbt(src_path: Path, dst_path: Path):
    """Apply PDS3 byte scaling/map offsets for older PBTs GDAL cannot georeference."""
    with rasterio.open(src_path) as src:
        if src.crs is not None:
            return src_path
        raw = src.read(1)
        height, width = raw.shape
    with src_path.open("rb") as stream:
        prefix = stream.read(64 * 1024).decode("ascii", errors="ignore")

    def field(name, cast=float):
        match = re.search(rf"^\s*{re.escape(name)}\s*=\s*\"?([^\s\"<]+)",
                          prefix, re.MULTILINE)
        if not match:
            raise ValueError(f"Missing {name} in PDS label for {src_path.name}")
        return cast(match.group(1))

    if field("MAP_PROJECTION_TYPE", str) != "SINUSOIDAL":
        raise ValueError(f"Unsupported legacy PBT projection in {src_path.name}")
    null = field("NULL_CONSTANT", int)
    offset = field("OFFSET")
    scale_dn = field("SCALING_FACTOR")
    pixel_m = field("MAP_SCALE") * 1000.0
    sample_offset = field("SAMPLE_PROJECTION_OFFSET")
    line_offset = field("LINE_PROJECTION_OFFSET")
    center_lon = field("CENTER_LONGITUDE")
    values = raw.astype("float32") * scale_dn + offset
    values[raw == null] = np.nan
    # PDS3 map offsets are referenced to pixel centers; these legacy PBT
    # labels store their line/sample projection offsets with opposite signs.
    transform = from_origin(sample_offset * pixel_m - pixel_m / 2,
                            -line_offset * pixel_m + pixel_m / 2,
                            pixel_m, pixel_m)
    crs = (f"+proj=sinu +lon_0={center_lon} +a={MARS_RADIUS_M} "
           f"+b={MARS_RADIUS_M} +units=m +no_defs")
    profile = {"driver": "GTiff", "height": height, "width": width,
               "count": 1, "dtype": "float32", "crs": crs,
               "transform": transform, "nodata": np.nan,
               "compress": "deflate", "predictor": 3, "tiled": True}
    with rasterio.open(dst_path, "w", **profile) as dst:
        dst.write(values, 1)
    return dst_path


def warp_thermal_mosaic(paths, dst_path, crs, transform, width, height):
    """Align PBT inputs, keep earlier-source pixels, and fill only their gaps."""
    mosaic = np.full((height, width), np.nan, dtype="float32")
    with tempfile.TemporaryDirectory(prefix="marspath-pbt-") as temp_dir:
        for index, source_path in enumerate(paths):
            with rasterio.open(source_path) as src:
                needs_legacy = src.crs is None
            prepared = source_path
            if needs_legacy:
                prepared = convert_legacy_pbt(
                    source_path, Path(temp_dir) / f"legacy_{index}.tif")
            with rasterio.open(prepared) as src:
                source_data = src.read(1).astype("float32")
                if src.nodata is not None:
                    if np.isnan(src.nodata):
                        source_data[np.isnan(source_data)] = np.nan
                    else:
                        source_data[source_data == src.nodata] = np.nan
                # PDS labels define zero as NULL_CONSTANT even when a GDAL
                # driver exposes a different floating-point nodata sentinel.
                source_data[source_data == 0] = np.nan
                warped = np.full((height, width), np.nan, dtype="float32")
                reproject(source=source_data, destination=warped,
                          src_transform=src.transform, src_crs=src.crs,
                          src_nodata=np.nan, dst_transform=transform,
                          dst_crs=crs, dst_nodata=np.nan,
                          resampling=Resampling.bilinear)
                fill = np.isnan(mosaic) & np.isfinite(warped)
                mosaic[fill] = warped[fill]
    profile = {"driver": "GTiff", "height": height, "width": width,
               "count": 1, "dtype": "float32", "crs": crs,
               "transform": transform, "nodata": np.nan,
               "compress": "deflate", "predictor": 3, "tiled": True}
    with rasterio.open(dst_path, "w", **profile) as dst:
        dst.write(mosaic, 1)
        dst.set_band_description(1, "THEMIS projected brightness temperature")
        dst.update_tags(1, UNIT="K", NODATA_SOURCE_VALUE="0",
                        MOSAIC_RULE="earlier inputs take precedence; later inputs fill nodata")


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
        # dz_dy is measured down the raster (southward); report downhill bearing
        # clockwise from north: 0=N, 90=E, 180=S, 270=W.
        aspect = (np.degrees(np.arctan2(-dz_dx, dz_dy)) + 360) % 360
        aspect[np.isnan(z)] = np.nan
        prof = ds.profile.copy()
        prof.update(dtype="float32", compress="deflate", predictor=3, tiled=True,
                    nodata=np.nan)
        for name, arr in (("slope_deg", slope), ("aspect_deg", aspect)):
            with rasterio.open(outdir / f"{name}.tif", "w", **prof) as dst:
                dst.write(arr.astype("float32"), 1)
                dst.set_band_description(1, name.replace("_", " "))
                dst.update_tags(1, UNIT="degree")


def clip_shelter_points(src_path: Path, dst_path: Path):
    """Clip GeoJSON or Mars Cave Catalog CSV points; convert 0–360E longitude."""
    kept = []
    if src_path.suffix.lower() == ".csv":
        with src_path.open(newline="", encoding="utf-8-sig") as stream:
            for row in csv.DictReader(stream):
                lon, lat = float(row["longitude"]), float(row["latitude"])
                props = {k: v for k, v in row.items() if k not in {"longitude", "latitude", "Feature"}}
                kept.append({"type": "Feature", "properties": props,
                             "geometry": {"type": "Point", "coordinates": [lon, lat]}})
    else:
        data = json.loads(src_path.read_text())
        for feature in data.get("features", []):
            geom = feature.get("geometry") or {}
            if geom.get("type") != "Point":
                continue
            lon, lat = geom["coordinates"][:2]
            feature["geometry"]["coordinates"][0] = lon
            kept.append(feature)
    clipped = []
    for feature in kept:
        lon, lat = feature["geometry"]["coordinates"][:2]
        if lon > 180:
            lon -= 360
        if WEST <= lon <= EAST and SOUTH <= lat <= NORTH:
            feature["geometry"]["coordinates"][0] = lon
            clipped.append(feature)
    dst_path.write_text(json.dumps({"type": "FeatureCollection", "features": clipped}, indent=2) + "\n")
    return len(clipped)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dem", required=True, type=Path, help="MOLA/HRSC elevation GeoTIFF")
    ap.add_argument("--ice", type=Path, help="SWIM ice-consistency GeoTIFF")
    ap.add_argument("--thermal", type=Path, action="append",
                    help="optional THEMIS PBT; repeat to mosaic multiple observations")
    ap.add_argument("--shelters", type=Path, help="optional shelter candidate GeoJSON")
    ap.add_argument("--out", type=Path, default=Path("data/processed"))
    ap.add_argument("--pixel-m", type=int, default=1000,
                    help="output spacing; 1000 m avoids implying source-scale detail")
    args = ap.parse_args()
    if args.pixel_m < 200:
        ap.error("pixel spacing below 200 m overstates the effective resolution of the ice data")
    crs, transform, width, height = target_grid(args.pixel_m)
    args.out.mkdir(parents=True, exist_ok=True)
    warp(args.dem, args.out / "elevation_m.tif", crs, transform, width, height,
         unit="m", description="MOLA elevation")
    terrain_derivatives(args.out / "elevation_m.tif", args.out)
    if args.ice:
        warp(args.ice, args.out / "ice_consistency.tif", crs, transform, width, height,
             unit="SWIM consistency index", description="SWIM ice consistency (0-1 m)")
    if args.thermal:
        # PBT labels specify Kelvin and NULL_CONSTANT=0. Older byte PBTs are
        # converted using their PDS OFFSET/SCALING_FACTOR and projection fields.
        warp_thermal_mosaic(args.thermal,
                            args.out / "thermal_brightness_temperature_k.tif",
                            crs, transform, width, height)
    cave_count = None
    if args.shelters:
        cave_count = clip_shelter_points(args.shelters, args.out / "cave_candidates.geojson")
    metadata = {
        "region": "Arcadia Planitia", "bbox_lonlat_east_positive": [WEST, SOUTH, EAST, NORTH],
        "grid_crs": crs, "pixel_size_m": args.pixel_m, "width": width, "height": height,
        "layers": [p.name for p in sorted(args.out.glob("*.tif"))],
        "cave_candidate_count": cave_count,
        "source_inputs": {"dem": source_summary(args.dem), "ice": source_summary(args.ice),
                          "thermal": [source_summary(path) for path in args.thermal] if args.thermal else [],
                          "cave_catalog_file": args.shelters.name if args.shelters else None},
        "thermal_valid_cell_fraction": None,
        "thermal_valid_cell_count": None,
        "thermal_null_values_masked": [0, "source raster nodata"],
        "thermal_mosaic_rule": "earlier inputs take precedence; later inputs fill nodata; no averaging",
        "caveat": "Resampling aligns grids; it does not increase the source data resolution.",
    }
    thermal_output = args.out / "thermal_brightness_temperature_k.tif"
    if thermal_output.exists():
        with rasterio.open(thermal_output) as ds:
            valid = ds.read(1, masked=True).count()
            metadata["thermal_valid_cell_fraction"] = round(valid / (width * height), 4)
            metadata["thermal_valid_cell_count"] = int(valid)
    (args.out / "grid.json").write_text(json.dumps(metadata, indent=2) + "\n")


if __name__ == "__main__":
    main()
