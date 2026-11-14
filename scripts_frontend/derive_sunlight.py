#!/usr/bin/env python
"""Derive a relative MOLA illumination index at local solar noon on equinox."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
import rasterio
from rasterio.warp import transform_bounds

from convert_layers import PALETTE, mars_geographic_crs, write_values_overlay


ASSUMPTIONS = (
    "Local solar noon, solar declination 0 degrees (equinox), Sun due south "
    "for this northern-hemisphere region. Direct-beam cosine incidence is "
    "clipped to 0-1. Ignores atmosphere, dust, shadows and seasonal/daylight "
    "duration; relative index only."
)


def _read_aligned(path: Path, reference: rasterio.DatasetReader) -> tuple[np.ndarray, np.ndarray]:
    with rasterio.open(path) as dataset:
        if (
            dataset.shape != reference.shape
            or dataset.transform != reference.transform
            or dataset.crs != reference.crs
        ):
            raise ValueError(f"{path.name} is not aligned to elevation_m.tif.")
        values = dataset.read(1).astype(np.float32)
        valid = (dataset.read_masks(1) > 0) & np.isfinite(values)
        return values, valid


def derive(input_dir: Path, output_dir: Path) -> Path:
    grid_path = input_dir / "grid.json"
    if not grid_path.is_file():
        raise FileNotFoundError(f"Required grid metadata not found: {grid_path}")
    grid = json.loads(grid_path.read_text(encoding="utf-8"))
    parameters = {
        key[1:]: value
        for token in grid["grid_crs"].split()
        if token.startswith("+") and "=" in token
        for key, value in [token.split("=", maxsplit=1)]
    }
    radius = float(parameters["a"])
    latitude_origin = float(parameters.get("lat_0", 0))

    elevation_path = input_dir / "elevation_m.tif"
    slope_path = input_dir / "slope_deg.tif"
    aspect_path = input_dir / "aspect_deg.tif"
    with rasterio.open(elevation_path) as elevation:
        elevation_values = elevation.read(1).astype(np.float32)
        valid = (elevation.read_masks(1) > 0) & np.isfinite(elevation_values)
        slope_values, slope_valid = _read_aligned(slope_path, elevation)
        aspect_values, aspect_valid = _read_aligned(aspect_path, elevation)
        valid &= slope_valid & aspect_valid
        rows = np.arange(elevation.height, dtype=np.float64)
        northing = elevation.transform.f + (rows + 0.5) * elevation.transform.e
        latitude = np.deg2rad(northing / radius * 180 / math.pi + latitude_origin)
        slope = np.deg2rad(slope_values)
        aspect = np.deg2rad(aspect_values)

        solar_altitude = math.pi / 2 - np.abs(latitude[:, np.newaxis])
        solar_azimuth = math.pi
        incidence = (
            np.sin(solar_altitude) * np.cos(slope)
            + np.cos(solar_altitude) * np.sin(slope) * np.cos(aspect - solar_azimuth)
        )
        illumination = np.clip(incidence, 0, 1).astype(np.float32)
        output_dir.mkdir(parents=True, exist_ok=True)
        image_path = output_dir / "sunlight.png"
        minimum, maximum = write_values_overlay(
            illumination,
            valid,
            image_path,
            PALETTE["sunlight"],
        )
        west, south, east, north = transform_bounds(
            elevation.crs,
            mars_geographic_crs(grid["grid_crs"]),
            *elevation.bounds,
            densify_pts=21,
        )
        count = int(valid.sum())
        total = int(valid.size)

    metadata_path = output_dir / "layers.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["layers"] = [layer for layer in metadata["layers"] if layer["id"] != "sunlight"]
    metadata["layers"].append(
        {
            "id": "sunlight",
            "label": "Relative illumination · equinox noon",
            "image": image_path.name,
            "bounds_latlng": [[south, west], [north, east]],
            "width": grid["width"],
            "height": grid["height"],
            "min": minimum,
            "max": maximum,
            "units": "relative index (0–1)",
            "coverage_percent": round(count / total * 100, 2),
            "valid_pixels": count,
            "total_pixels": total,
            "description": (
                "Derived from MOLA terrain. Ignores atmosphere, dust and shadows. "
                "Relative index only."
            ),
            "assumptions": ASSUMPTIONS,
            "source": "mola",
            "badge": "Derived",
            "legend_colors": PALETTE["sunlight"],
        }
    )
    metadata_path.write_text(
        json.dumps(metadata, indent=2) + "\n",
        encoding="utf-8",
    )
    return metadata_path


def main() -> None:
    repository_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=repository_root / "data" / "processed",
        help="Directory containing grid.json and the aligned MOLA GeoTIFFs.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=repository_root / "frontend" / "public" / "layers",
        help="Directory for the PNG overlay and layers.json.",
    )
    arguments = parser.parse_args()
    result = derive(arguments.input_dir, arguments.output_dir)
    print(f"Wrote {result}; sunlight assumptions: {ASSUMPTIONS}")


if __name__ == "__main__":
    main()
