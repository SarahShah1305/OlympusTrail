# MarsPath data layers — Arcadia Planitia

Person 2 data handoff. The map footprint is 40–52°N, 173–157°W (west-positive
longitude is negative), a manageable Arcadia Planitia window chosen for its
documented mid-latitude shallow subsurface ice. The output grid defaults to 1 km
pixels in a local Mars equirectangular projection. This is a harmonized analysis
grid, not a claim that every source resolves 1 km features.

## Source plan and interpretation

| Layer | Preferred source | Meaning and caveat |
|---|---|---|
| Elevation | NASA Mars Trek **MGS MOLA, Global DEM**; the global MOLA DEM is also distributed by USGS Astrogeology | Orbital altimetry terrain base. Mars Trek lets a user draw an AOI and download georeferenced products. Record the exact product metadata with the downloaded file. |
| Slope, aspect | Derived from the aligned elevation raster by `scripts/prepare_mars_layers.py` | Gradient-derived at the output grid spacing; slope in degrees, aspect clockwise from north. At 1 km it is regional-scale terrain, not rover-scale hazard mapping. |
| Ice prospectivity | NASA PDS Odyssey GRS/Neutron Spectrometer data or a published, GIS-ready NASA-funded subsurface-water-ice mapping product (SWIM) covering Arcadia | Neutron hydrogen is a proxy for near-surface hydrogen, not proof of mineable water ice at a specific point. Prefer the SWIM ice-consistency raster because it combines multiple independent ice-detection methods; cite its source paper and product version in the final dataset manifest. Do not relabel consistency as probability or ice abundance. |
| Thermal | NASA Mars Trek THEMIS-IR daytime/nighttime mosaics or NASA PDS THEMIS products | THEMIS brightness temperature is observation/time dependent. Use a clearly named day or night product, preserve Kelvin values, and note acquisition/season. Do not call a single mosaic a forecast or current weather. |
| Shelter candidates | NASA/USGS cave-candidate catalog if included in the selected region; otherwise leave the layer absent | Candidate features are not confirmed accessible shelters. Store source identifiers and coordinates in GeoJSON. Do not invent candidates to fill coverage. |

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

## Prepare aligned GeoTIFFs

Download the chosen source rasters with their metadata, then run:

```sh
python scripts/prepare_mars_layers.py \
  --dem path/to/mola_dem.tif \
  --ice path/to/arcadia_ice_consistency.tif \
  --thermal path/to/themis_temperature.tif \
  --out data/processed
```

Use `--shelters path/to/candidates.geojson` if there is a verified candidate
catalog for the footprint. `rasterio` and `numpy` are required. Outputs include
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
