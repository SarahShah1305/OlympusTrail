"""Build the Person 1 500 m Arcadia grid (40-58N, 173-157W) from raw sources.

Fills the data gaps left by the 3 km handoff without touching Person 2's
files in data/processed/:

* finer terrain: MOLA MEGDR 128 px/deg (~463 m) instead of 3 km cells;
* northern extension 52-58N, because SWIM ice consistency stays high there;
* climate scenarios at 00/06/12/18 h local time (MCD v6.2, Ls 90), so the
  route cost reacts to time of day instead of a single warm noon sample;
* a uniform Gale RAD dose-equivalent reference, explicitly extrapolated;
* a terrain sky-obstruction proxy and unverified terrain candidates. These are
  crater walls/scarps that block part of the sky, NOT caves or lava tubes.

Inputs (see data/person1/arcadia_500m/README.md for where each came from):

  python scripts/prepare_person1_hires.py --swim path/to/SWIM4MIM_Ci_0_1.tif

The MOLA crop and MCD export are kept in data/person1/arcadia_500m/sources/
and used by default; only the 71 MB SWIM GeoTIFF has to be supplied.

THEMIS brightness temperatures are re-gridded from Person 2's
data/processed/thermal_brightness_temperature_k.tif (nearest neighbour); the
raw scenes were not re-downloaded.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
import sys
from pathlib import Path

import numpy as np
import rasterio
from rasterio.crs import CRS
from rasterio.enums import Resampling
from rasterio.transform import from_origin
from rasterio.warp import reproject, transform as project
from scipy.interpolate import RegularGridInterpolator
from scipy.ndimage import gaussian_filter, maximum_filter

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/person1/arcadia_500m"

R_MARS = 3396190.0
LON_W, LON_E, LAT_S, LAT_N = -173.0, -157.0, 40.0, 58.0
LAT_TS, LON_0 = 49.0, -165.0
PIXEL_M = 500.0
GEOG = CRS.from_string(f"+proj=longlat +a={R_MARS} +b={R_MARS} +no_defs")
GRID_CRS = CRS.from_string(f"+proj=eqc +lat_ts={LAT_TS} +lat_0=0 +lon_0={LON_0} "
                           f"+a={R_MARS} +b={R_MARS} +units=m +no_defs")

# MOLA crop written by the browser fetch: big-endian int16, 2816 x 2560,
# rows from 60N southward, columns from 185E eastward, 1/128 degree cells.
MOLA_SHAPE = (2816, 2560)
MOLA_ORIGIN = (185.0 - 360.0, 60.0)
MOLA_RES = 1 / 128

RAD_REFERENCE_MSV_DAY = 0.67  # NASA-reported Gale dose equivalent per Earth day
SCALE_HEIGHT_M = 11100.0     # Mars atmospheric scale height (NASA fact sheet)
LOCAL_TIMES = (0, 6, 12, 18)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def target_grid():
    x0 = math.radians(LON_W - LON_0) * R_MARS * math.cos(math.radians(LAT_TS))
    x1 = math.radians(LON_E - LON_0) * R_MARS * math.cos(math.radians(LAT_TS))
    y0 = math.radians(LAT_S) * R_MARS
    y1 = math.radians(LAT_N) * R_MARS
    width = int(round((x1 - x0) / PIXEL_M))
    height = int(round((y1 - y0) / PIXEL_M))
    return from_origin(x0, y1, PIXEL_M, PIXEL_M), width, height


def cell_lonlat(transform, shape):
    rows, cols = np.indices(shape)
    xs = transform.c + (cols + 0.5) * transform.a
    ys = transform.f + (rows + 0.5) * transform.e
    lon, lat = project(GRID_CRS, GEOG, xs.ravel(), ys.ravel())
    return np.asarray(lon).reshape(shape), np.asarray(lat).reshape(shape)


def warp_array(src, src_transform, src_crs, dst_transform, shape, resampling, src_nodata=None):
    out = np.full(shape, np.nan, dtype="float32")
    reproject(source=src, destination=out, src_transform=src_transform, src_crs=src_crs,
              src_nodata=src_nodata, dst_transform=dst_transform, dst_crs=GRID_CRS,
              dst_nodata=np.nan, resampling=resampling)
    return out


def load_mola(path: Path):
    raw = np.fromfile(path, dtype=">i2")
    if raw.size != MOLA_SHAPE[0] * MOLA_SHAPE[1]:
        raise ValueError(f"MOLA crop has {raw.size} samples, expected {MOLA_SHAPE}")
    dem = raw.reshape(MOLA_SHAPE).astype("float32")
    tr = from_origin(MOLA_ORIGIN[0], MOLA_ORIGIN[1], MOLA_RES, MOLA_RES)
    return dem, tr


def slope_aspect(dem, lat):
    """Slope (deg) and downhill aspect (deg clockwise from north).

    The equirectangular grid has true scale only at LAT_TS, so the east-west
    cell size is corrected per row before differencing.
    """
    dx = PIXEL_M * np.cos(np.radians(lat)) / math.cos(math.radians(LAT_TS))
    dzdrow, dzdcol = np.gradient(dem.astype("float64"))
    dz_east = dzdcol / dx
    dz_north = -dzdrow / PIXEL_M
    slope = np.degrees(np.arctan(np.hypot(dz_east, dz_north)))
    aspect = (np.degrees(np.arctan2(-dz_east, -dz_north)) + 360.0) % 360.0
    return slope.astype("float32"), aspect.astype("float32")


def sky_blocked_fraction(dem, lat, max_dist_m=6000.0, azimuths=16):
    """Fraction of the upper sky hidden by surrounding terrain.

    For each azimuth the maximum horizon elevation angle h within max_dist_m
    is found. The upper-hemisphere geometry is described by mean(sin(h)).
    This solid-angle proxy is not
    a calibrated attenuation of particle radiation or dose.
    """
    dem = dem.astype("float64")
    rows, cols = dem.shape
    dx = PIXEL_M * np.cos(np.radians(lat)) / math.cos(math.radians(LAT_TS))
    total = np.zeros_like(dem)
    steps = int(max_dist_m // PIXEL_M)
    for k in range(azimuths):
        az = 2 * math.pi * k / azimuths
        best = np.zeros_like(dem)
        for s in range(1, steps + 1):
            dist = s * PIXEL_M
            east, north = dist * math.sin(az), dist * math.cos(az)
            dr = int(round(-north / PIXEL_M))
            # column offset varies with latitude; use the region-centre value
            dc = int(round(east / (PIXEL_M * math.cos(math.radians(lat.mean())) /
                                   math.cos(math.radians(LAT_TS)))))
            if dr == 0 and dc == 0:
                continue
            shifted = np.full_like(dem, np.nan)
            r0, r1 = max(0, -dr), min(rows, rows - dr)
            c0, c1 = max(0, -dc), min(cols, cols - dc)
            shifted[r0:r1, c0:c1] = dem[r0 + dr:r1 + dr, c0 + dc:c1 + dc]
            true_dist = np.hypot(dr * PIXEL_M, dc * dx)
            angle = np.arctan2(shifted - dem, true_dist)
            best = np.fmax(best, np.nan_to_num(angle, nan=0.0))
        total += np.sin(np.clip(best, 0, math.pi / 2))
    return (total / azimuths).astype("float32")


def mcd_layers(path: Path, lon, lat):
    """Interpolate the MCD exports onto the grid.

    The 2D export prints longitudes rounded to integers; the samples are an
    even linspace between the requested bounds. The rounded labels are
    checked against that axis before use.
    """
    doc = json.loads(path.read_text())
    lo, hi = doc["lon_bounds"]
    la0, la1 = doc["lat_bounds"]
    names = {
        "Surface temperature (K)": "temperature",
        "Monthly mean dust column visible optical depth above surface": "dust",
        "Incident solar flux on horizontal surface (W/m2)": "sunlight",
        "Surface pressure (Pa)": "pressure",
    }
    lon_e = np.where(lon < 0, lon + 360.0, lon)
    out, provenance = {}, {}
    for lt in LOCAL_TIMES:
        export = doc["exports"][str(lt)]
        if f"Local time {float(lt)}h" not in export["header"]:
            raise ValueError(f"MCD export for {lt}h has unexpected header")
        provenance[str(lt)] = dict(query=export["query"], txt=export["txt"])
        for label, key in names.items():
            table = export["vars"][label]
            values = np.asarray(table["v"], dtype="float64")
            lons = np.linspace(lo, hi, values.shape[0])
            lats = np.linspace(table["lats"][0], table["lats"][1], table["lats"][2])
            labels = np.asarray(table["lonlabels"], dtype=float)
            if np.max(np.abs(np.trunc(lons) - labels)) > 1.0 or values.shape[1] != len(lats):
                raise ValueError("MCD longitude/latitude axes do not match the export labels")
            if not (lats[0] <= la0 + 1e-6 and lats[-1] >= la1 - 1e-6):
                raise ValueError("MCD export does not cover requested latitudes")
            f = RegularGridInterpolator((lons, lats), values)
            out[(key, lt)] = f(np.stack([lon_e.ravel(), lat.ravel()], -1)).reshape(lon.shape).astype("float32")
    return out, provenance, doc.get("retrieved")


def write(name, array, transform, description, unit):
    path = OUT / f"{name}.tif"
    profile = dict(driver="GTiff", height=array.shape[0], width=array.shape[1], count=1,
                   dtype="float32", crs=GRID_CRS, transform=transform, nodata=np.nan,
                   compress="deflate", predictor=3, zlevel=9, tiled=True,
                   blockxsize=256, blockysize=256)
    with rasterio.open(path, "w", **profile) as dst:
        dst.write(array.astype("float32"), 1)
        dst.set_band_description(1, description)
        dst.update_tags(1, unit=unit)
    finite = np.isfinite(array)
    return dict(file=path.name, unit=unit, description=description,
                coverage=float(finite.mean()),
                minimum=float(np.nanmin(array)) if finite.any() else None,
                maximum=float(np.nanmax(array)) if finite.any() else None)


def shelter_points(blocked, lon, lat, slope, threshold, limit=50):
    peaks = (blocked == maximum_filter(blocked, size=9)) & (blocked >= threshold)
    idx = np.argwhere(peaks)
    order = np.argsort(-blocked[peaks])[:limit]
    features = []
    for r, c in idx[order]:
        features.append(dict(type="Feature", geometry=dict(type="Point", coordinates=[
            round(float(lon[r, c]), 5), round(float(lat[r, c]), 5)]), properties=dict(
            row=int(r), col=int(c), sky_blocked_fraction=round(float(blocked[r, c]), 4),
            slope_deg=round(float(slope[r, c]), 2), kind="unverified_terrain_obstruction_candidate",
            verified_shelter=False, radiation_protection_validated=False,
            note="DEM obstruction maximum; shelter, accessibility and radiation protection are unverified.")))
    return dict(type="FeatureCollection", features=features)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sources = OUT / "sources"
    ap.add_argument("--mola", type=Path, default=sources / "mola_megdr128_38-60N_185-205E.be_int16.bin")
    ap.add_argument("--swim", type=Path, required=True, help="SWIM4MIM_Ci_0_1.tif (71 MB, not in the repo)")
    ap.add_argument("--mcd", type=Path, default=sources / "mcd62_ls90_lt00-06-12-18.json")
    ap.add_argument("--thermal", type=Path, default=ROOT / "data/processed/thermal_brightness_temperature_k.tif")
    ap.add_argument("--shelter-threshold", type=float, default=0.02)
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)

    transform, width, height = target_grid()
    shape = (height, width)
    lon, lat = cell_lonlat(transform, shape)
    layers = {}

    mola, mola_tr = load_mola(args.mola)
    dem = warp_array(mola, mola_tr, GEOG, transform, shape, Resampling.bilinear)
    slope, aspect = slope_aspect(dem, lat)
    layers["elevation_m"] = write("elevation_m", dem, transform, "MOLA MEGDR 128 px/deg median topography above areoid", "m")
    layers["slope_deg"] = write("slope_deg", slope, transform, "Slope from 500 m MOLA grid, latitude-corrected", "degree")
    layers["aspect_deg"] = write("aspect_deg", aspect, transform, "Downhill bearing clockwise from north", "degree")

    with rasterio.open(args.swim) as src:
        ice = warp_array(src.read(1), src.transform, src.crs, transform, shape, Resampling.bilinear, src.nodata)
    layers["ice_consistency"] = write("ice_consistency", ice, transform,
                                      "SWIM Combined Ice Consistency 0-1 m (native ~3 km)", "1")

    with rasterio.open(args.thermal) as src:
        thermal = warp_array(src.read(1, masked=True).filled(np.nan), src.transform, src.crs,
                             transform, shape, Resampling.nearest, np.nan)
    layers["thermal_observed_k"] = write("thermal_observed_k", thermal, transform,
                                         "THEMIS PBT brightness temperature (Person 2 mosaic, nearest)", "K")

    mcd, mcd_provenance, retrieved = mcd_layers(args.mcd, lon, lat)
    for lt in LOCAL_TIMES:
        layers[f"temperature_lt{lt:02d}_k"] = write(
            f"temperature_lt{lt:02d}_k", mcd[("temperature", lt)], transform,
            f"MCD v6.2 surface temperature, Ls 90, {lt:02d}h local", "K")
        layers[f"sunlight_lt{lt:02d}_w_m2"] = write(
            f"sunlight_lt{lt:02d}_w_m2", mcd[("sunlight", lt)], transform,
            f"MCD v6.2 incident solar flux on horizontal surface, Ls 90, {lt:02d}h local", "W/m2")
    dust = np.mean([mcd[("dust", lt)] for lt in LOCAL_TIMES], axis=0)
    layers["dust_optical_depth"] = write("dust_optical_depth", dust, transform,
                                         "MCD v6.2 monthly-mean dust column optical depth, Ls 90", "1")
    sun_mean = np.mean([mcd[("sunlight", lt)] for lt in LOCAL_TIMES], axis=0)
    layers["sunlight_mean_w_m2"] = write("sunlight_mean_w_m2", sun_mean, transform,
                                         "Mean of 4 local-time MCD solar flux samples (relative use only)", "W/m2")

    # Pressure: MCD values refer to its coarse model topography. Adjust to the
    # 500 m DEM with a barometric correction relative to a heavily smoothed
    # DEM standing in for the model's terrain.
    ps_mcd = np.mean([mcd[("pressure", lt)] for lt in LOCAL_TIMES], axis=0)
    dem_smooth = gaussian_filter(np.nan_to_num(dem, nan=float(np.nanmean(dem))), sigma=200, mode="nearest")
    pressure = ps_mcd * np.exp(-(dem - dem_smooth) / SCALE_HEIGHT_M)
    layers["pressure_pa"] = write("pressure_pa", pressure, transform,
                                  "Diurnal-mean MCD surface pressure, adjusted to 500 m DEM", "Pa")

    blocked = sky_blocked_fraction(dem, lat)
    layers["sky_blocked_fraction"] = write("sky_blocked_fraction", blocked, transform,
                                           "DEM horizon obstruction of upper hemisphere within 6 km; geometry proxy only", "1")

    # Neither Gale coefficients nor blocked sky establish Arcadia attenuation.
    radiation = np.full(shape, RAD_REFERENCE_MSV_DAY / 24.0, dtype="float32")
    layers["radiation_msv_h"] = write("radiation_msv_h", radiation, transform,
                                      "Uniform Gale RAD reference extrapolated for demo; no shielding correction", "mSv/h")

    shelters = shelter_points(blocked, lon, lat, slope, args.shelter_threshold)
    (OUT / "terrain_shelter_candidates.geojson").write_text(json.dumps(shelters, indent=1))

    manifest = dict(
        schema_version=2, region="Arcadia Planitia (extended north)",
        bounds_lonlat=[LON_W, LAT_S, LON_E, LAT_N], crs=GRID_CRS.to_string(),
        transform=list(transform)[:6], width=width, height=height, pixel_m=PIXEL_M,
        layers=layers, local_times_h=list(LOCAL_TIMES),
        shelters=dict(file="terrain_shelter_candidates.geojson", count=len(shelters["features"]),
                      threshold_sky_blocked=args.shelter_threshold,
                      kind="unverified_terrain_obstruction_candidate"),
        caves=dict(count_40_52N=0, checked_52_58N=False,
                   note="Person 2's catalog filter found 0 MGC3 candidates in 40-52N. "
                        "52-58N has not been checked against the catalog yet."),
        sources=dict(
            mola=dict(file=args.mola.name, sha256=sha256(args.mola),
                      products=["MEGT88N180HB.IMG rows 3584-5631", "MEGT44N180HB.IMG rows 0-767"],
                      columns="640-3199 (185-205E)",
                      url="https://pds-geosciences.wustl.edu/mgs/mgs-m-mola-5-megdr-l3-v1/mgsl_300x/meg128/"),
            swim=dict(file=args.swim.name, sha256=sha256(args.swim),
                      url="https://swim.psi.edu/SWIM4MIMProducts.php"),
            mcd=dict(file=args.mcd.name, sha256=sha256(args.mcd), retrieved=retrieved,
                     scenario="MCD v6.2, climatology average solar dust, Ls 90, altitude 0 m",
                     exports=mcd_provenance, url="https://www-mars.lmd.jussieu.fr/mcd_python/"),
            thermal=dict(file=str(args.thermal.relative_to(ROOT)) if args.thermal.is_relative_to(ROOT) else args.thermal.name,
                         note="Person 2's 3 km THEMIS PBT mosaic, nearest-neighbour regrid"),
            radiation=dict(model="Uniform 0.67 mSv per 24 Earth hours / 24; off-region reference assumption",
                           spatial_measurements_available=False, shielding_correction_applied=False,
                           citation="https://www.nasa.gov/news-release/nasa-rover-results-include-first-age-measurement-on-mars-and-help-for-human-exploration/"),
        ),
    )
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=1))
    # Carry retained observations/catalog checks across rebuilds, then apply
    # the same radiation/data policy as the adopted checked-in dataset.
    subprocess.run([sys.executable, str(ROOT/"scripts/retain_person1_observations.py")], check=True)
    subprocess.run([sys.executable, str(ROOT/"scripts/update_person1_metadata.py")], check=True)
    print(json.dumps({k: (v["minimum"], v["maximum"], round(v["coverage"], 4)) for k, v in layers.items()}, indent=1))
    print("shape", shape, "shelters", len(shelters["features"]))


if __name__ == "__main__":
    main()
