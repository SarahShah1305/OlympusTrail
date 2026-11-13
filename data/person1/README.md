# Person 1 scenario layers

These files add full-grid **scenario context** for Arcadia Planitia. They do not turn the existing partial observations into complete measurements.

## What's in this folder

`manifest.json` records provenance, units, ranges, coverage, and caveats. Four rasters are interpolated Mars Climate Database (MCD) v6.2 outputs for one selected scenario: solar longitude `Ls=90°` (northern summer), fixed local solar time `12:00`, altitude `0 m`, and the MCD **climatology average solar** dust scenario.

| Raster | Meaning | Unit | Interpretation |
|---|---|---|---|
| `temperature_model_k.tif` | MCD surface temperature | K | Model output for the selected season and local noon |
| `dust_model_optical_depth.tif` | Monthly mean dust column visible optical depth above surface | dimensionless | Atmospheric dust proxy; not storm probability or surface dust depth |
| `sunlight_model_w_m2.tif` | Incident solar flux on a horizontal surface | W/m² | Instantaneous scenario value; not annual solar availability or slope-adjusted illumination |
| `surface_pressure_model_pa.tif` | MCD surface pressure | Pa | Model output for the selected scenario |
| `radiation_reference_msv_h.tif` | Uniform reference derived from a Gale measurement | mSv/h | Assumption only; not an Arcadia observation, radiation map, or shielding estimate |

The MCD service describes a sampled model database that linearly interpolates requested locations and times. Its output is an interpolated climate-model scenario, not a forecast or a set of direct measurements. The nominal 3 km output grid is inherited from the terrain grid: resampling does not make the MCD climate inputs 3 km measurements. The layers cover the current output grid, but **regional measurements are incomplete**. MCD cautions that its stored grid may not capture the model's full resolution or variability, and that interpolation can smooth extrema. [MCD v6.2 web interface](https://www-mars.lmd.jussieu.fr/mcd_python/) · [MCD access notes and cautions](https://www-mars.lmd.jussieu.fr/mars/access.html)

### Radiation reference

The constant value is `0.67 mSv per 24 hours`, converted to `0.0279167 mSv/h` and repeated in every cell. NASA reports this as Curiosity's average surface dose at Gale Crater from August 2012 to June 2013. It is used here only as a reference scale. It is not measured at Arcadia, spatially modeled for Arcadia, adjusted for solar storms or time, or modified for terrain, caves, habitat construction, or shielding. [NASA's report of the Gale RAD measurement](https://www.nasa.gov/news-release/nasa-rover-results-include-first-age-measurement-on-mars-and-help-for-human-exploration/)

### Keep observation layers separate

The original THEMIS PBT brightness-temperature layer remains a separate observation layer with **5.6761% valid-cell coverage** (2,972 of 52,360 cells). Do not fill its nodata cells with the MCD temperature scenario, average the two, or describe the resulting area as measured. The cave inventory has **zero candidates in this region**; no shelter or cave locations are inferred by these scenario layers.

USGS describes the controlled THEMIS mosaics as blended 8-bit qualitative products and advises against quantitative analysis with them. They are useful as basemaps and for visual context, but their pixel values are not a calibrated Kelvin temperature layer. Quantitative THEMIS work should use the individual controlled science images. [USGS THEMIS controlled mosaic documentation](https://stac.astrogeology.usgs.gov/docs/data/mars/themis_controlled_mosaics/)

## Grid and geometry check

All five rasters in this folder were inspected against `data/processed/elevation_m.tif`. Each has the same `238 × 220` shape, Mars equirectangular CRS, 3,000 m pixel size, affine transform, and bounds as the DEM. The MCD layers therefore align cell-for-cell with the current reference grid. This confirms geometry only; it does not increase source resolution or establish measurement accuracy.

## Reproduce the layers

Run from the repository root with the project virtual environment. The checked-in source exports are in `data/person1/sources/`, so the script can be rerun without a new MCD web request:

```powershell
.\.venv\Scripts\python.exe scripts\prepare_person1_layers.py
```

The script reads `data/person1/sources/mcd62_ls90_noon.txt` and `data/person1/sources/mcd62_longitude_axis.txt`, interpolates onto the existing DEM grid, writes the four MCD scenario rasters and the uniform radiation reference, and refreshes `manifest.json`. The source export hashes and query URLs are recorded in that manifest.

## Source and use terms

The MCD export identifies itself as “MCD_v6.2 with climatology average solar scenario” and provides the selected variables and units. See the [MCD web interface](https://www-mars.lmd.jussieu.fr/mcd_python/) and its [access and copyright terms](https://www-mars.lmd.jussieu.fr/mars/access.html). The MCD provider allows scientific use when the source is correctly credited and asks users to inform the providers of usage and developments; **commercial use requires specific authorization**. Cite the Mars Climate Database v6.2 and its underlying model/provider when reusing these outputs.
