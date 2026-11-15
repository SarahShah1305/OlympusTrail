import { useEffect, useRef, useState } from "react";
import {
  CircleMarker,
  ImageOverlay,
  MapContainer,
  Marker,
  Polygon,
  Polyline,
  Popup,
  Rectangle,
  ScaleControl,
  TileLayer,
  ZoomControl,
  useMap,
  useMapEvents,
} from "react-leaflet";
import L from "leaflet";
import { config } from "../config";
import "../styles/map-revamp.css";

const marsCrs = Object.create(L.CRS.EPSG4326);
marsCrs.code = "IAU2000:104905";
marsCrs.distance = (a, b) => {
  const r = (d) => (d * Math.PI) / 180;
  const h =
    Math.sin(r(b.lat - a.lat) / 2) ** 2 +
    Math.cos(r(a.lat)) *
      Math.cos(r(b.lat)) *
      Math.sin(r(b.lng - a.lng) / 2) ** 2;
  return (
    2 * config.region.marsRadiusMeters * Math.asin(Math.sqrt(Math.min(1, h)))
  );
};
const bounds = config.region.bounds;
const EMPTY_PATH = [];
const viewBounds = [
  [bounds[0][0] - 4, bounds[0][1] - 4],
  [bounds[1][0] + 4, bounds[1][1] + 4],
];
const isInside = ({ lat, lng }) =>
  lat >= bounds[0][0] &&
  lat <= bounds[1][0] &&
  lng >= bounds[0][1] &&
  lng <= bounds[1][1];
const pos = (p) => [p.lat, p.lon > 180 ? p.lon - 360 : p.lon];

