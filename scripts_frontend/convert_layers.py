#!/usr/bin/env python
"""Convert the aligned Mars GeoTIFFs to transparent web map overlays."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
import rasterio
from netCDF4 import Dataset
from PIL import Image
from rasterio.crs import CRS
from rasterio.warp import transform_bounds


PALETTE = {
    "elevation": ["#1B2D52", "#2A4278", "#E9DFCC", "#FF6B5B"],
    "slope": ["#1B2D52", "#22386A", "#E9DFCC", "#FF6B5B"],
    "aspect": ["#1B2D52", "#2A4278", "#E9DFCC", "#FF6B5B", "#1B2D52"],
    "ice": ["#1B2D52", "#2A4278", "#E9DFCC", "#FF6B5B"],
    "temperature": ["#1B2D52", "#22386A", "#E9DFCC", "#FF6B5B"],
    "sunlight": ["#1B2D52", "#22386A", "#E9DFCC", "#FF6B5B"],
    "dust": ["#1B2D52", "#22386A", "#E9DFCC", "#FF6B5B"],
}

LAYER_SPECS = {
    "elevation_m.tif": {
        "id": "elevation",
        "label": "Elevation",
        "units": "m",
        "description": "Regional scale on a 3 km grid, not rover-scale hazards.",
        "source": "mola",
    },
    "slope_deg.tif": {
        "id": "slope",
        "label": "Slope",
        "units": "degrees",
        "description": "Regional scale on a 3 km grid, not rover-scale hazards.",
        "source": "mola",
    },
    "aspect_deg.tif": {
        "id": "aspect",
        "label": "Aspect",
        "units": "degrees clockwise from north",
        "description": "Downhill bearing. Flat-cell bearings are unreliable.",
        "source": "mola",
    },
    "ice_consistency.tif": {
        "id": "ice",
        "label": "Ice",
        "units": "consistency index (0–1 m)",
        "description": (
            "SWIM consistency index of ice in the upper metre. Not ice depth, "
            "not a probability, not a confirmed deposit."
        ),
        "source": "swim",
    },
    "thermal_brightness_temperature_k.tif": {
        "id": "temperature",
        "label": "Temperature",
        "units": "K",
        "description": (
            "Partial coverage from 3 THEMIS scenes taken on different dates. "
            "Not a forecast. Empty areas have no data."
        ),
        "source": "themis",
    },
}


def mars_geographic_crs(grid_crs: str) -> CRS:
    """Build a longitude/latitude CRS on the Mars sphere used by the grid."""
    parameters = _grid_parameters(grid_crs)
    radius = parameters.get("a")
    if radius is None:
        raise ValueError("grid.json grid_crs must specify the Mars sphere radius (+a).")
    return CRS.from_proj4(
        f"+proj=longlat +a={radius} +b={parameters.get('b', radius)} "
        f"+lon_0={parameters.get('lon_0', '0')} +no_defs +type=crs"
    )


def _grid_parameters(grid_crs: str) -> dict[str, str]:
    parameters = {}
    for token in grid_crs.split():
        if token.startswith("+") and "=" in token:
            key, value = token[1:].split("=", maxsplit=1)
            parameters[key] = value
    return parameters


def _interpolate_palette(values: np.ndarray, stops: list[str]) -> np.ndarray:
    colors = np.array(
        [
            [int(color[index : index + 2], 16) for index in (1, 3, 5)]
            for color in stops
        ],
        dtype=np.float64,
    )
    positions = np.linspace(0.0, 1.0, num=len(stops))
    channels = [
        np.interp(values.ravel(), positions, colors[:, channel]).reshape(values.shape)
        for channel in range(3)
    ]
    return np.stack(channels, axis=-1).round().astype(np.uint8)


def write_values_overlay(
    values: np.ndarray,
    valid: np.ndarray,
    destination: Path,
    colors: list[str],
) -> tuple[float, float]:
    if not valid.any():
        raise ValueError(f"{destination.name} contains no valid pixels.")
    minimum = float(values[valid].min())
    maximum = float(values[valid].max())
    if math.isclose(minimum, maximum):
        normalized = np.zeros(values.shape, dtype=np.float32)
    else:
        normalized = np.clip((values - minimum) / (maximum - minimum), 0, 1)
    normalized = np.where(valid, normalized, 0)
    rgba = np.zeros((*values.shape, 4), dtype=np.uint8)
    rgba[..., :3] = _interpolate_palette(normalized, colors)
    rgba[..., 3] = np.where(valid, 255, 0).astype(np.uint8)
    Image.fromarray(rgba).save(destination, optimize=True)
    return minimum, maximum


def _write_overlay(
    source: Path,
    destination: Path,
    layer_id: str,
    colors: list[str],
    geographic_crs: CRS,
) -> dict:
    with rasterio.open(source) as dataset:
        values = dataset.read(1).astype(np.float32)
        valid = (dataset.read_masks(1) > 0) & np.isfinite(values)
        minimum, maximum = write_values_overlay(
            values,
            valid,
            destination,
            colors,
        )
        count = int(valid.sum())
        total = int(valid.size)
        west, south, east, north = transform_bounds(
            dataset.crs,
            geographic_crs,
            *dataset.bounds,
            densify_pts=21,
        )
        return {
            "id": layer_id,
            "image": destination.name,
            "bounds_latlng": [[south, west], [north, east]],
            "width": dataset.width,
            "height": dataset.height,
            "min": minimum,
            "max": maximum,
            "units": LAYER_SPECS[source.name]["units"],
            "coverage_percent": round(count / total * 100, 2),
            "valid_pixels": count,
            "total_pixels": total,
        }


def _write_dust_overlay(
    source: Path,
    reference_path: Path,
    output_dir: Path,
    grid: dict,
    output_bounds: list,
) -> dict:
    with Dataset(source) as dataset, rasterio.open(reference_path) as reference:
        for name in ("longitude", "latitude", "cdodtot"):
            if name not in dataset.variables:
                raise ValueError(f"{source.name} is missing the required {name!r} variable.")
        values = np.ma.asarray(dataset.variables["cdodtot"][:], dtype=np.float32)
        if values.ndim != 3 or values.shape[1:] != (len(dataset["latitude"]), len(dataset["longitude"])):
            raise ValueError("cdodtot must have (time, latitude, longitude) dimensions.")
        annual = np.ma.mean(values, axis=0)
        latitudes = np.asarray(dataset.variables["latitude"][:], dtype=np.float64)
        longitudes = np.asarray(dataset.variables["longitude"][:], dtype=np.float64)
        parameters = _grid_parameters(grid["grid_crs"])
        radius = float(parameters["a"])
        lat_ts = math.radians(float(parameters.get("lat_ts", "0")))
        latitude_origin = float(parameters.get("lat_0", "0"))
        longitude_origin = float(parameters.get("lon_0", "0"))
        x_centers = reference.transform.c + (
            np.arange(reference.width, dtype=np.float64) + 0.5
        ) * reference.transform.a
        y_centers = reference.transform.f + (
            np.arange(reference.height, dtype=np.float64) + 0.5
        ) * reference.transform.e
        target_longitudes = np.rad2deg(x_centers / (radius * math.cos(lat_ts))) + longitude_origin
        target_latitudes = np.rad2deg(y_centers / radius) + latitude_origin
        latitude_indices = np.abs(latitudes[:, None] - target_latitudes[None, :]).argmin(axis=0)
        longitude_indices = np.abs(longitudes[:, None] - target_longitudes[None, :]).argmin(axis=0)
        clipped = annual[latitude_indices[:, None], longitude_indices[None, :]]
        dust_values = np.ma.filled(clipped, np.nan).astype(np.float32)
        valid = ~np.ma.getmaskarray(clipped) & np.isfinite(dust_values)
        if not valid.any() or np.all(dust_values[valid] == 0):
            raise ValueError(
                "The MY36 cdodtot field has no non-zero valid Arcadia values; "
                "dust rendering needs verification."
            )
        image_path = output_dir / "dust.png"
        minimum, maximum = write_values_overlay(
            dust_values,
            valid,
            image_path,
            PALETTE["dust"],
        )
        count = int(valid.sum())
        total = int(valid.size)
        longitude_bounds = (
            min(float(longitudes[0]), float(longitudes[-1])),
            max(float(longitudes[0]), float(longitudes[-1])),
        )
        if target_longitudes.min() < longitude_bounds[0] - 3 or target_longitudes.max() > longitude_bounds[1] + 3:
            raise ValueError("The Arcadia grid is outside the dust longitude coverage.")
        my_version = str(dataset.getncattr("version")) if "version" in dataset.ncattrs() else "unrecorded"
        sols = (
            int(dataset.variables["SOY"][0]),
            int(dataset.variables["SOY"][-1]),
        ) if "SOY" in dataset.variables else None
        solar_longitudes = np.asarray(dataset.variables["Ls"][:], dtype=np.float64) if "Ls" in dataset.variables else np.array([])
        solar_longitude_range = (
            [round(float(solar_longitudes.min()), 4), round(float(solar_longitudes.max()), 4)]
            if solar_longitudes.size
            else None
        )
        citation = str(dataset.getncattr("citation")) if "citation" in dataset.ncattrs() else ""
        license_terms = (
            str(dataset.getncattr("copyright"))
            if "copyright" in dataset.ncattrs()
            else "License needs verification."
        )

    return {
        "id": "dust",
        "label": "Atmospheric column dust optical depth",
        "image": image_path.name,
        "bounds_latlng": output_bounds,
        "width": grid["width"],
        "height": grid["height"],
        "min": minimum,
        "max": maximum,
        "units": "dimensionless optical depth",
        "coverage_percent": round(count / total * 100, 2),
        "valid_pixels": count,
        "total_pixels": total,
        "description": (
            "Atmospheric column dust optical depth, very coarse (3 deg cells). "
            "Not a surface hazard map. Averaged over MY36 daily maps."
        ),
        "badge": "Real data, coarse",
        "source": "lmd-dust",
        "variable": "cdodtot",
        "period": f"MY36, daily maps, SOY {sols[0]}-{sols[1]}" if sols else "MY36, daily maps",
        "solar_longitude_range_degrees": solar_longitude_range,
        "spatial_resolution_degrees": 3,
        "file_version": my_version,
        "citation": citation,
        "license": "CC BY-SA 3.0 Unported",
        "license_terms": license_terms,
        "source_url": "https://www-mars.lmd.jussieu.fr/mars/dust_climatology/dataset_v2/dustscenario_MY36_v2-5.nc",
        "methodology_doi": "10.1029/2019JE006111",
        "alternative_pds_doi_not_used": "10.17189/kwez-jq47",
        "legend_colors": PALETTE["dust"],
    }


def convert(input_dir: Path, output_dir: Path, dust_netcdf: Path | None = None) -> Path:
    grid_path = input_dir / "grid.json"
    if not grid_path.is_file():
        raise FileNotFoundError(f"Required grid metadata not found: {grid_path}")
    grid = json.loads(grid_path.read_text(encoding="utf-8"))
    geographic_crs = mars_geographic_crs(grid["grid_crs"])
    output_dir.mkdir(parents=True, exist_ok=True)

    layer_metadata = []
    output_bounds = None
    for filename, spec in LAYER_SPECS.items():
        source = input_dir / filename
        if not source.is_file():
            raise FileNotFoundError(f"Required source raster not found: {source}")
        destination = output_dir / f"{spec['id']}.png"
        with rasterio.open(source) as dataset:
            if (dataset.width, dataset.height) != (grid["width"], grid["height"]):
                raise ValueError(
                    f"{filename} grid dimensions do not match grid.json: "
                    f"{dataset.width}x{dataset.height}."
                )
        metadata = _write_overlay(
            source,
            destination,
            spec["id"],
            PALETTE[spec["id"]],
            geographic_crs,
        )
        metadata.update(
            {
                "label": spec["label"],
                "description": spec["description"],
                "source": spec["source"],
                "legend_colors": PALETTE[spec["id"]],
            }
        )
        if output_bounds is None:
            output_bounds = metadata["bounds_latlng"]
        layer_metadata.append(metadata)

    if dust_netcdf is not None:
        layer_metadata.append(
            _write_dust_overlay(
                dust_netcdf,
                input_dir / "elevation_m.tif",
                output_dir,
                grid,
                output_bounds,
            )
        )

    cave_path = input_dir / "cave_candidates.geojson"
    cave_count = grid.get("cave_candidate_count")
    if cave_path.is_file():
        cave_count = len(json.loads(cave_path.read_text(encoding="utf-8")).get("features", []))

    metadata_path = output_dir / "layers.json"
    metadata_path.write_text(
        json.dumps(
            {
                "region": grid["region"],
                "crs": grid["grid_crs"],
                "pixel_size_m": grid["pixel_size_m"],
                "bounds_lonlat": grid["bbox_lonlat_east_positive"],
                "bounds_latlng": layer_metadata[0]["bounds_latlng"],
                "cave_candidate_count": cave_count,
                "layers": layer_metadata,
            },
            indent=2,
        )
        + "\n",
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
        help="Directory containing grid.json and the aligned GeoTIFFs.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=repository_root / "frontend" / "public" / "layers",
        help="Directory for transparent PNG overlays and layers.json.",
    )
    parser.add_argument(
        "--dust-netcdf",
        type=Path,
        help="Optional LMD MY36 v2.5 dustscenario NetCDF file.",
    )
    arguments = parser.parse_args()
    result = convert(arguments.input_dir, arguments.output_dir, arguments.dust_netcdf)
    print(f"Wrote {result}")


if __name__ == "__main__":
    main()
