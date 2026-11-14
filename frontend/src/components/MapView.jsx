import { useEffect, useState } from 'react'
import {
  CircleMarker,
  ImageOverlay,
  MapContainer,
  Marker,
  Polyline,
  Popup,
  ScaleControl,
  TileLayer,
  useMap,
  useMapEvents,
} from 'react-leaflet'
import L from 'leaflet'
import { config } from '../config'

const marsCrs = Object.create(L.CRS.EPSG4326)
marsCrs.code = 'IAU2000:104905'
marsCrs.distance = (first, second) => {
  const radians = (degrees) => (degrees * Math.PI) / 180
  const lat1 = radians(first.lat)
  const lat2 = radians(second.lat)
  const deltaLat = lat2 - lat1
  const deltaLng = radians(second.lng - first.lng)
  const haversine =
    Math.sin(deltaLat / 2) ** 2 +
    Math.cos(lat1) * Math.cos(lat2) * Math.sin(deltaLng / 2) ** 2
  return 2 * config.region.marsRadiusMeters * Math.asin(Math.sqrt(haversine))
}

function MapClickHandler({ enabled, onMapClick }) {
  useMapEvents({
    click(event) {
      if (enabled) onMapClick(event.latlng)
    },
  })
  return null
}

function SiteFocus({ site }) {
  const map = useMap()
  useEffect(() => {
    if (site) map.flyTo([site.lat, site.lng], Math.max(map.getZoom(), 6), { duration: 0.5 })
  }, [map, site])
  return null
}

function GridBounds({ bounds }) {
  const map = useMap()
  useEffect(() => {
    map.setMaxBounds(bounds)
    map.fitBounds(bounds, { animate: false })
  }, [bounds, map])
  return null
}

function RouteFocus({ path }) {
  const map = useMap()
  useEffect(() => {
    if (path?.length > 1) map.fitBounds(path, { padding: [24, 24] })
  }, [map, path])
  return null
}

function makeMarkerIcon(label, kind, rank) {
  return L.divIcon({
    className: 'map-marker-icon',
    html: `<span class="map-marker map-marker--${kind} ${rank === 1 ? 'map-marker--top' : ''}">${label}</span>`,
    iconSize: [kind === 'site' && rank === 1 ? 38 : 32, kind === 'site' && rank === 1 ? 38 : 32],
    iconAnchor: [16, 16],
  })
}

function DraggableEndpoint({ point, label, onDrag }) {
  if (!point) return null
  return (
    <Marker
      position={[point.lat, point.lng]}
      icon={makeMarkerIcon(label, 'endpoint')}
      draggable
      eventHandlers={{
        dragend(event) {
          const position = event.target.getLatLng()
          onDrag({ lat: position.lat, lng: position.lng })
        },
      }}
    >
      <Popup>{label === 'A' ? 'Start point' : 'Goal point'} · drag to adjust</Popup>
    </Marker>
  )
}

function LayerLegend({ layers, activeLayers }) {
  const active = layers.filter((layer) => activeLayers[layer.id])
  if (!active.length) return null
  return (
    <div className="map-layer-legends" aria-label="Active layer legends">
      {active.map((layer) => (
        <div className="map-layer-legend" key={layer.id}>
          <strong>{layer.label}</strong>
          <span>{layer.min.toLocaleString(undefined, { maximumFractionDigits: 2 })}–{layer.max.toLocaleString(undefined, { maximumFractionDigits: 2 })} {layer.units}</span>
          <span
            className="legend-ramp"
            style={{ background: `linear-gradient(90deg, ${layer.legend_colors.join(', ')})` }}
            aria-hidden="true"
          />
          {layer.id === 'temperature' && (
            <span className="temperature-coverage">
              <span><i style={{ width: `${layer.coverage_percent}%` }} /></span>
              <small>{layer.coverage_percent.toFixed(1)}% of map has data</small>
            </span>
          )}
        </div>
      ))}
    </div>
  )
}

