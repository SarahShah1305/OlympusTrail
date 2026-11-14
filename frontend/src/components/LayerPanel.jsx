import SourcesPanel from './SourcesPanel'

function LayerRow({ layer, metadata, active, onToggle }) {
  const coverage =
    metadata && Number.isFinite(metadata.coverage_percent)
      ? `${metadata.coverage_percent.toFixed(1)}% data coverage`
      : null

  return (
    <div className="layer-row">
      <button
        type="button"
        className="layer-switch"
        role="switch"
        aria-checked={active}
        onClick={() => onToggle(layer.id)}
        aria-label={`${layer.label}${metadata?.description ? `: ${metadata.description}` : ''}`}
        title={metadata?.description || layer.description}
      >
        <span
          className={`switch-track ${active ? 'is-on' : ''}`}
          aria-hidden="true"
        >
          <i />
        </span>
        <span className="layer-row-copy">
          <span className="layer-row-title">{layer.label}</span>
          <span className="layer-badge">
            {metadata ? layer.kind : 'Loading'}
          </span>
          {coverage && <span className="coverage-badge">{coverage}</span>}
        </span>
        <span
          className="layer-info"
          title={metadata?.description || layer.description}
          aria-hidden="true"
        >
          i
        </span>
      </button>
      <p className="layer-explanation">
        {metadata?.description || layer.description}
      </p>
    </div>
  )
}

