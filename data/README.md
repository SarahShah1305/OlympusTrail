# MarsPath data layers — Arcadia Planitia

Person 2 data handoff. The map footprint is 40–52°N, 173–157°W (equivalent to
187–203°E), a manageable Arcadia Planitia window chosen for its
documented mid-latitude shallow subsurface ice. The output grid defaults to 1 km
pixels in a local Mars equirectangular projection. This is a harmonized analysis
grid, not a claim that every source resolves 1 km features.

## Recommended region

Keep Arcadia Planitia for the demo because published NASA material identifies
it as a low-latitude region with abundant shallow subsurface ice. The selected
footprint is a smaller subset within the published Arcadia ice-map coverage.

## Source plan and interpretation

| Layer | Preferred source | Meaning and caveat |
|---|---|---|
| Elevation | NASA Mars Trek **MGS MOLA, Global DEM**; the global MOLA DEM is also distributed by USGS Astrogeology | Orbital altimetry terrain base. Mars Trek lets a user draw an AOI and download georeferenced products. Record the exact product metadata with the downloaded file. |
| Slope, aspect | Derived from the aligned elevation raster by `scripts/prepare_mars_layers.py` | Gradient-derived at the output grid spacing; slope in degrees, aspect clockwise from north. At 1 km it is regional-scale terrain, not rover-scale hazard mapping. |
| Ice prospectivity | SWIM Combined Ice Consistency Map (0–1 m), GeoTIFF | SWIM combines neutron, thermal, geomorphology, and radar indicators. Native grid is 3 km. It indicates agreement with ice presence in the upper metre, not ice thickness, a probability, or a confirmed mineable deposit. |
| Thermal | THEMIS IR products from NASA Mars Trek or the ASU THEMIS archive | Prefer calibrated brightness-temperature values, preserve Kelvin units, and record day/night, season, local time, and product scaling. A colorized PNG is only a visual layer; do not interpret its colors as Kelvin. A single observation is not a forecast. |
| Shelter candidates | USGS Mars Global Cave Candidate Catalog | These are candidate entrances derived from orbiter observations, not confirmed accessible or safe shelters. Clip to the project footprint; if there are no candidates in Arcadia, report zero rather than inventing points. |

NASA Mars Trek is the recommended practical download route for elevation and
THEMIS products: https://trek.nasa.gov/mars/ . Its product metadata and download
workflow are documented at https://trek.nasa.gov/mars/jpl/config/textAbout.html
and its tile/product catalog at https://trek.nasa.gov/tiles/apidoc/trekAPI.html?body=mars .
The MOLA archive is described by the PDS Geosciences Node at
https://pds-geosciences.wustl.edu/missions/mgs/mola.html . Odyssey neutron data
are catalogued at https://pds-geosciences.wustl.edu/missions/odyssey/grs.html .
The peer-reviewed Arcadia shallow-ice evidence and SWIM product availability are
summarized in NASA NTRS at
https://ntrs.nasa.gov/api/citations/20205008958/downloads/Morgan_etal_NA_Perspective_NATASTRON_19122833C%20.pdf .

## Download and prepare, step by step