function MapEvents({ enabled, onMapClick, onOutside }) {
  useMapEvents({
    click(e) {
      if (!isInside(e.latlng)) onOutside();
      else if (enabled) onMapClick(e.latlng);
    },
  });
  return null;
}
function FitArea({ site, path }) {
  const map = useMap();
  const siteId = site?.id;
  const siteLat = site?.lat;
  const siteLng = site?.lng;
  const pathKey = path.map((point) => point.join(",")).join(";");
  useEffect(() => {
    let initial = true;
    const update = () => {
      const container = map.getContainer();
      if (!container.clientWidth || !container.clientHeight) return;
      map.invalidateSize({ animate: false });
      const initialBounds = window.matchMedia("(max-width: 780px)").matches
        ? bounds
        : viewBounds;
      const zoom = Math.max(0, map.getBoundsZoom(initialBounds));
      map.setMinZoom(Math.min(zoom, config.region.maxZoom));
      map.setMaxBounds(viewBounds);
      if (initial) {
        map.fitBounds(initialBounds, {
          animate: false,
          padding: initialBounds === bounds ? [24, 24] : [0, 0],
        });
        initial = false;
      }
    };
    const observer = new ResizeObserver(update);
    observer.observe(map.getContainer());
    update();
    return () => observer.disconnect();
  }, [map]);
  useEffect(() => {
    if (!map.getSize().x || !map.getSize().y) return;
    const stablePath = pathKey
      ? pathKey.split(";").map((point) => point.split(",").map(Number))
      : EMPTY_PATH;
    if (stablePath.length > 1)
      map.fitBounds(stablePath, { padding: [36, 36], animate: false });
    else if (Number.isFinite(siteLat) && Number.isFinite(siteLng))
      map.setView([siteLat, siteLng], Math.max(map.getZoom(), 6), {
        animate: false,
      });
  }, [map, pathKey, siteId, siteLat, siteLng]);
  return null;
}
function PanToStart({ start, route, selectedSite }) {
  const map = useMap();
  const lat = start?.lat,
    lng = start?.lng;
  const context = useRef({ route, selectedSite });
  useEffect(() => {
    context.current = { route, selectedSite };
  }, [route, selectedSite]);
  useEffect(() => {
    const { route: currentRoute, selectedSite: site } = context.current;
    if (
      lat == null ||
      lng == null ||
      currentRoute ||
      (site && site.lat === lat && site.lng === lng)
    )
      return;
    map.panTo([lat, lng], { animate: false });
  }, [map, lat, lng]);
  return null;
}
function icon(label, kind, selected) {
  return L.divIcon({
    className: "map-marker-icon",
    html: `<span class="trail-marker trail-marker-${kind}${selected ? " selected" : ""}">${label}</span>`,
    iconSize: kind === "site" ? [26, 26] : [40, 40],
    iconAnchor: kind === "site" ? [13, 13] : [20, 20],
  });
}
function Endpoint({ point, label, onDrag, draggable = true }) {
  if (!point) return null;
  const title = label === "A" ? "A, you are here" : "B, destination";
  return (
    <Marker
      position={[point.lat, point.lng]}
      icon={icon(label, label.toLowerCase())}
      zIndexOffset={label === "A" ? 1000 : 900}
      title={title}
      alt={title}
      draggable={draggable}
      eventHandlers={{
        dragend(e) {
          const p = e.target.getLatLng();
          if (isInside(p)) onDrag?.({ lat: p.lat, lng: p.lng });
          else e.target.setLatLng([point.lat, point.lng]);
        },
      }}
    >
      <Popup>
        {title}
        {draggable ? ", drag to adjust" : ""}
      </Popup>
    </Marker>
  );
}
function Legend() {
  return (
    <details className="trail-map-legend">
      <summary>Map key</summary>
      <div className="trail-legend-items">
        <span>
          <b className="trail-key-a">A</b> You are here
        </span>
        <span>
          <b className="trail-key-b">B</b> Destination
        </span>
        <span>
          <i className="trail-key-route" /> Route out
        </span>
        <span>
          <i className="trail-key-return" /> Return route
        </span>
        <span>● Turn-back point</span>
        <span>① Candidate site</span>
        <span className="elevation-key">
          <i /> Low elevation (blue) → high elevation (yellow)
        </span>
      </div>
    </details>
  );
}
function LayerControls({
  layers,
  activeLayers,
  onSelectLayer,
  opacity,
  onOpacityChange,
}) {
  const [optionsOpen, setOptionsOpen] = useState(
    () => !window.matchMedia("(max-width: 780px)").matches,
  );
  const activeId = Object.keys(activeLayers).find((id) => activeLayers[id]);
  const activeLayer = layers.find((layer) => layer.id === activeId);
  const quickLayers = [
    ["", "None"],
    ["ice", "Ice evidence"],
    ["slope", "Steepness"],
    ["elevation", "Elevation"],
  ];
  const moreLayers = layers.filter(
    (layer) => !["ice", "slope", "elevation"].includes(layer.id),
  );
  return (
    <div className="trail-layer-controls" aria-label="Map layers">
      <div className="trail-layer-chips">
        {quickLayers.map(([id, label]) => (
          <button
            key={id || "none"}
            type="button"
            className={(activeId || "") === id ? "active" : ""}
            aria-pressed={(activeId || "") === id}
            onClick={() => onSelectLayer(id)}
          >
            {label}
          </button>
        ))}
        <details className="trail-more-layers">
          <summary>More layers</summary>
          <div>
            {moreLayers.map((layer) => (
              <button
                key={layer.id}
                type="button"
                aria-pressed={activeId === layer.id}
                onClick={(event) => {
                  onSelectLayer(layer.id);
                  event.currentTarget.closest("details").open = false;
                }}
              >
                {layer.label}
              </button>
            ))}
          </div>
        </details>
      </div>
      <details
        className="trail-layer-options"
        open={optionsOpen}
        onToggle={(event) => setOptionsOpen(event.currentTarget.open)}
      >
        <summary>Layer options</summary>
        <label className="trail-opacity">
          Overlay opacity{" "}
          <input
            type="range"
            min="20"
            max="100"
            value={opacity * 100}
            onChange={(event) =>
              onOpacityChange(Number(event.target.value) / 100)
            }
          />
        </label>
        <div className="active-layer-key" aria-live="polite">
          {activeLayer ? (
            <>
              <strong>{activeLayer.label}</strong>
              {activeLayer.legend_colors?.length > 0 && (
                <div
                  className="trail-ramp"
                  style={{
                    background: `linear-gradient(90deg, ${activeLayer.legend_colors.join(", ")})`,
                  }}
                />
              )}
              {activeLayer.id === "ice" ? (
                <>
                  <div className="ice-scale">
                    <span>Low</span>
                    <span>Medium</span>
                    <span>High</span>
                  </div>
                  <p>
                    Evidence only, not a confirmed deposit. Regional data;
                    native cells are about 3 km across.
                  </p>
                </>
              ) : activeLayer.id === "aspect" ? (
                <p>
                  {activeLayer.description} 0° is north; values increase
                  clockwise.
                </p>
              ) : (
                <>
                  <div className="ramp-labels">
                    <span>
                      Low: {activeLayer.min} {activeLayer.units}
                    </span>
                    <span>
                      High: {activeLayer.max} {activeLayer.units}
                    </span>
                  </div>
                  <p>{activeLayer.description}</p>
                </>
              )}
            </>
          ) : (
            <span>NASA MOLA colour-shaded elevation</span>
          )}
        </div>
      </details>
    </div>
  );
}
export default function MapView({
  mode,
  sites = [],
  activeLayers,
  onSelectLayer,
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
  onOpacityChange,
  allowMapClick,
  mapNotice,
  onDismissNotice,
}) {
  const [tileError, setTileError] = useState(false);
  const tileFailures = useRef(0);
  useEffect(() => {
    if (!tileError) return;
    const timer = window.setTimeout(() => setTileError(false), 4000);
    return () => window.clearTimeout(timer);
  }, [tileError]);
  const [imageError, setImageError] = useState("");
  const [outside, setOutside] = useState(false);
  useEffect(() => {
    if (!mapNotice) return;
    const timer = window.setTimeout(() => onDismissNotice?.(), 4000);
    return () => window.clearTimeout(timer);
  }, [mapNotice, onDismissNotice]);
  useEffect(() => {
    if (!imageError) return;
    const timer = window.setTimeout(() => setImageError(""), 4000);
    return () => window.clearTimeout(timer);
  }, [imageError]);
  const layerList = layerMetadata?.layers || [];
  const path = route?.path || EMPTY_PATH;
  const outbound = route?.route?.outbound?.map(pos) || path;
  const returnPath = route?.route?.return_path?.map(pos) || [];
  const destination = route?.route?.destination
    ? pos(route.route.destination)
    : sourceMode === "demo" && route?.status === "ok"
      ? path[1]
      : null;
  const hiddenSite = (s) =>
    start &&
    Math.abs(s.lat - start.lat) < 0.00001 &&
    Math.abs(s.lng - start.lng) < 0.00001;
  const mid = Math.floor(outbound.length / 2);
  const arrow =
    mid > 0
      ? {
          point: outbound[mid],
          angle:
            (Math.atan2(
              outbound[mid][1] - outbound[mid - 1][1],
              outbound[mid][0] - outbound[mid - 1][0],
            ) *
              180) /
            Math.PI,
        }
      : null;
  const mask = [
    [
      [-90, -180],
      [-90, 180],
      [90, 180],
      [90, -180],
    ],
    [
      [40, -173],
      [58, -173],
      [58, -157],
      [40, -157],
    ],
  ];
  const pathKey = outbound.map((point) => point.join(",")).join(";");
  return (
    <section className="map-column" aria-label="Mars planning map">
      <div className="map-canvas">
        <MapContainer
          center={config.region.center}
          zoom={config.region.zoom}
          minZoom={config.region.minZoom}
          maxZoom={config.region.maxZoom}
          maxBounds={viewBounds}
          maxBoundsViscosity={0.65}
          crs={marsCrs}
          scrollWheelZoom
          zoomControl={false}
          zoomSnap={0.25}
          zoomDelta={0.5}
          className="leaflet-map"
        >
          <FitArea site={selectedSite} path={askRoutePath || path} />
          <PanToStart start={start} route={route} selectedSite={selectedSite} />
          <TileLayer
            className="trail-basemap"
            url={config.map.tileUrl}
            maxNativeZoom={6}
            attribution={config.map.attribution}
            eventHandlers={{
              tileerror: () => {
                tileFailures.current += 1;
                if (tileFailures.current >= 3) {
                  tileFailures.current = 0;
                  setTileError(true);
                }
              },
              tileload: () => {
                tileFailures.current = 0;
              },
            }}
          />
          {layerList
            .filter((l) => activeLayers[l.id])
            .map((l) => (
              <ImageOverlay
                key={l.id}
                url={`${import.meta.env.BASE_URL}layers/${l.image}`}
                bounds={l.bounds_latlng}
                opacity={overlayOpacity}
                alt={`${l.label} map overlay`}
                eventHandlers={{ error: () => setImageError(l.label) }}
              />
            ))}
          <Polygon
            positions={mask}
            interactive={false}
            pathOptions={{
              stroke: false,
              fillColor: "#191b1b",
              fillOpacity: 0.27,
              fillRule: "evenodd",
            }}
          />
          <Rectangle
            bounds={bounds}
            interactive={false}
            pathOptions={{
              color: "#fff",
              opacity: 0.7,
              weight: 1,
              fill: false,
            }}
          />
          <MapEvents
            enabled={allowMapClick ?? (mode === "route" || !start)}
            onMapClick={onMapClick}
            onOutside={() => {
              setOutside(true);
              window.setTimeout(() => setOutside(false), 4000);
            }}
          />
          {sites
            .filter((s) => !hiddenSite(s))
            .map((site) => (
              <Marker
                key={site.id}
                position={[site.lat, site.lng]}
                icon={icon(site.rank, "site", selectedSite?.id === site.id)}
                opacity={selectedSite && selectedSite.id !== site.id ? 0.55 : 1}
                title={`Candidate base ${site.rank}`}
                eventHandlers={{ click: () => onSelectSite?.(site) }}
              >
                <Popup>
                  <div className="site-popup">
                    <strong>Candidate base {site.rank}</strong>
                    <p>
                      {sourceMode === "demo"
                        ? "Example location"
                        : `Relative score ${site.score}/100`}
                    </p>
                    <button
                      type="button"
                      className="site-use-button"
                      onClick={() => onUseSite?.(site)}
                    >
                      Start here
                    </button>
                  </div>
                </Popup>
              </Marker>
            ))}
          {outbound.length > 1 && (
            <>
              <Polyline
                key={`casing-${pathKey}`}
                interactive={false}
                positions={outbound}
                pathOptions={{ color: "#142322", weight: 12, opacity: 0.96 }}
              />
              <Polyline
                key={`route-${pathKey}`}
                className="trail-route"
                interactive={false}
                positions={outbound}
                pathOptions={{
                  color: "#fff",
                  weight: 6,
                  opacity: 1,
                }}
              />
            </>
          )}
          {arrow && (
            <Marker
              position={arrow.point}
              interactive={false}
              icon={L.divIcon({
                className: "route-arrow",
                html: `<span style="transform:rotate(${arrow.angle}deg)">▲</span>`,
                iconSize: [22, 22],
                iconAnchor: [11, 11],
              })}
            />
          )}
          {returnPath.length > 1 && (
            <Polyline
              interactive={false}
              positions={returnPath}
              pathOptions={{ color: "#d78154", weight: 3, dashArray: "5 9" }}
            />
          )}
          {route?.turn_back?.abort_points?.map(
            (point, i) =>
              point.position && (
                <CircleMarker
                  key={i}
                  center={pos(point.position)}
                  radius={5}
                  pathOptions={{
                    color: "#292c28",
                    fillColor: "#f3ce74",
                    fillOpacity: 1,
                    weight: 2,
                  }}
                >
                  <Popup>Return checkpoint {i + 1}</Popup>
                </CircleMarker>
              ),
          )}
          <Endpoint point={start} label="A" onDrag={onStartChange} />
          {goal ? (
            <Endpoint point={goal} label="B" onDrag={onGoalChange} />
          ) : (
            destination && (
              <Endpoint
                point={{ lat: destination[0], lng: destination[1] }}
                label="B"
                draggable={false}
              />
            )
          )}
          <ScaleControl position="bottomright" imperial={false} />
          <ZoomControl position="bottomright" />
        </MapContainer>
        <LayerControls
          layers={layerList}
          activeLayers={activeLayers}
          onSelectLayer={onSelectLayer}
          opacity={overlayOpacity}
          onOpacityChange={onOpacityChange}
        />
        {mode === "route" && (
          <div className="map-hint" role="status">
            {editPoint === "goal" ? (
              <>
                <span className="pointer-click">Click</span>
                <span className="pointer-tap">Tap</span> to set destination B
              </>
            ) : (
              <>
                <span className="pointer-click">Click</span>
                <span className="pointer-tap">Tap</span> anywhere to place A
              </>
            )}
          </div>
        )}
        <div className="map-notices" aria-live="polite">
          {outside && (
            <div className="trail-map-notice">
              That spot is outside the area we can plan routes for.
            </div>
          )}
          {tileError && (
            <div className="trail-map-notice">
              Some NASA basemap tiles could not load.
            </div>
          )}
          {imageError && (
            <div className="trail-map-notice">
              {imageError} overlay is unavailable.{" "}
              <button type="button" onClick={() => setImageError("")}>
                Dismiss
              </button>
            </div>
          )}
          {mapNotice && (
            <div className="trail-map-notice">
              {mapNotice}{" "}
              <button type="button" onClick={onDismissNotice}>
                Dismiss
              </button>
            </div>
          )}
        </div>
        <Legend />
      </div>
    </section>
  );
}
