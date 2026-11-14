export default function BasePicker({
  sites,
  selectedSite,
  sourceMode,
  sitesLoading,
  sitesError,
  onRetry,
  onSelectSite,
  onUseSite,
}) {
  return (
    <section>
      <h2>Choose a starting point</h2>
      <p>
        Pick a candidate or tap the map to place A. Then check if your supplies
        can get you to ice and back.
      </p>
      {sitesLoading && (
        <p role="status">
          Loading planner data. The first request can take up to a minute.
        </p>
      )}
      {sitesError && (
        <p role="alert">
          {sitesError}{" "}
          <button type="button" onClick={onRetry}>
            Retry
          </button>
        </p>
      )}
      <div className="candidate-list">
        {sites.map((site) => (
          <div
            key={site.id}
            className={`candidate ${selectedSite?.id === site.id ? "selected" : ""}`}
          >
            <button
              type="button"
              onClick={() => onSelectSite(site)}
              aria-pressed={selectedSite?.id === site.id}
            >
              <b>{site.rank}</b>
              <span>
                Candidate base {site.rank}
                <small>
                  {sourceMode === "demo"
                    ? "Illustrative example"
                    : `Ranking score ${site.score} out of 100`}
                </small>
              </span>
            </button>
            <p>
              {sourceMode === "demo"
                ? "Example location only; no site score or ice deposit was calculated."
                : `Ice evidence is ${site.ice_consistency >= 0.75 ? "stronger" : site.ice_consistency >= 0.4 ? "moderate" : "lower"}. The terrain slope is ${site.slope_deg < 5 ? "gentle" : site.slope_deg < 10 ? "moderate" : "steep"}.`}
            </p>
            {selectedSite?.id === site.id && (
              <button
                type="button"
                className="primary-button"
                onClick={() => onUseSite(site)}
              >
                Start here
              </button>
            )}
          </div>
        ))}
      </div>
      <p className="sheet-hint">
        Scores compare candidate locations. They do not establish safety.
      </p>
    </section>
  );
}
