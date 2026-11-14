# Arcadia 500 m grid (Person 1 data-gap fill)

This folder fills the gaps in the 3 km handoff. Person 2's files in
`data/processed/` are **unchanged**; this is a separate grid that the API
loads by default. Set `OLYMPUSTRAIL_DATASET=regional_3km` to switch back to
the original 3 km data.

| | 3 km handoff | This grid |
|---|---|---|
| Footprint | 40–52°N, 173–157°W | **40–58°N**, 173–157°W |
| Cell size | 3,000 m (238 × 220) | **500 m** (2134 × 1244) |
| Slope range | 0–10.6°, median 0.1° | 0–29.1°, median 0.27° |
| Temperature | one noon sample (262–275 K) | **00/06/12/18 h** (186–275 K) |
| Radiation | one constant (0.0279167 mSv/h) | **one uniform 0.0279167 mSv/h off-region Gale RAD reference** |
| Shelter / shielding | none | no verified shelters; geometric sky-obstruction layer and unverified obstruction candidates for display only |

## What each gap became

1. **Coarse terrain (3 km).** Re-gridded from MOLA MEGDR 128 px/deg
   (~463 m) to 500 m. Checked against Person 2's DEM by averaging back to
   3 km: correlation 0.9987, mean difference 0.02 m. Slope is computed with a
   per-row east–west cell-size correction, because the equirectangular grid
   is true-scale only at 49°N.
2. **Ice cut off at 52°N.** SWIM ice consistency stays high north of 52°N
   (cells > 0.9: 1.7 % in 46–52°N vs 5.9 % in 52–58°N), so the footprint was
   extended to 58°N. SWIM stops at 60°N. Re-gridded ice matches Person 2's
   layer at correlation 0.9997. SWIM is a ~3 km product; 500 m cells do not
   make it finer.
3. **Partial thermal observations.** Person 2's THEMIS PBT mosaic from the
   original 3 km atlas and 14 additional THEMIS scenes are regridded to 500 m
   with nearest-neighbour. They fill only cells that are still missing an
   observation. Coverage is 24.00% of the expanded grid (637,257 of 2,654,696 cells). The scenes have different observation dates and do not form a
   coherent temperature field. They are used only in `observations` mode and
   are never filled from the model. For routing, `scenario` mode uses
   MCD surface temperature at four local times, so temperature and the
   cold-heater energy actually change the route cost (06 h is 194–211 K,
   below the 230 K cold reference).
4. **Dust, radiation, and sunlight inputs.**
   * *Dust:* MCD monthly-mean optical depth is still almost uniform here
     (0.253–0.275). That is what the model says; it is not stretched.
   * *Radiation:* a uniform Gale RAD off-region reference of 0.67 mSv per 24
     Earth hours, or 0.0279167 mSv/h. See the [NASA Gale RAD report](https://www.nasa.gov/news-release/nasa-rover-results-include-first-age-measurement-on-mars-and-help-for-human-exploration/).
     This reference is not an Arcadia measurement and
     is not adjusted for local pressure or horizon geometry. There is no
     absorbed-Gy-to-Sv conversion or solar-particle-event model. Terrain sky
     obstruction does not change the radiation value or validate protection.
   * *Sunlight:* MCD flux per local time; the site score uses a 4-sample
     mean, normalised within the region (relative use only).
5. **Geometric sky obstruction, not shelter screening.**
   `sky_blocked_fraction.tif` measures how much of the sky surrounding terrain
   is hidden within 6 km (16 azimuths). `terrain_shelter_candidates.geojson`
   is retained for compatibility and display; its crater-wall/scarp points are
   unverified terrain-obstruction candidates, not caves or verified shelters.
   The downloaded USGS catalog contains 1,062 valid-coordinate records. Filtering the full expanded region returned zero listed candidates. Sources and checks are in `sources/caves/catalog_check.json`.

## Files

| File | Unit | Source |
|---|---|---|
| `elevation_m.tif` | m | MOLA MEGDR MEGT88N180HB + MEGT44N180HB |
| `slope_deg.tif`, `aspect_deg.tif` | degree | derived from elevation |
| `ice_consistency.tif` | 0–1 | SWIM Combined Ice Consistency 0–1 m |
| `thermal_observed_k.tif` | K | Original P2 mosaic plus 14 added historical THEMIS scenes (partial) |
| `thermal_observed_source_id.tif` | source index | 0 original; positive added scene; -1 unknown |
| `thermal_provenance.json` | � | source mapping, hashes and historical-atlas limitations |
| `cave_candidates.geojson` | � | empty full-region catalog subset; sources retained under `sources/caves/` |
| `temperature_ltHH_k.tif` | K | MCD v6.2, Ls 90, HH h local time |
| `sunlight_ltHH_w_m2.tif`, `sunlight_mean_w_m2.tif` | W/m² | MCD v6.2 |
| `dust_optical_depth.tif` | – | MCD v6.2 monthly mean |
| `pressure_pa.tif` | Pa | MCD v6.2 + DEM barometric correction |
| `radiation_msv_h.tif` | mSv/h | uniform Gale RAD off-region reference |
| `sky_blocked_fraction.tif` | 0–1 | geometric horizon scan of elevation; display only, not radiation shielding |
| `terrain_shelter_candidates.geojson` | – | local maxima of sky obstruction; unverified candidates only |
| `manifest.json` | – | ranges, coverage, SHA-256 of every input, MCD query URLs |
| `sources/` | – | raw MOLA crop (big-endian int16, 2816 × 2560, 60°N→38°N, 185°E→205°E, 1/128°) and MCD JSON export |

Rebuild with
`python scripts/prepare_person1_hires.py --swim path/to/SWIM4MIM_Ci_0_1.tif`
(the 71 MB SWIM GeoTIFF is not committed; download it from the SWIM page).

## Sources

* MOLA MEGDR 128 px/deg, PDS Geosciences Node:
  https://pds-geosciences.wustl.edu/mgs/mgs-m-mola-5-megdr-l3-v1/mgsl_300x/meg128/
* SWIM Combined Ice Consistency Map (0–1 m): https://swim.psi.edu/SWIM4MIMProducts.php
* Mars Climate Database v6.2 (LMD/OU/IAA/ESA/CNES), climatology average
  solar dust scenario: https://www-mars.lmd.jussieu.fr/mcd_python/ .
  Scientific use with credit; commercial use needs authorisation.
* NASA Planetary Data System: https://pds.nasa.gov/ (Gale RAD reference source).
* THEMIS IR PBT scenes I01710002, I01922032, I02546006 (via Person 2).

## Open items

* Walking speed, power and oxygen numbers are still placeholders until
  Person 5's parameter table arrives (`MissionParameters` in `models.py`).

The rebuild also runs `retain_person1_observations.py` and `update_person1_metadata.py` to preserve the added observations, cave check and radiation policy. These two scripts can be run on their own without the SWIM source.
