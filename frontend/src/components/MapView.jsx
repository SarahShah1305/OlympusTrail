import { useEffect, useState } from 'react'
import {
  CircleMarker,
  Rectangle,
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
    if (site && map.getSize().x > 0 && map.getSize().y > 0)
      map.flyTo([site.lat, site.lng], Math.max(map.getZoom(), 6), {
        duration: 0.5,
      })
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

function MapResize({ site, path }) {
  const map = useMap()
  useEffect(() => {
    const observer = new ResizeObserver(() => {
      if (!map.getContainer().clientWidth || !map.getContainer().clientHeight)
        return
      map.invalidateSize()
      if (path?.length > 1)
        map.fitBounds(path, { padding: [24, 24], animate: false })
      else if (site)
        map.setView([site.lat, site.lng], Math.max(map.getZoom(), 6), {
          animate: false,
        })
    })
    observer.observe(map.getContainer())
    return () => observer.disconnect()
  }, [map, site, path])
  return null
}

function RouteFocus({ path }) {
  const map = useMap()
  useEffect(() => {
    if (path?.length > 1 && map.getSize().x > 0 && map.getSize().y > 0)
      map.fitBounds(path, { padding: [24, 24] })
  }, [map, path])
  return null
}

function makeMarkerIcon(label, kind, rank) {
  return L.divIcon({
    className: 'map-marker-icon',
    html: `<span class="map-marker map-marker--${kind} ${rank === 1 ? 'map-marker--top' : ''}">${label}</span>`,
    iconSize: [
      kind === 'site' && rank === 1 ? 38 : 32,
      kind === 'site' && rank === 1 ? 38 : 32,
    ],
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
      <Popup>
        {label === 'A' ? 'Start point' : 'Goal point'} · drag to adjust
      </Popup>
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
          {layer.id === 'ice' && (
            <span>Weaker → stronger ice evidence (not probability)</span>
          )}
          <span>3 km display grid; resampling does not add detail.</span>
          <span>
            {layer.min.toLocaleString(undefined, { maximumFractionDigits: 2 })}–
            {layer.max.toLocaleString(undefined, { maximumFractionDigits: 2 })}{' '}
            {layer.units}
          </span>
          <span
            className="legend-ramp"
            style={{
              background: `linear-gradient(90deg, ${layer.legend_colors.join(', ')})`,
            }}
            aria-hidden="true"
          />
          {layer.id === 'temperature' && (
            <span className="temperature-coverage">
              <span>
                <i style={{ width: `${layer.coverage_percent}%` }} />
              </span>
              <small>
                {layer.coverage_percent.toFixed(1)}% of map has data
              </small>
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
  onSelectSite,
  onUseSite,
  sourceMode,
  editPoint,
  selectedSite,
  layerMetadata,
  overlayOpacity,
}) {
  const [tileError, setTileError] = useState(false)
  const [imageError, setImageError] = useState('')
  const layerList = layerMetadata?.layers || []
  const regionBounds = config.region.bounds
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
          <MapResize site={selectedSite} path={askRoutePath} />
          <GridBounds bounds={regionBounds} />
          {layerMetadata?.bounds_latlng && (
            <Rectangle
              bounds={layerMetadata.bounds_latlng}
              pathOptions={{
                color: '#f4ede0',
                weight: 2,
                dashArray: '6 6',
                fill: false,
              }}
            >
              <Popup>
                Historical overlay coverage: 40–52°N. Planner coverage extends
                to 58°N. Blank temperature cells mean no observation.
              </Popup>
            </Rectangle>
          )}
          <RouteFocus path={askRoutePath} />
          {
            <TileLayer
              url={config.map.tileUrl}
              maxNativeZoom={6}
              attribution={config.map.attribution}
              eventHandlers={{
                tileerror: () => setTileError(true),
                tileload: () => setTileError(false),
              }}
            />
          }
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
                eventHandlers={{ click: () => onSelectSite?.(site) }}
              >
                <Popup>
                  <div className="site-popup">
                    <span className="eyebrow">
                      {sourceMode === 'demo' ? 'Example' : 'Model ranking'} ·
                      rank {site.rank} · relative score {site.score}/100
                    </span>
                    <strong>{site.name}</strong>
                    <ul>
                      {site.reasons.map((reason) => (
                        <li key={reason}>{reason}</li>
                      ))}
                    </ul>
                    <button
                      type="button"
                      className="site-use-button"
                      onClick={() => onUseSite?.(site)}
                    >
                      Use as starting base
                    </button>
                  </div>
                </Popup>
              </Marker>
            ))}
          {!goal && route?.status === 'ok' && route.route?.destination && (
            <Marker
              position={[
                route.route.destination.lat,
                route.route.destination.lon > 180
                  ? route.route.destination.lon - 360
                  : route.route.destination.lon,
              ]}
              icon={makeMarkerIcon('B', 'endpoint')}
            >
              <Popup>
                Ice evidence destination B. Return follows the same path to A.
              </Popup>
            </Marker>
          )}
          <DraggableEndpoint point={start} label="A" onDrag={onStartChange} />
          <DraggableEndpoint point={goal} label="B" onDrag={onGoalChange} />
          {alternative.length > 1 && (
            <Polyline
              positions={alternative}
              pathOptions={{
                color: '#F4EDE0',
                opacity: 1,
                weight: 7,
                dashArray: '5 9',
              }}
            />
          )}
          {routePositions.length > 1 && (
            <>
              <Polyline
                positions={routePositions}
                pathOptions={{ color: '#14213D', opacity: 1, weight: 11 }}
              />
              <Polyline
                positions={routePositions}
                pathOptions={{
                  className: 'planned-route-line',
                  color: '#FF4F45',
                  opacity: 1,
                  weight: 7,
                }}
              />
            </>
          )}
          {route?.abort_points?.map((point) => (
            <CircleMarker
              key={`abort-${point.lat}-${point.lng}`}
              center={[point.lat, point.lng]}
              radius={6}
              pathOptions={{
                color: '#14213D',
                weight: 2,
                fillColor: '#FF6B5B',
                fillOpacity: 1,
              }}
            >
              <Popup>{point.label}</Popup>
            </CircleMarker>
          ))}
          <ScaleControl position="bottomleft" imperial={false} />
        </MapContainer>
        <div className="map-caption">
          <span>{config.region.name}</span>
          <span className="map-status">
            <i />{' '}
            {tileError ? 'Basemap unavailable' : 'NASA basemap (historical)'}
          </span>
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
            {editPoint === 'goal'
              ? 'Click to set destination B'
              : 'Click to set starting base A'}{' '}
            · markers can also be dragged
          </div>
        )}
        {imageError && (
          <div className="map-data-error" role="alert">
            {imageError} overlay is unavailable. Other layers and the planner
            can still be used.
            <button type="button" onClick={() => setImageError('')}>
              Dismiss
            </button>
          </div>
        )}
        <p className="map-coverage-note">
          Planner: 40–58°N · 500 m cells. Dashed boundary: historical 3 km
          overlays, 40–52°N. Not rover-scale detail.
        </p>
        <LayerLegend layers={layerList} activeLayers={activeLayers} />
      </div>
    </section>
  )
}
