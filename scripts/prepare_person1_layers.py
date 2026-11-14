"""Add traceable scenario layers without changing Person 2's data handoff.

The MCD web export is model output, not an observation or a forecast.
Run from the repository root; downloads use Windows curl because it works in
the desktop sandbox where Python's network stack may be restricted.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path
from urllib.parse import urlencode, urljoin

import numpy as np
import rasterio
from rasterio.transform import xy
from rasterio.warp import transform

ROOT = Path(__file__).resolve().parents[1]
BASE = "https://www-mars.lmd.jussieu.fr/mcd_python/"
PARAMS = dict(var1="tsurf", var2="dod", var3="fluxsurf_dn_sw", var4="ps",
              datekeyhtml="1", ls="90", localtime="12", latitude="39 53",
              longitude="186 204", altitude="0", zkey="3", isfixedlt="on",
              dust="1", hrkey="0", averaging="off", zonmean="off", diumean="off",
              animation="off", dpi="80", islog="off", colorm="jet", proj="cyl",
              iswind="off", betatest="on")
VARIABLES = [
    ("temperature_model_k", "Surface temperature (K)", "K"),
    ("dust_model_optical_depth", "Monthly mean dust column visible optical depth above surface", "1"),
    ("sunlight_model_w_m2", "Incident solar flux on horizontal surface (W/m2)", "W/m2"),
    ("surface_pressure_model_pa", "Surface pressure (Pa)", "Pa"),
]


def download(url: str, path: Path) -> None:
    subprocess.run(["curl.exe", "-fsSL", "--connect-timeout", "15", "--max-time",
                    "120", url, "-o", str(path)], check=True)


def export(params: dict, target: Path) -> str:
    query = BASE + "cgi-bin/mcdcgi.py?" + urlencode(params)
    response = target.with_suffix(".response.html")
    download(query, response)
    match = re.search(r"href=['\"]([^'\"]+\.txt)['\"]", response.read_text())
    if not match:
        raise ValueError("MCD did not return a numeric ASCII export; inspect response")
    data_url = urljoin(BASE + "cgi-bin/", match.group(1))
    download(data_url, target)
    return query


def parse_export(path: Path, longitude_path: Path):
    """Recover precise longitude coordinates from a companion 1D export.

    The 2D service prints row longitudes as truncated integers. A companion
    transect provides the actual 64 longitude sample coordinates; retaining
    that export avoids guessing georeferencing from the rounded row labels.
    """
    text = path.read_text(encoding="utf-8")
    expected = "MCD_v6.2 with climatology average solar scenario."
    if expected not in text or "Ls 90.0deg." not in text or "Local time 12.0h (fixed at all longitudes)" not in text:
        raise ValueError("Unexpected MCD version, scenario, season, or local time")
    axis_lines = [line for line in longitude_path.read_text().splitlines()
                  if line.strip() and not line.startswith("#")]
    axis_data = np.loadtxt(axis_lines, ndmin=2)
    lons = axis_data[:, 0]
    if len(lons) < 2 or not np.all(np.diff(lons) > 0):
        raise ValueError("Invalid longitude axis")
    if not np.allclose(lons[[0, -1]], [186, 204]):
        raise ValueError("Longitude export does not match requested bounds")
    sections = re.split(r"(?=### MCD_v)", text)[1:]
    if len(sections) != len(VARIABLES):
        raise ValueError("Expected four MCD data tables")
    tables = []
    latitude_axis = None
    for section, (_, description, _) in zip(sections, VARIABLES):
        if "### Columns 2+ are " + description not in section:
            raise ValueError("MCD variable labels/order do not match the request")
        lines = section.splitlines()
        header = next(line for line in lines if line.startswith("---- ||"))
        lats = np.fromstring(header.split("||", 1)[1], sep=" ")
        rows = [line for line in lines if re.match(r"^[+-]\d+\s*\|\|", line)]
        row_labels = np.array([float(line.split("||")[0]) for line in rows])
        if len(rows) != len(lons) or not np.array_equal(row_labels, np.trunc(lons)):
            raise ValueError("2D export and companion longitude axis disagree")
        values = np.array([np.fromstring(line.split("||", 1)[1], sep=" ") for line in rows]).T
        if values.shape != (len(lats), len(lons)) or not np.all(np.isfinite(values)):
            raise ValueError("Invalid MCD array shape or missing values")
        if latitude_axis is not None and not np.array_equal(latitude_axis, lats):
            raise ValueError("MCD variable grids differ")
        latitude_axis = lats
        tables.append(values)
    return lons, latitude_axis, tables


def interpolate(lons, lats, values, query_lon, query_lat):
    if (np.any(query_lon < lons[0]) or np.any(query_lon > lons[-1]) or
            np.any(query_lat < lats[0]) or np.any(query_lat > lats[-1])):
        raise ValueError("Destination grid extends beyond downloaded data")
    ix = np.clip(np.searchsorted(lons, query_lon) - 1, 0, len(lons) - 2)
    iy = np.clip(np.searchsorted(lats, query_lat) - 1, 0, len(lats) - 2)
    fx = (query_lon - lons[ix]) / (lons[ix + 1] - lons[ix])
    fy = (query_lat - lats[iy]) / (lats[iy + 1] - lats[iy])
    return ((1-fx)*(1-fy)*values[iy, ix] + fx*(1-fy)*values[iy, ix+1] +
            (1-fx)*fy*values[iy+1, ix] + fx*fy*values[iy+1, ix+1]).astype("float32")


def prepare(out: Path, table_path: Path, longitude_path: Path, source_urls: dict):
    out.mkdir(parents=True, exist_ok=True)
    lons, lats, tables = parse_export(table_path, longitude_path)
    with rasterio.open(ROOT / "data/processed/elevation_m.tif") as reference:
        profile = reference.profile.copy()
        rows, cols = np.indices(reference.shape)
        xs, ys = xy(reference.transform, rows.ravel(), cols.ravel())
        geographic = "+proj=longlat +a=3396190 +b=3396190 +no_defs"
        lon, lat = transform(reference.crs, geographic, xs, ys)
        query_lon = np.array(lon).reshape(reference.shape) % 360
        query_lat = np.array(lat).reshape(reference.shape)
        profile.update(dtype="float32", count=1, nodata=np.nan,
                       compress="deflate", predictor=3, tiled=True)
    layers = {}
    entries = list(zip(VARIABLES, tables))
    for (name, description, unit), table in entries:
        values = interpolate(lons, lats, table, query_lon, query_lat)
        if np.any(values < 0) or (name.startswith("temperature") and np.any(values < 100)):
            raise ValueError(f"Unexpected values in {name}")
        path = out / (name + ".tif")
        with rasterio.open(path, "w", **profile) as dst:
            dst.write(values, 1)
            dst.set_band_description(1, description)
            dst.update_tags(1, UNIT=unit, DATA_CLASS="climate_model",
                            MCD_VERSION="6.2", LS_DEG="90", LOCAL_SOLAR_TIME_H="12")
        layers[name] = dict(file=path.name, unit=unit, data_class="climate_model",
                            coverage=float(np.isfinite(values).mean()),
                            minimum=float(values.min()), maximum=float(values.max()))
    # An explicit uniform reference, not a regional measurement or shielding map.
    radiation = np.full(query_lat.shape, 0.67 / 24.0, dtype="float32")
    path = out / "radiation_reference_msv_h.tif"
    with rasterio.open(path, "w", **profile) as dst:
        dst.write(radiation, 1)
        dst.set_band_description(1, "Uniform Gale RAD reference extrapolated for demo")
        dst.update_tags(1, UNIT="mSv/h", DATA_CLASS="reference_assumption",
                        OBSERVATION_SITE="Gale crater; not Arcadia", RATE_MSV_EARTH_DAY="0.67")
    layers["radiation_reference_msv_h"] = dict(
        file=path.name, unit="mSv/h", data_class="reference_assumption", coverage=1.0,
        minimum=float(radiation.min()), maximum=float(radiation.max()),
        caveat="Uniform extrapolation from Gale RAD 2012-2013; no Arcadia spatial or storm model")
    manifest = dict(
        schema_version=1, region="Arcadia Planitia", reference_grid="../processed/grid.json",
        scenario=dict(id="mcd62_ls90_noon", season_ls_deg=90, local_solar_time_h=12,
                      dust="climatology average solar", high_resolution_topography=False),
        scenario_layers_ready=True, regional_measurements_complete=False,
        layers=layers,
        provenance=dict(source_urls=source_urls,
                        ascii_sha256=hashlib.sha256(table_path.read_bytes()).hexdigest(),
                        longitude_sha256=hashlib.sha256(longitude_path.read_bytes()).hexdigest(),
                        sampled_grid=dict(longitude_samples=len(lons), latitude_samples=len(lats)),
                        coordinate_method="Companion 1D longitude coordinates; 2D latitude header; bilinear interpolation"),
        citations=[
            "https://www-mars.lmd.jussieu.fr/mcd_python/",
            "https://www-mars.lmd.jussieu.fr/mars/info_web/index.html",
            "https://www-mars.lmd.jussieu.fr/mars/access.html",
            "https://www.nasa.gov/news-release/nasa-rover-results-include-first-age-measurement-on-mars-and-help-for-human-exploration/",
            "https://stac.astrogeology.usgs.gov/docs/data/mars/themis_controlled_mosaics/"],
        caveats=[
            "MCD is an interpolated climate model; this sample is northern summer at local noon, not a forecast.",
            "3 km output alignment does not create 3 km climate measurements.",
            "Existing THEMIS PBT remains a separate partial observation layer, not blended with this scenario.",
            "Sunlight is horizontal-surface instantaneous model flux, not annual solar availability.",
            "Dust optical depth is an atmospheric proxy, not dust-storm probability or terrain trafficability.",
            "Radiation is a uniform reference assumption; no measured Arcadia radiation or shielding map is supplied.",
            "Cave catalog contains zero candidates in the region; no shelter locations are invented.",
            "MCD source terms allow scientific use; commercial use needs provider authorization."],
    )
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(dict(scenario=manifest["scenario"], layers=layers), indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ROOT / "data/person1")
    parser.add_argument("--ascii", type=Path)
    parser.add_argument("--longitude-ascii", type=Path)
    args = parser.parse_args()
    sources = args.out / "sources"
    sources.mkdir(parents=True, exist_ok=True)
    table = sources / "mcd62_ls90_noon.txt"
    longitude = sources / "mcd62_longitude_axis.txt"
    urls = {}
    if args.ascii:
        table.write_bytes(args.ascii.read_bytes())
        urls["table_query"] = BASE + "cgi-bin/mcdcgi.py?" + urlencode(PARAMS)
    elif not table.exists():
        urls["table_query"] = export(PARAMS, table)
    coordinate_params = dict(PARAMS, latitude="46", var2="none", var3="none", var4="none")
    if args.longitude_ascii:
        longitude.write_bytes(args.longitude_ascii.read_bytes())
        urls["longitude_query"] = BASE + "cgi-bin/mcdcgi.py?" + urlencode(coordinate_params)
    elif not longitude.exists():
        urls["longitude_query"] = export(coordinate_params, longitude)
    urls.setdefault("table_query", BASE + "cgi-bin/mcdcgi.py?" + urlencode(PARAMS))
    urls.setdefault("longitude_query", BASE + "cgi-bin/mcdcgi.py?" + urlencode(coordinate_params))
    prepare(args.out, table, longitude, urls)


if __name__ == "__main__":
    main()
