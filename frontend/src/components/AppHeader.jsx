export default function AppHeader({
  step,
  start,
  onStepChange,
  onReset,
  onExample,
  onGuide,
  exampleDisabled,
}) {
  return (
    <header className="revamp-header">
      <button className="wordmark" type="button" onClick={onReset}>
        OlympusTrail
      </button>
      <nav aria-label="Mission steps">
        {[
          ["base", "Base"],
          ["gear", "Gear"],
          ["result", "Result"],
        ].map(([id, label], index) => (
          <button
            key={id}
            type="button"
            className={step === id ? "current" : ""}
            aria-current={step === id ? "step" : undefined}
            disabled={id !== "base" && !start}
            onClick={() => onStepChange(id)}
          >
            <span>{index + 1}</span> {label}
          </button>
        ))}
      </nav>
      <div className="header-actions">
        <button
          className="example-trigger"
          type="button"
          onClick={onExample}
          disabled={exampleDisabled}
        >
          Try an example mission
        </button>
        <button className="guide-trigger" type="button" onClick={onGuide}>
          Ask the guide
        </button>
      </div>
    </header>
  );
}
