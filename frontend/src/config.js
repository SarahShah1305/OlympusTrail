export const AI_API_URL = 'http://localhost:8001'

export const config = {
  region: {
    name: 'Arcadia Planitia',
    marsRadiusMeters: 3396190,
    center: [46, -165],
    zoom: 4,
    minZoom: 3,
    maxZoom: 8,
    bounds: [
      [40, -173],
      [52, -157],
    ],
  },
  map: {
    crs: 'EPSG:4326',
    tileUrl:
      'https://trek.nasa.gov/tiles/Mars/EQ/Mars_MGS_MOLA_ClrShade_merge_global_463m/1.0.0/default/default028mm/{z}/{y}/{x}.jpg',
    attribution:
      '&copy; NASA/JPL/USGS — <a href="https://trek.nasa.gov/mars/" target="_blank" rel="noreferrer">Mars Trek</a>',
  },
}

export const layerDefinitions = [
  { id: 'elevation', label: 'Elevation' },
  { id: 'slope', label: 'Slope' },
  { id: 'aspect', label: 'Aspect' },
  { id: 'dust', label: 'Dust risk' },
  { id: 'ice', label: 'Ice' },
  { id: 'temperature', label: 'Temperature' },
  { id: 'sunlight', label: 'Sunlight' },
]

