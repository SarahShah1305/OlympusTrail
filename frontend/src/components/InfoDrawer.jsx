import AskPanel from "./AskPanel";
import SourcesPanel from "./SourcesPanel";

export default function InfoDrawer({
  drawer,
  onClose,
  onRoute,
  getMapStart,
  sourceMode,
  onChangeSource,
}) {
  if (!drawer) return null;
  const guide = drawer === "guide";
  return (
    <div className="drawer-backdrop" onClick={onClose}>
      <aside
        className="info-drawer"
        role="dialog"
        aria-modal="true"
        aria-label={guide ? "Ask the guide" : "About this data"}
        onClick={(event) => event.stopPropagation()}
      >
        <button className="close-drawer" type="button" onClick={onClose}>
          Close
        </button>
        {guide ? (
          <AskPanel
            key={sourceMode}
            onRoute={onRoute}
            getMapStart={getMapStart}
            sourceMode={sourceMode}
          />
        ) : (
          <>
            <h2>About this data</h2>
            <p>
              OlympusTrail is a hackathon planning demonstration. Estimates are
              not validated mission guidance.
            </p>
            <p>
              Ice consistency is evidence, not a confirmed deposit. Radiation
              uses a uniform Gale crater reference, not a local Arcadia
              measurement. Cave and shelter candidates are unverified.
              Regridding does not increase source resolution.
            </p>
            <SourcesPanel />
            <button type="button" onClick={onChangeSource}>
              {sourceMode === "live" ? "Use sample mode" : "Use live planner"}
            </button>
          </>
        )}
      </aside>
    </div>
  );
}
