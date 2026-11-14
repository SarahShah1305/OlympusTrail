"""Apply the adopted radiation policy and refresh retained-data disclosures.

Only Person 1 outputs are written. May be rerun after rebuilding the 500 m
dataset or adding historical observations; no network access is required.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import rasterio

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / "data/person1/arcadia_500m"
NASA_REFERENCE = "https://www.nasa.gov/news-release/nasa-rover-results-include-first-age-measurement-on-mars-and-help-for-human-exploration/"


def refresh():
    manifest_path = FOLDER / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    path = FOLDER / "radiation_msv_h.tif"
    with rasterio.open(path) as src:
        profile, shape = src.profile.copy(), src.shape
    reference = np.full(shape, 0.67/24, dtype="float32")
    with rasterio.open(path, "w", **profile) as dst:
        dst.write(reference, 1)
        dst.set_band_description(1, "Uniform Gale dose-equivalent reference extrapolated to Arcadia for demo")
        dst.update_tags(1, UNIT="mSv/h", DATA_CLASS="off_region_reference_assumption",
                        SOURCE=NASA_REFERENCE, OBSERVATION_SITE="Gale crater, 2012-2013",
                        RATE_CONVENTION="0.67 mSv per 24 Earth hours",
                        TERRAIN_ATTENUATION_APPLIED="false", PRESSURE_ADJUSTMENT_APPLIED="false")
    manifest["layers"]["radiation_msv_h"].update(
        coverage=1.0, minimum=float(reference.min()), maximum=float(reference.max()),
        description="Uniform Gale RAD reference; off-region assumption without pressure or terrain attenuation",
        data_class="off_region_reference_assumption")
    manifest["sources"]["radiation"] = dict(
        model="Uniform 0.67 mSv per 24 Earth hours / 24",
        citation=NASA_REFERENCE, observation_site="Gale crater, August 2012-June 2013",
        rate_convention="Reference interpreted per 24 Earth hours for planner time units",
        arcadia_measurement=False, shielding_correction_applied=False,
        pressure_correction_applied=False, absorbed_dose_conversion_applied=False,
        caveat="Reference scenario only; no regional calibration, particle transport or solar storm model")
    with rasterio.open(FOLDER/"sky_blocked_fraction.tif", "r+") as dst:
        dst.set_band_description(1, "DEM upper-hemisphere horizon obstruction; geometry proxy only")
        dst.update_tags(1, DATA_CLASS="dem_geometry_proxy", UNIT="1",
                        RADIATION_PROTECTION_VALIDATED="false")
    manifest["layers"]["sky_blocked_fraction"].update(
        description="DEM horizon obstruction within 6 km; no validated radiation attenuation",
        data_class="dem_geometry_proxy")
    candidate_path = FOLDER / manifest["shelters"]["file"]
    candidates = json.loads(candidate_path.read_text())
    for feature in candidates["features"]:
        feature["properties"].update(
            kind="unverified_terrain_obstruction_candidate", verified_shelter=False,
            radiation_protection_validated=False,
            note="DEM obstruction maximum; shelter, accessibility and radiation protection are unverified.")
    candidate_path.write_text(json.dumps(candidates,indent=2)+"\n")
    manifest["shelters"].update(kind="unverified_terrain_obstruction_candidate",
                               verified_shelter_count=0, radiation_protection_validated=False)
    with rasterio.open(FOLDER/"thermal_observed_k.tif") as src:
        measured = src.read(1,masked=True).filled(np.nan)
    finite = np.isfinite(measured)
    manifest["layers"]["thermal_observed_k"].update(
        coverage=float(finite.mean()), minimum=float(measured[finite].min()),
        maximum=float(measured[finite].max()),
        description="Historical THEMIS atlas: original P2 observations plus retained calibrated samples; nearest regrid")
    provenance_path = FOLDER/"thermal_provenance.json"
    if provenance_path.exists():
        manifest["thermal_retention"] = json.loads(provenance_path.read_text())
    cave_check = FOLDER/"sources/caves/catalog_check.json"
    if cave_check.exists():
        check = json.loads(cave_check.read_text())
        manifest["caves"] = check
    manifest.update(scenario_layers_ready=True, regional_measurements_complete=False,
                    validated_radiation_shielding_available=False)
    manifest["caveats"] = [
        "Scenario layers provide complete numerical coverage using climate models and reference assumptions.",
        "Thermal observations are historical, partial, and acquired at different dates/local times; no model fill is applied.",
        "Regridding observations from 3 km to 500 m does not add measurement detail.",
        "Pressure downscaling uses a smoothed DEM as an illustrative coarse-terrain proxy; it is not a validated local pressure field.",
        "DEM sky obstruction is excluded from radiation dose and site shielding scores.",
        "Terrain candidates are unverified; no safe shelter or radiation protection is established."]
    manifest_path.write_text(json.dumps(manifest,indent=2)+"\n")
    print(json.dumps(dict(radiation_msv_h=float(reference[0,0]),
                         thermal_coverage_percent=100*float(finite.mean()))))


if __name__ == "__main__":
    refresh()