1. **Download elevation.** Open [NASA Mars Trek](https://trek.nasa.gov/mars/)
   and search for **MGS MOLA, Global DEM**. Select the numeric elevation DEM,
   not a colorized elevation or shaded-relief image. Add it to the map, use
   Mars Trek's download/area-of-interest tool for 173–157°W and 40–52°N, and
   export a georeferenced raster with its metadata. If the Trek export is
   unavailable, download the MOLA DEM from [USGS Astrogeology](https://astrogeology.usgs.gov/search/map/mars_global_surveyor_mola_globe)
   and clip the same bounds in QGIS.
2. **Derive slope and aspect.** In QGIS open the DEM, then use *Processing
   Toolbox → GDAL → Raster terrain analysis → Slope* and save degrees. Run
   *Aspect* on the same DEM and save degrees clockwise from north (0° north,
   90° east, 180° south, 270° west). Save as `slope_deg.tif` and
   `aspect_deg.tif`. Never derive these from a shaded-relief picture. The Python
   script below can derive both from the aligned DEM instead.
3. **Download ice.** On the [SWIM product page](https://swim.psi.edu/SWIM4MIMProducts.php),
   select **Combined Ice Consistency Map (0–1 m)** and download its **GeoTIFF**.
   The page documents simple cylindrical projection, 3,000 m pixels, longitude
   0–360°E, latitude −60 to 60°, and nodata value −30. The NASA PDS archives
   the mission data behind the product; SWIM provides the ready-to-use combined
   science map. Retain the consistency values and explain their meaning.
4. **Download thermal.** In Mars Trek search for **THEMIS IR** and download a
   daytime or nighttime raster for the same region. If offered, choose calibrated
   brightness-temperature data and retain units/scaling. You can also search the
   [THEMIS Image Explorer](https://themis-data.mars.asu.edu/) for calibrated,
   map-projected products. If you only find an RGB/PNG browse mosaic, use it as
   a visual layer and cite it that way; do not convert its colors into
   temperatures. Record day/night and the observation's season/local time.
5. **Get cave candidates.** Download the [USGS Mars Global Cave Candidate Catalog](https://astrogeology.usgs.gov/search/map/mars_global_cave_candidate_catalog_v1_cushing)
   ZIP. Open the table or shapefile in QGIS. If it is a table with coordinates,
   use *Add Delimited Text Layer* to make points. Filter points to 173–157°W and
   40–52°N, then export selected points as GeoJSON. These are candidate
   entrances, not verified shelters. An empty Arcadia subset is a valid result.
6. **Align and export.** Put the downloaded DEM, SWIM GeoTIFF, and numerical
   thermal raster together. In a terminal at the project folder, create an
   isolated Python environment and install the listed packages:

   ```sh
   python3 -m venv .venv
   source .venv/bin/activate
   python -m pip install -r requirements.txt
   ```

   Then run the script below. It outputs a shared 1 km grid and derives
   slope/aspect; it can also clip cave point candidates from GeoJSON. Resampling
   the 3 km ice grid to 1 km does not add ice detail, so preserve the native
   source resolution in the layer metadata.

## Prepare aligned GeoTIFFs

Download the chosen source rasters with their metadata, then run:

```sh
python scripts/prepare_mars_layers.py \
  --dem path/to/mola_dem.tif \
  --ice path/to/arcadia_ice_consistency.tif \
  --thermal path/to/themis_temperature.tif \
  --out data/processed
```

Add `--shelters path/to/arcadia_cave_candidates.geojson` to clip candidate
points to the region. Outputs include
`elevation_m.tif`, `slope_deg.tif`, `aspect_deg.tif`, and whichever optional
source layers were supplied, plus `grid.json`. All rasters share one extent,
CRS, transform, dimensions, and nodata convention. Continuous rasters use
bilinear resampling; discrete data use nearest-neighbor. The script deliberately
does not synthesize missing ice, temperature, or shelter observations.

## Arcadia processing handoff (2026-11-13)

The supplied files were processed into `data/processed/` on a shared 3 km grid.
Three kilometres preserves the effective spacing of the SWIM input; the finer
MOLA and THEMIS measurements are resampled to that grid and do not make the ice
layer finer. `grid.json` records the shared CRS, footprint, source raster
metadata, and input filenames.

| Output | Result | Interpretation / limitation |
|---|---|---|
| `elevation_m.tif` | MOLA elevations, −4,763 to −3,354 m in this footprint | MOLA-derived elevation, metres; global MOLA source cropped/reprojected to Arcadia. |
| `slope_deg.tif` | Derived slope, 0.0002–10.56° | Gradient from aligned MOLA elevation at 3 km spacing; regional terrain only. |
| `aspect_deg.tif` | Derived aspect, 0–360° | Downhill bearing clockwise from north. Flat-cell bearings are mathematically unstable and should not be interpreted. |
| `ice_consistency.tif` | SWIM consistency index, approximately 0.29–0.98 in valid footprint | SWIM Combined Ice Consistency Map (0–1 m); consistency indicator, not ice depth or a calibrated probability. |
| `thermal_brightness_temperature_k.tif` | THEMIS PBT I01710002, I01922032, I02546006, Kelvin; valid over about 5.7% of the grid | Three observations fill some additional areas, but most of the region remains nodata. No values are interpolated into the gaps. This is not a region-wide thermal layer. |
| `cave_candidates.geojson` | 0 candidates | The supplied USGS/PDS catalog has no candidate points in this Arcadia window. Do not display this as confirmed shelter coverage. |

### Sources and processing

- **Elevation:** NASA Mars Trek `mola128_mola64_merge_90Nto90S_SimpleC_clon0.tif`, global MOLA/MOLA64 merged DEM. Source has 46,081 × 23,041 pixels and approximately 1/128° cell spacing. The source file is global (2 GB); it remains outside the repository. NASA Mars Trek: <https://trek.nasa.gov/mars/>; PDS Geosciences MOLA archive: <https://pds-geosciences.wustl.edu/missions/mgs/mola.html>.
- **Ice:** SWIM `SWIM4MIM_Ci_0_1.tif`, 7,200 × 2,400 cells, about 2,964 m native pixel spacing, nodata −30. NASA-sponsored SWIM product: <https://swim.psi.edu/SWIM4MIMProducts.php>. Source mosaic is global in longitude and spans ±60° latitude; it covers this region.
- **Thermal:** THEMIS IR PBT `I01710002PBT.IMG`, `I01922032PBT.IMG`, and `I02546006PBT.IMG`. They are projected brightness temperatures from 2002-05-04, 2002-05-21, and 2002-07-12. The first two are 100 m floating-point PDS images; the third is a legacy unsigned-byte PDS image with 100 m map scale. For the legacy product, its embedded label's `OFFSET=177.285`, `SCALING_FACTOR=0.027486`, sinusoidal center longitude 198°E, and line/sample projection offsets were applied to recover Kelvin and georeference it. All three labels specify `NULL_CONSTANT=0`; zero pixels were masked. The resulting mosaic prioritizes earlier files and fills only nodata gaps, without averaging observations taken at different times. PBT is projected brightness temperature, not a complete regional climatology. NASA PDS product archive: <https://pds.nasa.gov/>; THEMIS archive: <https://themis-data.mars.asu.edu/>.
- **Cave candidates:** Mars Global Cave Candidate Catalog, PDS product `urn:nasa:pds:mars_mro.odyssey_multi_cavecatalog_cushing_2016`. Filtered `Mars_Cave_Catalog_shapefile.csv`, converting 0–360°E longitudes to signed longitude before clipping. The primary `Mars_Cave_Catalog.csv` supplied alongside it has inconsistent header/row field order, so the companion CSV with explicit longitude/latitude columns was used. These are image-derived candidate entrances, not verified shelters. Catalog landing page: <https://astrogeology.usgs.gov/search/map/mars_global_cave_candidate_catalog_v1_cushing>.

The shared analysis window is 40–52°N, 173–157°W. Continuous layers were bilinearly reprojected; the cave points were spatially filtered. THEMIS source null value 0 and the floating-point nodata sentinel were masked according to the PDS labels/GDAL metadata. Slope and aspect were derived from the MOLA output. The script is reproducible with:

```sh
python scripts/prepare_mars_layers.py \
  --dem /path/to/mola128_mola64_merge_90Nto90S_SimpleC_clon0.tif \
  --ice /path/to/SWIM4MIM_Ci_0_1.tif \
  --thermal /path/to/I01710002PBT.IMG \
  --thermal /path/to/I01922032PBT.IMG \
  --thermal /path/to/I02546006PBT.IMG \
  --shelters /path/to/Mars_Cave_Catalog_shapefile.csv \
  --out data/processed --pixel-m 3000
```

### Download status and required handoff

The elevation, slope, aspect, ice, and cave-catalog work is complete from the
files supplied. Three numerical THEMIS PBT scenes were processed, but **the
regional thermal layer is incomplete**: only about 5.7% of the 3 km Arcadia
grid has a PBT value. The requested controlled-mosaic GeoTIFF
`THEMIS_NightIR_ControlledMosaic_Diacria_30N180E_100mpp.tif` was not downloaded.
The available `download-2` file is only its small PDS label, the `.txt` files
are source-image lists, and the `.jpg` files are browse previews; none contains
the mosaic's numeric raster pixels. Do not use the preview JPEGs as calibrated
temperatures. This failed/absent raster is the specific missing data item.

**Person 1 handoff:** use the provided `thermal_brightness_temperature_k.tif`
as a partial layer and handle its nodata mask in the Terrain Cost Grid. Do not
assign fabricated thermal values to the remaining cells. If the route/site
scoring requires region-wide thermal coverage, obtain more THEMIS PBT scenes or
the controlled-mosaic GeoTIFF and rerun the preparation script before treating
thermal risk as spatially complete. The 3-scene PBT mosaic combines different
observation dates/local times and is not a forecast.

The cave-candidate catalog was successfully filtered and contains zero points
inside this Arcadia window. Report shelter candidates as unavailable here; do
not infer shelter coverage from the empty GeoJSON. Dust, radiation, and sunlight
were not in Person 2's downloaded inputs and remain for the other assigned
layers/roles to supply.