export default function MapView({
  mode,
  sites,
  activeLayers,
  start,
  goal,
  onMapClick,
  onStartChange,
  onGoalChange,
  route,
  askRoutePath,
  selectedSite,
  layerMetadata,
  overlayOpacity,
}) {
  const [tileError, setTileError] = useState(false)
  const [imageError, setImageError] = useState('')
  const layerList = layerMetadata?.layers || []
  const regionBounds = layerMetadata?.bounds_latlng || config.region.bounds
  const routePositions = route?.path || []
  const alternative = route?.alternative_path || []

  return (
    <section className="map-column" aria-label="Mars map">
      <div className="map-canvas">
        <MapContainer
          center={config.region.center}
          zoom={config.region.zoom}
          minZoom={config.region.minZoom}
          maxZoom={config.region.maxZoom}
          maxBounds={regionBounds}
          maxBoundsViscosity={0.75}
          crs={marsCrs}
          scrollWheelZoom
          zoomControl
          className="leaflet-map"
        >
          <GridBounds bounds={regionBounds} />
          <RouteFocus path={askRoutePath} />
          {!tileError && (
            <TileLayer
              url={config.map.tileUrl}
              attribution={config.map.attribution}
              eventHandlers={{
                tileerror: () => setTileError(true),
              }}
            />
          )}
          {layerList
            .filter((layer) => activeLayers[layer.id])
            .map((layer) => (
              <ImageOverlay
                key={layer.id}
                url={`${import.meta.env.BASE_URL}layers/${layer.image}`}
                bounds={layer.bounds_latlng}
                opacity={overlayOpacity}
                alt={`${layer.label} source raster overlay`}
                eventHandlers={{
                  error: () => setImageError(layer.label),
                }}
              />
            ))}
          <MapClickHandler enabled={mode === 'route'} onMapClick={onMapClick} />
          <SiteFocus site={selectedSite} />
          {mode === 'sites' &&
            sites.map((site) => (
              <Marker
                key={site.id}
                position={[site.lat, site.lng]}
                icon={makeMarkerIcon(site.rank, 'site', site.rank)}
                title={`Rank ${site.rank}: ${site.name}`}
                alt={`Rank ${site.rank}, ${site.name}`}
              >
                <Popup>
                  <div className="site-popup">
                    <span className="eyebrow">Preview · rank {site.rank} · score {site.score}/100</span>
                    <strong>{site.name}</strong>
                    <ul>{site.reasons.map((reason) => <li key={reason}>{reason}</li>)}</ul>
                  </div>
                </Popup>
              </Marker>
            ))}
          <DraggableEndpoint point={start} label="A" onDrag={onStartChange} />
          <DraggableEndpoint point={goal} label="B" onDrag={onGoalChange} />
          {alternative.length > 1 && (
            <Polyline
              positions={alternative}
              pathOptions={{ color: '#F4EDE0', opacity: 1, weight: 7, dashArray: '5 9' }}
            />
          )}
          {routePositions.length > 1 && (
            <>
              <Polyline positions={routePositions} pathOptions={{ color: '#14213D', opacity: 1, weight: 11 }} />
              <Polyline
                positions={routePositions}
                pathOptions={{ className: 'planned-route-line', color: '#FF4F45', opacity: 1, weight: 7 }}
              />
            </>
          )}
          {route?.abort_points?.map((point) => (
            <CircleMarker
              key={`abort-${point.lat}-${point.lng}`}
              center={[point.lat, point.lng]}
              radius={6}
              pathOptions={{ color: '#14213D', weight: 2, fillColor: '#FF6B5B', fillOpacity: 1 }}
            >
              <Popup>{point.label}</Popup>
            </CircleMarker>
          ))}
          <ScaleControl position="bottomleft" imperial={false} />
        </MapContainer>
        <div className="map-caption">
          <span>{config.region.name}</span>
          <span className="map-status"><i /> {tileError ? 'Navy fallback' : 'Live tiles'}</span>
          <a
            className="map-credit"
            href="https://trek.nasa.gov/mars/"
            target="_blank"
            rel="noreferrer"
          >
            NASA Mars Trek
          </a>
        </div>
        {mode === 'route' && (
          <div className="map-hint" role="status">
            {!start ? 'Click the map to set start A' : !goal ? 'Click again to set goal B' : 'Drag A or B to adjust points'}
          </div>
        )}
        {imageError && (
          <div className="map-data-error" role="alert">
            {imageError} overlay did not load. Check the generated layer files.
            <button type="button" onClick={() => setImageError('')}>Dismiss</button>
          </div>
        )}
        <LayerLegend layers={layerList} activeLayers={activeLayers} />
      </div>
    </section>
  )
}
