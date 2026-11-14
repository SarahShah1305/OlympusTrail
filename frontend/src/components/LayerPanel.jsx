import SourcesPanel from './SourcesPanel'

function LayerRow({ layer, metadata, active, onToggle }) {
  const badge = layer.badge || (metadata?.coverage_percent >= 99
    ? 'Complete'
    : `Partial · ${metadata?.coverage_percent.toFixed(1)}%`)
  const coverage = layer.badge && metadata
    ? (metadata.coverage_percent >= 99
      ? 'Complete coverage'
      : `${metadata.coverage_percent.toFixed(1)}% coverage`)
    : ''

  return (
    <div className="layer-row">
      <button
        type="button"
        className="layer-switch"
        role="switch"
        aria-checked={active}
        onClick={() => onToggle(layer.id)}
        aria-label={`${layer.label}${metadata?.description ? `: ${metadata.description}` : ''}`}
        title={metadata?.description}
      >
        <span className={`switch-track ${active ? 'is-on' : ''}`} aria-hidden="true"><i /></span>
        <span className="layer-row-copy">
          <span className="layer-row-title">{layer.label}</span>
          <span className={`layer-badge ${badge.startsWith('Partial') ? 'partial-badge' : ''}`}>
            {metadata ? badge : 'Loading'}
          </span>
          {coverage && <span className="coverage-badge">{coverage}</span>}
        </span>
        <span className="layer-info" title={metadata?.description} aria-hidden="true">i</span>
      </button>
    </div>
  )
}

export default function LayerPanel({
  activeLayers,
  onToggle,
  opacity,
  onOpacityChange,
  layerMetadata,
  layerMetadataError,
  sites,
  loading,
  error,
  onSelectSite,
}) {
  const metadataById = Object.fromEntries(
    (layerMetadata?.layers || []).map((layer) => [layer.id, layer]),
  )
  const availableLayers = [
    { id: 'elevation', label: 'Elevation' },
    { id: 'slope', label: 'Slope' },
    { id: 'aspect', label: 'Aspect' },
    {
      id: 'dust',
      label: 'Dust risk',
      badge: 'Real data, coarse',
      info: 'Atmospheric column dust optical depth, very coarse (3 deg cells). Not a surface hazard map. Averaged over MY36 daily maps.',
    },
    {
      id: 'ice',
      label: 'Ice',
      info: 'SWIM consistency index of ice in the upper metre. Not ice depth, not a probability, not a confirmed deposit.',
    },
    {
      id: 'temperature',
      label: 'Temperature',
      info: 'Partial coverage from 3 THEMIS scenes taken on different dates. Not a forecast. Empty areas have no data.',
    },
    {
      id: 'sunlight',
      label: 'Sunlight',
      badge: 'Derived',
      info: 'Derived from MOLA terrain. Ignores atmosphere, dust and shadows. Relative index only. Local solar noon at equinox, Sun due south; not daily duration or energy.',
    },
  ]
  return (
    <aside className="side-panel left-panel" aria-label="Map layers and site rankings">
      <section className="panel-section">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Terrain cost grid</p>
            <h2>Layers</h2>
          </div>
          <span className="section-count">{Object.values(activeLayers).filter(Boolean).length}</span>
        </div>
        <p className="layer-group-title">Available layers</p>
        <div className="layer-list">
          {availableLayers.map((layer) => (
            <LayerRow
              key={layer.id}
              layer={layer}
              metadata={metadataById[layer.id]}
              active={Boolean(activeLayers[layer.id])}
              onToggle={onToggle}
            />
          ))}
        </div>
        <label className="opacity-control" htmlFor="layer-opacity">
          <span>Overlay opacity</span>
          <strong>{Math.round(opacity * 100)}%</strong>
          <input
            id="layer-opacity"
            type="range"
            min="20"
            max="100"
            step="5"
            value={Math.round(opacity * 100)}
            onChange={(event) => onOpacityChange(Number(event.target.value) / 100)}
          />
        </label>
        {layerMetadataError && <p className="inline-error" role="alert">{layerMetadataError}</p>}
      </section>

      <section className="radiation-reference" aria-labelledby="radiation-title">
        <div className="radiation-heading">
          <strong id="radiation-title">Radiation</strong>
          <span>Reference value</span>
        </div>
        <p><b>~0.21 mGy/day</b> GCR absorbed dose measured by MSL RAD at Gale crater (-4.4 km).</p>
        <p>This is not an Arcadia measurement. Dose depends on atmospheric depth and solar conditions; Arcadia is in a comparable elevation range. Check with Person 5 for project radiation values.</p>
        <a href="https://doi.org/10.1126/science.1244797" target="_blank" rel="noreferrer">Hassler et al. (2014), Science</a>
      </section>

      <section className="panel-section legend-section">
        <div className="section-heading"><h2>Legend</h2></div>
        <ul className="legend-list">
          <li><span className="legend-rank">1</span> Top base sites</li>
          <li><span className="legend-route" /> Planned route</li>
          <li><span className="legend-abort">!</span> Abort point</li>
        </ul>
      </section>

      <section className="panel-section sites-section">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Colony site selector</p>
            <h2>Top 5 sites</h2>
          </div>
          <span className="section-count">{loading ? '…' : sites.length}</span>
        </div>
        {error && <p className="inline-error" role="alert">{error}</p>}
        {loading ? (
          <p className="muted-copy">Loading candidate sites…</p>
        ) : sites.length === 0 ? (
          <p className="muted-copy">No candidate sites are available.</p>
        ) : (
          <ol className="site-list">
            {sites.map((site) => (
              <li key={site.id}>
                <button type="button" className="site-row" onClick={() => onSelectSite(site)}>
                  <span className={`site-rank ${site.rank === 1 ? 'first' : ''}`}>{site.rank}</span>
                  <span className="site-row-copy">
                    <strong>{site.name}</strong>
                    <span>{site.score}/100 site score</span>
                  </span>
                  <span className="site-chevron" aria-hidden="true">›</span>
                </button>
              </li>
            ))}
          </ol>
        )}
      </section>
      <SourcesPanel />
      <p className="panel-footnote">Terrain, ice and thermal overlays use source rasters; dust is a coarse climatology and sunlight is derived. Site rankings and route estimates are preview data, not API measurements.</p>
    </aside>
  )
}
