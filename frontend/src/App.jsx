import { useEffect, useRef, useState } from 'react'
import { getSites, planRoute } from './api/client'
import { normalizeRoute } from './api/contract'
import { layerDefinitions } from './config'
import AskPanel from './components/AskPanel'
import LayerPanel from './components/LayerPanel'
import MapView from './components/MapView'
import MissionPanel from './components/MissionPanel'
import TopBar from './components/TopBar'

export default function App() {
  const [mode, setMode] = useState('sites')
  const [mobilePanel, setMobilePanel] = useState('layers')
  const [sourceMode, setSourceMode] = useState('live')
  const [overlayOpacity, setOverlayOpacity] = useState(0.6)
  const [activeLayers, setActiveLayers] = useState(
    Object.fromEntries(layerDefinitions.map((l) => [l.id, l.id === 'ice'])),
  )
  const [layerMetadata, setLayerMetadata] = useState(null)
  const [layerMetadataError, setLayerMetadataError] = useState('')
  const [sites, setSites] = useState([])
  const [sitesLoading, setSitesLoading] = useState(true)
  const [sitesError, setSitesError] = useState('')
  const [retry, setRetry] = useState(0)
  const [start, setStart] = useState(null)
  const [goal, setGoal] = useState(null)
  const [goalType, setGoalType] = useState('ice')
  const [editPoint, setEditPoint] = useState(null)
  const [oxygenHours, setOxygenHours] = useState('4')
  const [batteryWh, setBatteryWh] = useState('1000')
  const [localTimeH, setLocalTimeH] = useState('6')
  const [avoid, setAvoid] = useState([])
  const [route, setRoute] = useState(null)
  const [routeLoading, setRouteLoading] = useState(false)
  const [routeError, setRouteError] = useState('')
  const [selectedSite, setSelectedSite] = useState(null)
  const generation = useRef(0)
  const workspaceRef = useRef(null)
  useEffect(() => {
    fetch(`${import.meta.env.BASE_URL}layers/layers.json`)
      .then((r) => {
        if (!r.ok) throw Error()
        return r.json()
      })
      .then(setLayerMetadata)
      .catch(() =>
        setLayerMetadataError(
          'Map overlays are unavailable. You can still use the planner.',
        ),
      )
  }, [])
  useEffect(() => {
    let active = true
    getSites(sourceMode)
      .then((data) => {
        if (active) setSites(data.sites)
      })
      .catch((error) => {
        if (active) setSitesError(error.message)
      })
      .finally(() => {
        if (active) setSitesLoading(false)
      })
    return () => {
      active = false
    }
  }, [sourceMode, retry])
  function invalidate() {
    generation.current++
    setRoute(null)
    setRouteError('')
    setRouteLoading(false)
  }
  function changeSource(next) {
    invalidate()
    setSourceMode(next)
    setSitesLoading(true)
    setSitesError('')
    setSites([])
    setStart(null)
    setGoal(null)
    setSelectedSite(null)
    setEditPoint(null)
  }
  function chooseMode(next) {
    setMode(next)
    setMobilePanel(next === 'sites' ? 'layers' : 'mission')
    workspaceRef.current?.scrollIntoView({ block: 'start' })
  }
  function useSite(site) {
    invalidate()
    setStart({ lat: site.lat, lng: site.lng, name: site.name })
    setGoal(null)
    setSelectedSite(site)
    setEditPoint(null)
    chooseMode('route')
  }
  function pointChange(which, point) {
    invalidate()
    ;(which === 'start' ? setStart : setGoal)({
      lat: point.lat,
      lng: point.lng,
    })
    setEditPoint(null)
  }
  function change(setter, value) {
    invalidate()
    setter(value)
  }
  async function calculate() {
    if (routeLoading || !start || (goalType === 'manual' && !goal)) return
    const current = ++generation.current
    setRouteLoading(true)
    setRouteError('')
    try {
      const result = await planRoute({
        sourceMode,
        start,
        goal,
        goalType,
        oxygenHours,
        batteryWh,
        localTimeH,
        avoid,
      })
      if (generation.current === current) {
        setRoute(result)
        setMode('route')
      }
    } catch (error) {
      if (generation.current === current) setRouteError(error.message)
    } finally {
      if (generation.current === current) setRouteLoading(false)
    }
  }
  function guideRoute(result) {
    if (!result) return
    invalidate()
    const planned = result.planner
      ? normalizeRoute(result.planner)
      : { ...result, sourceMode: 'live' }
    setRoute(planned)
    if (planned.path?.length)
      setStart({
        lat: planned.path[0][0],
        lng: planned.path[0][1],
        name: 'Guide starting point',
      })
    if (planned.budget) {
      setOxygenHours(String(planned.budget.oxygen_hours))
      setBatteryWh(String(planned.budget.battery_wh))
    }
    if (planned.request) {
      setLocalTimeH(String(planned.request.local_time_h))
      setAvoid(planned.request.avoid || [])
      setGoalType(planned.request.goal_type ? 'ice' : 'manual')
    }
    if (planned.route?.destination)
      setGoal({
        lat: planned.route.destination.lat,
        lng:
          planned.route.destination.lon > 180
            ? planned.route.destination.lon - 360
            : planned.route.destination.lon,
      })
    setMode('route')
  }
  return (
    <div className={`app-shell mobile-view-${mobilePanel}`}>
      <TopBar
        mode={mode}
        onModeChange={chooseMode}
        mobilePanel={mobilePanel}
        onMobilePanelChange={setMobilePanel}
      />
      <section className="mission-intro" aria-labelledby="purpose-title">
        <div>
          <p className="eyebrow">Explore a possible human mission on Mars</p>
          <h1 id="purpose-title">
            Choose a base. Reach the ice. Make it back.
          </h1>
          <p>
            Compare possible base locations in Arcadia Planitia, a Mars region
            with evidence of shallow subsurface ice. Then check a walking round
            trip against oxygen and battery limits.
          </p>
        </div>
        <div className="intro-actions">
          <button
            className="primary-button"
            onClick={() => chooseMode('sites')}
          >
            1. Choose a starting base
          </button>
          <button
            className="secondary-button"
            onClick={() => {
              chooseMode('route')
              setEditPoint('start')
              setMobilePanel('map')
            }}
          >
            Explore the map
          </button>
        </div>
      </section>
      <div
        className={`source-banner ${sourceMode === 'demo' ? 'is-demo' : ''}`}
        role="status"
      >
        <strong>
          {sourceMode === 'demo'
            ? 'SAMPLE DEMONSTRATION'
            : 'NASA observations + scientific models'}
        </strong>
        <span>
          {sourceMode === 'demo'
            ? 'Example sites and simple supply calculations; no terrain route or verified ice target.'
            : 'Hackathon planning estimates, not validated human mission guidance. Failed requests never switch to samples.'}
        </span>
        <button
          type="button"
          onClick={() => changeSource(sourceMode === 'live' ? 'demo' : 'live')}
        >
          {sourceMode === 'live' ? 'Try sample mode' : 'Use real planner'}
        </button>
        {sitesError && (
          <button
            type="button"
            onClick={() => {
              setSitesLoading(true)
              setSitesError('')
              setRetry((n) => n + 1)
            }}
          >
            Retry connection
          </button>
        )}
      </div>
      <main className="workspace" ref={workspaceRef}>
        <LayerPanel
          activeLayers={activeLayers}
          onToggle={(id) =>
            setActiveLayers((previous) =>
              Object.fromEntries(
                layerDefinitions.map((l) => [
                  l.id,
                  l.id === id && !previous[id],
                ]),
              ),
            )
          }
          opacity={overlayOpacity}
          onOpacityChange={setOverlayOpacity}
          layerMetadata={layerMetadata}
          layerMetadataError={layerMetadataError}
          sites={sites}
          loading={sitesLoading}
          error={sitesError}
          selectedSite={selectedSite}
          onSelectSite={setSelectedSite}
          onUseSite={useSite}
          sourceMode={sourceMode}
        />
        <MapView
          mode={editPoint ? 'route' : 'sites'}
          sites={sites}
          activeLayers={activeLayers}
          start={start}
          goal={goalType === 'manual' ? goal : null}
          onMapClick={(point) => pointChange(editPoint || 'start', point)}
          onStartChange={(point) => pointChange('start', point)}
          onGoalChange={(point) => pointChange('goal', point)}
          route={route}
          askRoutePath={route?.path}
          selectedSite={selectedSite}
          layerMetadata={layerMetadata}
          overlayOpacity={overlayOpacity}
          onSelectSite={setSelectedSite}
          onUseSite={useSite}
          sourceMode={sourceMode}
          editPoint={editPoint}
        />
        <aside
          className="side-panel right-panel"
          aria-label="Plan and review your mission"
        >
          {mode !== 'ask' && (
            <MissionPanel
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
              onEditPoint={(which) => {
                setEditPoint(which)
                setMobilePanel('map')
              }}
              onReset={() => {
                invalidate()
                setStart(null)
                setGoal(null)
                setEditPoint(null)
                setSelectedSite(null)
              }}
              onPlanRoute={calculate}
              route={route}
              routeLoading={routeLoading}
              routeError={routeError}
              sourceMode={sourceMode}
            />
          )}
          <AskPanel
            key={sourceMode}
            onRoute={guideRoute}
            getMapStart={() => (start ? [start.lat, start.lng] : null)}
            sourceMode={sourceMode}
          />
        </aside>
      </main>
    </div>
  )
}
