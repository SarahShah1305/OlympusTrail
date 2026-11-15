import AskPanel from "./AskPanel";
import SourcesPanel from "./SourcesPanel";
import { useEffect, useRef } from "react";

export default function InfoDrawer({
  drawer,
  onClose,
  onRoute,
  getMapStart,
  sourceMode,
  onChangeSource,
}) {
  const dialogRef = useRef(null);
  const closeRef = useRef(null);
  const onCloseRef = useRef(onClose);
  useEffect(() => {
    onCloseRef.current = onClose;
  }, [onClose]);
  useEffect(() => {
    if (!drawer) return;
    const trigger = document.activeElement;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    closeRef.current?.focus();
    function handleKey(event) {
      if (event.key === "Escape") {
        event.preventDefault();
        onCloseRef.current();
      }
      if (event.key !== "Tab") return;
      const controls = [
        ...dialogRef.current.querySelectorAll(
          'button:not(:disabled), a[href], input:not(:disabled), select:not(:disabled), textarea:not(:disabled), summary, [tabindex="0"]',
        ),
      ].filter((element) => element.getClientRects().length);
      const first = controls[0];
      const last = controls.at(-1);
      if (!first) {
        event.preventDefault();
        return;
      }
      if (
        event.shiftKey &&
        (document.activeElement === first ||
          !dialogRef.current.contains(document.activeElement))
      ) {
        event.preventDefault();
        last.focus();
      } else if (
        !event.shiftKey &&
        (document.activeElement === last ||
          !dialogRef.current.contains(document.activeElement))
      ) {
        event.preventDefault();
        first.focus();
      }
    }
    document.addEventListener("keydown", handleKey);
    return () => {
      document.removeEventListener("keydown", handleKey);
      document.body.style.overflow = previousOverflow;
      if (trigger?.isConnected) trigger.focus();
    };
  }, [drawer]);
  if (!drawer) return null;
  const guide = drawer === "guide";
  return (
    <div className="drawer-backdrop" onClick={onClose}>
      <aside
        ref={dialogRef}
        className="info-drawer"
        role="dialog"
        aria-modal="true"
        aria-label={guide ? "Ask the guide" : "About this data"}
        onClick={(event) => event.stopPropagation()}
      >
        <button
          ref={closeRef}
          className="close-drawer"
          type="button"
          onClick={onClose}
        >
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
