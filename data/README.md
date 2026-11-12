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

## Download manifest to complete

Keep source files out of version control if they are large. For each downloaded
product, record the actual product name/version, source URL, access date, native
projection, native pixel spacing, units, processing level, and any masking or
conversion performed. The source layers are required before producing the final
processed grid; no generated rasters are checked in yet.
