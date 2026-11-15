import { useEffect, useRef, useState } from "react";
import { getSites, planRoute } from "./api/client";
import { normalizeRoute } from "./api/contract";
import { getBriefingMetrics } from "./briefing";
import { timeOfDay } from "./mission";
import { layerDefinitions } from "./config";
import MapView from "./components/MapView";
import MissionPanel from "./components/MissionPanel";
import AppHeader from "./components/AppHeader";
import BasePicker from "./components/BasePicker";
import InfoDrawer from "./components/InfoDrawer";

export default function App() {
  const [step, setStep] = useState("base");
  const [sourceMode, setSourceMode] = useState("live");
  const [activeLayers, setActiveLayers] = useState(
    Object.fromEntries(layerDefinitions.map((l) => [l.id, false])),
  );
  const [overlayOpacity, setOverlayOpacity] = useState(0.6);
  const [layerMetadata, setLayerMetadata] = useState(null);
  const [sites, setSites] = useState([]);
  const [sitesLoading, setSitesLoading] = useState(true);
  const [sitesError, setSitesError] = useState("");
  const [retry, setRetry] = useState(0);
  const [start, setStart] = useState(null);
  const [selectedSite, setSelectedSite] = useState(null);
  const [goal, setGoal] = useState(null);
  const [goalType, setGoalType] = useState("ice");
  const [editPoint, setEditPoint] = useState(null);
  const [oxygenHours, setOxygenHours] = useState("4");
  const [batteryWh, setBatteryWh] = useState("1000");
  const [localTimeH, setLocalTimeH] = useState("6");
  const [avoid, setAvoid] = useState([]);
  const [route, setRoute] = useState(null);
  const [routeLoading, setRouteLoading] = useState(false);
  const [routeError, setRouteError] = useState("");
  const [drawer, setDrawer] = useState(null);
  const [sheetOpen, setSheetOpen] = useState(true);
  const [mapNotice, setMapNotice] = useState("");
  const generation = useRef(0);
  useEffect(() => {
    fetch(`${import.meta.env.BASE_URL}layers/layers.json`)
      .then((r) => {
        if (!r.ok) throw Error();
        return r.json();
      })
      .then(setLayerMetadata)
      .catch(() => setMapNotice("Map layers could not be loaded."));
  }, []);
  useEffect(() => {
    let active = true;
    getSites(sourceMode)
      .then((data) => {
        if (active) setSites(data.sites);
      })
      .catch((error) => {
        if (active) setSitesError(error.message);
      })
      .finally(() => {
        if (active) setSitesLoading(false);
      });
    return () => {
      active = false;
    };
  }, [sourceMode, retry]);
  function invalidate() {
    generation.current++;
    setRoute(null);
    setRouteError("");
    setRouteLoading(false);
  }
  function reset() {
    invalidate();
    setStart(null);
    setGoal(null);
    setSelectedSite(null);
    setEditPoint(null);
    setStep("base");
  }
  function changeSource(next) {
    reset();
    setSourceMode(next);
    setSitesLoading(true);
    setSitesError("");
    setSites([]);
  }
  function chooseSite(site) {
    invalidate();
    setStart({ lat: site.lat, lng: site.lng, name: site.name });
    setGoal(null);
    setSelectedSite(site);
    setEditPoint(null);
    setStep("gear");
  }
  function pointChange(which, point) {
    if (
      point.lat < 40 ||
      point.lat > 58 ||
      point.lng < -173 ||
      point.lng > -157
    ) {
      setMapNotice("That spot is outside the area we can plan routes for.");
      return;
    }
    setMapNotice("");
    invalidate();
    if (which === "start") {
      setStart({ lat: point.lat, lng: point.lng });
      setSelectedSite(null);
      setStep("gear");
    } else setGoal({ lat: point.lat, lng: point.lng });
    setEditPoint(null);
  }
  function change(setter, value) {
    invalidate();
    setter(value);
  }
  async function calculate(overrides = {}) {
    const options = {
      sourceMode,
      start,
      goal,
      goalType,
      oxygenHours,
      batteryWh,
      localTimeH,
      avoid,
      ...overrides,
    };
    if (
      routeLoading ||
      !options.start ||
      (options.goalType === "manual" && !options.goal)
    )
      return;
    const current = ++generation.current;
    setRouteLoading(true);
    setRouteError("");
    setStep("result");
    try {
      const result = await planRoute(options);
      if (generation.current === current) setRoute(result);
    } catch (error) {
      if (generation.current === current) setRouteError(error.message);
    } finally {
      if (generation.current === current) setRouteLoading(false);
    }
  }
  function example() {
    if (!sites[0]) return;
    const site = sites[0];
    const point = { lat: site.lat, lng: site.lng, name: site.name };
    invalidate();
    setStart(point);
    setSelectedSite(site);
    setGoal(null);
    setGoalType("ice");
    setOxygenHours("4");
    setBatteryWh("1000");
    setLocalTimeH("6");
    setAvoid([]);
    void calculate({
      start: point,
      goal: null,
      goalType: "ice",
      oxygenHours: 4,
      batteryWh: 1000,
      localTimeH: 6,
      avoid: [],
    });
  }
  function selectLayer(id) {
    setActiveLayers(
      Object.fromEntries(
        layerDefinitions.map((layer) => [layer.id, layer.id === id]),
      ),
    );
  }
  function guideRoute(result) {
    if (!result) return;
    invalidate();
    const planned = result.planner
      ? normalizeRoute(result.planner)
      : { ...result, sourceMode: "live" };
    setRoute(planned);
    if (planned.path?.length)
      setStart({
        lat: planned.path[0][0],
        lng: planned.path[0][1],
        name: "Guide starting point",
      });
    if (planned.budget) {
      setOxygenHours(String(planned.budget.oxygen_hours));
      setBatteryWh(String(planned.budget.battery_wh));
    }
    if (planned.request) {
      setLocalTimeH(String(planned.request.local_time_h));
      setAvoid(planned.request.avoid || []);
      setGoalType(planned.request.goal_type ? "ice" : "manual");
    }
    if (planned.route?.destination)
      setGoal({
        lat: planned.route.destination.lat,
        lng:
          planned.route.destination.lon > 180
            ? planned.route.destination.lon - 360
            : planned.route.destination.lon,
      });
    setDrawer(null);
    setStep("result");
  }
  return (
    <div className="revamp-shell">
      <AppHeader
        step={step}
        start={start}
        onStepChange={setStep}
        onReset={reset}
        onExample={example}
        onGuide={() => setDrawer("guide")}
        exampleDisabled={!sites.length || sitesLoading || routeLoading}
      />
      <main className="revamp-workspace">
        <MapView
          mode={editPoint || !start ? "route" : "sites"}
          sites={sites}
          activeLayers={activeLayers}
          onSelectLayer={selectLayer}
          start={start}
          goal={goalType === "manual" ? goal : null}
          onMapClick={(p) => pointChange(editPoint || "start", p)}
          onStartChange={(p) => pointChange("start", p)}
          onGoalChange={(p) => pointChange("goal", p)}
          route={route}
          askRoutePath={route?.path}
          selectedSite={selectedSite}
          layerMetadata={layerMetadata}
          overlayOpacity={overlayOpacity}
          onOpacityChange={setOverlayOpacity}
          onSelectSite={setSelectedSite}
          onUseSite={chooseSite}
          sourceMode={sourceMode}
          editPoint={editPoint}
          mapNotice={mapNotice}
          onDismissNotice={() => setMapNotice("")}
        />
        <aside
          className={`mission-sheet ${sheetOpen ? "" : "sheet-collapsed"}`}
          aria-label="Mission planner"
        >
          <button
            type="button"
            className="sheet-handle"
            aria-expanded={sheetOpen}
            onClick={() => setSheetOpen((open) => !open)}
          >
            {sheetOpen ? "Hide mission panel" : "Show mission panel"}
          </button>
          <div className="sheet-body">
            {step === "base" ? (
              <BasePicker
                sites={sites}
                selectedSite={selectedSite}
                sourceMode={sourceMode}
                sitesLoading={sitesLoading}
                sitesError={sitesError}
                onRetry={() => {
                  setSitesLoading(true);
                  setSitesError("");
                  setRetry((n) => n + 1);
                }}
                onSelectSite={setSelectedSite}
                onUseSite={chooseSite}
              />
            ) : (
              <MissionPanel
                step={step}
                onStepChange={setStep}
                start={start}
                goal={goal}
                goalType={goalType}
                onGoalTypeChange={(v) => change(setGoalType, v)}
                oxygenHours={oxygenHours}
                onOxygenChange={(v) => change(setOxygenHours, v)}
                batteryWh={batteryWh}
                onBatteryChange={(v) => change(setBatteryWh, v)}
                localTimeH={localTimeH}
                onTimeChange={(v) => change(setLocalTimeH, v)}
                avoid={avoid}
                onAvoidToggle={(id) =>
                  change(
                    setAvoid,
                    avoid.includes(id)
                      ? avoid.filter((v) => v !== id)
                      : [...avoid, id],
                  )
                }
                onSetPoint={pointChange}
                onEditPoint={setEditPoint}
                onReset={reset}
                onPlanRoute={calculate}
                route={route}
                routeLoading={routeLoading}
                routeError={routeError}
                sourceMode={sourceMode}
              />
            )}
            <p className="panel-disclaimer">
              Planning estimates only. Not validated mission guidance.
            </p>
          </div>
        </aside>
      </main>
      {route && (
        <article className="print-brief">
          <h1>OlympusTrail mission briefing</h1>
          <p>Planning demonstration. Not validated mission guidance.</p>
          <h2>
            {route.status === "ok"
              ? "Within modeled limits"
              : route.status === "search_limit"
                ? "Search incomplete"
                : "No feasible route found"}
          </h2>
          <p>
            Starting point:{" "}
            {Number.isFinite(start?.lat) && Number.isFinite(start?.lng)
              ? `${start.lat.toFixed(3)}° N, ${Math.abs(start.lng).toFixed(3)}° W.`
              : "Not set."}{" "}
            Local scenario time: {timeOfDay(localTimeH)} (
            {String(localTimeH).padStart(2, "0")}:00).
          </p>
          {getBriefingMetrics(route.metrics).length > 0 && (
            <ul>
              {getBriefingMetrics(route.metrics).map((metric) => (
                <li key={metric.label}>
                  {metric.label}: {metric.value} {metric.unit}.
                </li>
              ))}
            </ul>
          )}
          <p>
            A 20% oxygen and battery reserve is included. Return follows the
            outbound path. Ice evidence is not a confirmed deposit. Radiation
            uses a Gale reference; shelter candidates are unverified.
          </p>
          <p>
            Sources: NASA MGS MOLA; SWIM ice consistency; Mars Climate Database.
            See the project sources and caveats for details.
          </p>
        </article>
      )}
      <InfoDrawer
        drawer={drawer}
        onClose={() => setDrawer(null)}
        onRoute={guideRoute}
        getMapStart={() => (start ? [start.lat, start.lng] : null)}
        sourceMode={sourceMode}
        onChangeSource={() =>
          changeSource(sourceMode === "live" ? "demo" : "live")
        }
      />
    </div>
  );
}
