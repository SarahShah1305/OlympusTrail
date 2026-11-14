# Data sources and credits

The map uses the source data and interpretation notes in the
[project data handoff](https://github.com/SarahShah1305/OlympusTrail/blob/main/data/README.md).
Project raster PNGs are visual renderings of the aligned GeoTIFF values;
transparent pixels preserve source nodata.

- **Basemap and elevation:** NASA Mars Trek, MGS MOLA/MOLA64 merged global DEM.
  [Mars Trek](https://trek.nasa.gov/mars/),
  [product information](https://trek.nasa.gov/mars/jpl/config/textAbout.html),
  [Mars Trek WMTS catalog](https://trek.nasa.gov/tiles/apidoc/trekAPI.html?body=mars),
  [PDS Geosciences MOLA archive](https://pds-geosciences.wustl.edu/missions/mgs/mola.html).
- **Ice:** SWIM Combined Ice Consistency Map (0–1 m).
  [SWIM product page](https://swim.psi.edu/SWIM4MIMProducts.php).
  The index is not ice depth, a calibrated probability, or confirmation of a deposit.
- **Atmospheric dust:** LMD column dust optical-depth climatology, MY36 daily
  kriged maps, file `dustscenario_MY36_v2-5.nc` (NetCDF variable `cdodtot`,
  data version 2.5, MCS v5.2), averaged across sols 1–669. The dataset is on a
  3° × 3° grid and is licensed under CC BY-SA 3.0 Unported. The derived
  `dust.png` and its displayed values retain those share-alike terms. This is
  atmospheric column dust optical depth, not a surface hazard map.
  [LMD climatology and download](https://www-mars.lmd.jussieu.fr/mars/dust_climatology/),
  [MY36 v2.5 file](https://www-mars.lmd.jussieu.fr/mars/dust_climatology/dataset_v2/dustscenario_MY36_v2-5.nc),
  [methodology DOI 10.1029/2019JE006111](https://doi.org/10.1029/2019JE006111),
  [methodology DOI 10.1016/j.icarus.2014.12.034](https://doi.org/10.1016/j.icarus.2014.12.034).
  The alternate PDS TES bundle DOI
  [10.17189/kwez-jq47](https://doi.org/10.17189/kwez-jq47) was checked but
  was not used for this overlay.
- **Temperature:** THEMIS IR projected brightness temperature (PBT), three
  scenes from different dates.
  [THEMIS archive](https://themis-data.mars.asu.edu/),
  [NASA PDS](https://pds.nasa.gov/).
  Coverage is partial (about 5.7% of this grid); values are not a forecast.
- **Radiation reference:** Hassler et al. (2014), *Mars' Surface Radiation
  Environment Measured with the Mars Science Laboratory's Curiosity Rover*,
  *Science* 343, DOI
  [10.1126/science.1244797](https://doi.org/10.1126/science.1244797);
  [NASA NTRS record](https://ntrs.nasa.gov/citations/20180007641). The Gale
  value is context only, not a measurement for Arcadia. Confirm Arcadia values
  with Person 5.
- **Shelter candidates:** USGS Mars Global Cave Candidate Catalog, archived in
  [NASA PDS](https://pds.nasa.gov/).
  [USGS catalog](https://astrogeology.usgs.gov/search/map/mars_global_cave_candidate_catalog_v1_cushing).
  The supplied Arcadia subset contains zero candidates; orbital candidates
  would not constitute verified shelters.
- **Regional context:** NASA NTRS summary of Arcadia shallow-ice evidence and
  SWIM availability:
  [NASA NTRS paper](https://ntrs.nasa.gov/api/citations/20205008958/downloads/Morgan_etal_NA_Perspective_NATASTRON_19122833C%20.pdf).

Slope and aspect are derived from the shared MOLA grid. All GeoTIFFs are
resampled/aligned to a 3 km analysis grid; this does not increase native data
resolution or make the terrain rover-scale. Dust risk, radiation, and sunlight
do not have measured Arcadia layers: dust is a coarse atmospheric climatology,
sunlight is a relative terrain-derived index, and radiation is only a Gale
reference value. See the in-app Sources panel and
[data handoff](https://github.com/SarahShah1305/OlympusTrail/blob/main/data/README.md)
for per-layer caveats.