function SiteDetails({ site, sourceMode, onUseSite }) {
  if (!site) return null

  const reasons = (site.reasons || []).filter(
    (reason) => !/shield|radiat|shelter/i.test(String(reason)),
  )

  return (
    <div className="selected-site-details" aria-live="polite">
      <h3>{site.name}</h3>
      <p className="site-score-detail">
        Relative site score: <strong>{site.score}/100</strong>
      </p>
      <p className="muted-copy">
        A comparison score, not a safety percentage or a probability of success.
      </p>
      {Number.isFinite(site.lat) && Number.isFinite(site.lng) && (
        <p className="site-coordinates">
          {site.lat.toFixed(2)}°N,{' '}
          {site.lng < 0
            ? `${Math.abs(site.lng).toFixed(2)}°W`
            : `${site.lng.toFixed(2)}°E`}
        </p>
      )}
      {reasons.length > 0 && (
        <>
          <strong className="site-detail-label">Factors in this ranking</strong>
          <ul className="site-reasons">
            {reasons.map((reason, index) => (
              <li key={`${site.id}-${index}`}>{reason}</li>
            ))}
          </ul>
        </>
      )}
      <p className="muted-copy">
        No verified shelter or radiation protection is established for this
        site.
      </p>
      {sourceMode === 'demo' && (
        <p className="muted-copy">Demo site details are illustrative.</p>
      )}
      <button
        type="button"
        className="site-use-button"
        onClick={() => onUseSite?.(site)}
      >
        Use as starting base
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
  sites = [],
  loading,
  error,
  onSelectSite,
  selectedSite,
  onUseSite,
  sourceMode = 'demo',
}) {
  const metadataById = Object.fromEntries(
    (layerMetadata?.layers || []).map((layer) => [layer.id, layer]),
  )
  const terrainLayers = [
    {
      id: 'elevation',
      label: 'Elevation',
      kind: 'Orbital observation',
      description: 'MOLA orbital altimetry, regridded to the map grid.',
    },
    {
      id: 'slope',
      label: 'Slope',
      kind: 'Derived',
      description: 'Calculated from the elevation grid; regional terrain only.',
    },
    {
      id: 'aspect',
      label: 'Aspect',
      kind: 'Derived',
      description: 'Downhill direction calculated from the elevation grid.',
    },
  ]
  const scienceLayers = [
    {
      id: 'ice',
      label: 'Ice consistency',
      kind: 'Orbital data product',
      description:
        'SWIM indicator for ice consistency in the upper metre. It is not ice depth, a probability, or a confirmed deposit.',
    },
    {
      id: 'temperature',
      label: 'Temperature',
      kind: 'Historical observation',
      description:
        'Scenario mode uses MCD modeled temperatures by local time. Historical THEMIS observations are sparse and span different dates; they are not a forecast.',
    },
    {
      id: 'dust',
      label: 'Atmospheric dust',
      kind: 'Observed climatology',
      description:
        'Modeled atmospheric column optical depth. Coarse regional values, not a surface dust hazard map.',
    },
    {
      id: 'sunlight',
      label: 'Sunlight',
      kind: 'Derived terrain index',
      description:
        'MCD solar flux by local time. Regional model output; it does not account for local shadows at a site.',
    },
  ]
  const activeCount = Object.values(activeLayers || {}).filter(Boolean).length

  return (
    <aside
      className="side-panel left-panel"
      aria-label="Candidate sites and map layers"
    >
      <section className="panel-section sites-section">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Start with a candidate</p>
            <h2>Top sites</h2>
          </div>
          <span className="section-count">{loading ? '…' : sites.length}</span>
        </div>
        <p className="muted-copy">
          Ranked for comparison. Scores are relative and do not measure safety.
        </p>
        {sourceMode === 'demo' && (
          <p className="source-mode-note">
            Demo data: site rankings are illustrative.
          </p>
        )}
        {error && (
          <p className="inline-error" role="alert">
            {error}
          </p>
        )}
        {loading ? (
          <p className="muted-copy">Loading candidate sites…</p>
        ) : sites.length === 0 ? (
          <p className="muted-copy">No candidate sites are available.</p>
        ) : (
          <ol className="site-list">
            {sites.map((site) => (
              <li key={site.id}>
                <button
                  type="button"
                  className="site-row"
                  aria-pressed={selectedSite?.id === site.id}
                  onClick={() => onSelectSite?.(site)}
                >
                  <span
                    className={`site-rank ${site.rank === 1 ? 'first' : ''}`}
                  >
                    {site.rank}
                  </span>
                  <span className="site-row-copy">
                    <strong>{site.name}</strong>
                    <span>Relative score · {site.score}/100</span>
                  </span>
                  <span className="site-chevron" aria-hidden="true">
                    ›
                  </span>
                </button>
              </li>
            ))}
          </ol>
        )}
        <SiteDetails
          site={selectedSite}
          sourceMode={sourceMode}
          onUseSite={onUseSite}
        />
      </section>

      <section className="panel-section">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Explore the map</p>
            <h2>Layers</h2>
          </div>
          <span className="section-count">{activeCount}</span>
        </div>
        <p className="layer-group-title">Terrain</p>
        <div className="layer-list">
          {terrainLayers.map((layer) => (
            <LayerRow
              key={layer.id}
              layer={layer}
              metadata={metadataById[layer.id]}
              active={Boolean(activeLayers?.[layer.id])}
              onToggle={onToggle}
            />
          ))}
        </div>
        <details className="advanced-layers">
          <summary>More data layers</summary>
          <p className="muted-copy">
            Choose one overlay at a time for easier comparison. Data coverage
            describes where values exist; it does not measure certainty or
            resolution.
          </p>
          <div className="layer-list">
            {scienceLayers.map((layer) => (
              <LayerRow
                key={layer.id}
                layer={layer}
                metadata={metadataById[layer.id]}
                active={Boolean(activeLayers?.[layer.id])}
                onToggle={onToggle}
              />
            ))}
          </div>
        </details>
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
            onChange={(event) =>
              onOpacityChange(Number(event.target.value) / 100)
            }
          />
        </label>
        {layerMetadataError && (
          <p className="inline-error" role="alert">
            {layerMetadataError}
          </p>
        )}
      </section>

      <section
        className="radiation-reference"
        aria-labelledby="radiation-title"
      >
        <div className="radiation-heading">
          <strong id="radiation-title">Radiation reference</strong>
          <span>Gale reference</span>
        </div>
        <p>
          <b>0.67 mSv per 24 Earth hours</b> (about 0.028 mSv/h), used as a
          uniform reference scenario.
        </p>
        <p>
          This dose-equivalent reference comes from Gale crater. It is not an
          Arcadia measurement and does not estimate local shielding or
          protection.
        </p>
        <a
          href="https://www.nasa.gov/news-release/nasa-rover-results-include-first-age-measurement-on-mars-and-help-for-human-exploration/"
          target="_blank"
          rel="noreferrer"
        >
          NASA Gale RAD report
        </a>
      </section>

      <section className="panel-section legend-section">
        <div className="section-heading">
          <h2>Map key</h2>
        </div>
        <ul className="legend-list">
          <li>
            <span className="legend-rank">1</span> Ranked candidate site
          </li>
          <li>
            <span className="legend-route" /> Planned route
          </li>
          <li>
            <span className="legend-abort">!</span> Return checkpoint
          </li>
        </ul>
      </section>
      <SourcesPanel />
      <p className="panel-footnote">
        Observations, model scenarios and derived layers are labelled
        separately. Regridding changes pixel spacing, not the source resolution.
        Candidate rankings are for exploration and do not establish safety.
      </p>
    </aside>
  )
}
