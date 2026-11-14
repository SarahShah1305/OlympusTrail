# OlympusTrail front end

The map is centered on Arcadia Planitia (40–52°N, 173–157°W). It loads the
aligned 3 km Mars rasters as transparent image overlays. Elevation, slope,
aspect, ice and partial THEMIS temperature are rendered from the supplied
GeoTIFFs. Dust uses the LMD MY36 daily kriged climatology. Sunlight is a
documented relative-illumination derivation. Radiation is shown as a Gale
reference only; no Arcadia radiation raster is displayed. The shelter
candidate file contains zero candidates in this region.

The Mars Trek MOLA shaded-relief WMTS is the basemap; if its tiles fail, the
map remains on a plain navy background. Available overlay opacity is
adjustable. Site rankings, route planning and chat currently use preview data;
these are not real route or site measurements.

## Run locally

From `frontend\`:

```powershell
npm install
npm install leaflet react-leaflet
npm run dev
```

Production checks:

```powershell
npm run lint
npm run build
```

## Rebuild real overlays

The conversion scripts do not alter `data\`. They read the Person 2 handoff
from `data\processed\` and write generated PNGs and `layers.json` to
`frontend\public\layers\`.

Create a local environment at the repository root and install the conversion
dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install numpy rasterio pillow netCDF4
```

The dust source is the LMD daily kriged column-dust NetCDF,
`dustscenario_MY36_v2-5.nc` (file version `2-5`, product version 2.5; 669 daily
maps spanning MY36 sols 1–669). Download it from
<https://www-mars.lmd.jussieu.fr/mars/dust_climatology/dataset_v2/dustscenario_MY36_v2-5.nc>
to a local path outside `data\`, then run:

```powershell
.\.venv\Scripts\python.exe scripts_frontend\convert_layers.py `
  --input-dir data\processed `
  --output-dir frontend\public\layers `
  --dust-netcdf C:\path\to\dustscenario_MY36_v2-5.nc
.\.venv\Scripts\python.exe scripts_frontend\derive_sunlight.py `
  --input-dir data\processed `
  --output-dir frontend\public\layers
```

`convert_layers.py` writes Elevation, Slope, Aspect, Ice, Temperature and, when
given the NetCDF file, Dust overlays. Nodata is alpha-transparent. Dust is the
mean of valid daily MY36 maps, a very coarse 3° × 3° atmospheric column value,
not a surface hazard map. The LMD page specifies CC BY-SA 3.0 terms; retain the
attribution in [CREDITS.md](../CREDITS.md) and share-alike terms for
redistribution of that derivative. The alternative PDS TES bundle DOI
<https://doi.org/10.17189/kwez-jq47> was checked as an alternative source; it
was not used for the map overlay.

`derive_sunlight.py` combines MOLA slope/aspect with each grid-row latitude. Its
assumption is local solar noon at equinox (solar declination 0°, Sun due south
in this northern-hemisphere region);
it computes a clipped direct-beam cosine-incidence index and ignores
atmosphere, dust, shadows and seasonal/daylight duration. It is not energy or
daily sunlight duration. Radiation is only the cited MSL RAD Gale reference
(about 0.21 mGy/day GCR at -4.4 km); check Person 5's Arcadia radiation values.

## Preview API and connecting the team APIs

By default the front end uses labeled preview sites/routes/chat and a short
response delay. Configure the API in `frontend\.env.local`:

```dotenv
VITE_USE_MOCK=false
VITE_API_URL=http://localhost:8000
```

Assumed JSON contracts in `src\api\client.js`:

- `GET /sites` → `{ "sites": [{ "id", "rank", "name", "lat", "lng", "score", "reasons": [] }] }`
- `POST /route` request → `{ "start": {"lat", "lng"}, "goal": {"lat", "lng"}, "oxygen_hours": 4, "avoid": [] }`
- `POST /route` response → `{ "status", "path": [[lat, lng]], "distance_km", "duration_h", "oxygen_used_h", "oxygen_total_h", "battery_used_pct", "abort_points": [], "shelters": [], "hazards": [], "message" }`
- `POST /chat` request → `{ "message", "context" }`; response → `{ "reply", "route"? }`

If a real API request fails, the client warns and returns labeled preview values.
Confirm exact request/response field names with Persons 1 and 4 before switching
to the live API.

See the in-app **Sources and caveats** section and the project
[credits](../CREDITS.md) for source URLs and interpretation limits.
