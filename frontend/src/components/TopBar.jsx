const modes = [
  { id: 'sites', label: 'Choose base' },
  { id: 'route', label: 'Plan & review' },
  { id: 'ask', label: 'Ask the map' },
]

export default function TopBar({
  mode,
  onModeChange,
  mobilePanel,
  onMobilePanelChange,
}) {
  return (
    <header className="topbar">
      <div className="topbar-main">
        <a
          className="brand"
          href="#purpose-title"
          aria-label="OlympusTrail home"
        >
          <span className="brand-mark" aria-hidden="true">
            <i />
            <i />
            <i />
          </span>
          <span>
            OlympusTrail
            <small className="brand-subtitle">Mars mission planner</small>
          </span>
        </a>
        <nav className="mode-nav" aria-label="Mission tools">
          {modes.map((item, index) => (
            <button
              type="button"
              key={item.id}
              className={`mode-pill ${mode === item.id ? 'is-active' : ''}`}
              aria-current={mode === item.id ? 'page' : undefined}
              onClick={() => onModeChange(item.id)}
            >
              <span className="mode-index">
                {index < 2 ? `0${index + 1}` : '?'}
              </span>{' '}
              {item.label}
            </button>
          ))}
        </nav>
        <span className="mission-region">
          Arcadia Planitia <span> / </span> Mars
        </span>
      </div>
      <nav className="mobile-tabs" aria-label="Mobile panels">
        {[
          ['map', 'Map'],
          ['layers', 'Bases & layers'],
          ['mission', 'Mission'],
        ].map(([id, label]) => (
          <button
            type="button"
            key={id}
            aria-pressed={mobilePanel === id}
            className={mobilePanel === id ? 'mobile-tab active' : 'mobile-tab'}
            onClick={() => onMobilePanelChange(id)}
          >
            {label}
          </button>
        ))}
      </nav>
    </header>
  )
}
