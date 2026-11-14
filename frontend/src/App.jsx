import { useEffect, useRef, useState } from 'react'
import { getSites, planRoute } from './api/client'
import { normalizeRoute } from './api/contract'
import { layerDefinitions } from './config'
import AskPanel from './components/AskPanel'
import MapView from './components/MapView'
import MissionPanel from './components/MissionPanel'
import SourcesPanel from './components/SourcesPanel'

export default function App() {
  const [step, setStep] = useState('base')
  const [sourceMode, setSourceMode] = useState('live')
  const [activeLayers, setActiveLayers] = useState(Object.fromEntries(layerDefinitions.map(l => [l.id, l.id === 'ice'])))
  const [overlayOpacity, setOverlayOpacity] = useState(.6)
  const [layerMetadata, setLayerMetadata] = useState(null)
  const [sites, setSites] = useState([])
  const [sitesLoading, setSitesLoading] = useState(true)
  const [sitesError, setSitesError] = useState('')
  const [retry, setRetry] = useState(0)
  const [start, setStart] = useState(null)
  const [selectedSite, setSelectedSite] = useState(null)
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
  const [drawer, setDrawer] = useState(null)
  const [mapNotice, setMapNotice] = useState('')
  const generation = useRef(0)
  useEffect(() => { fetch(`${import.meta.env.BASE_URL}layers/layers.json`).then(r => { if (!r.ok) throw Error(); return r.json() }).then(setLayerMetadata).catch(() => setMapNotice('Map layers could not be loaded.')) }, [])
  useEffect(() => {
    let active = true
    getSites(sourceMode).then(data => { if (active) setSites(data.sites) }).catch(error => { if (active) setSitesError(error.message) }).finally(() => { if (active) setSitesLoading(false) })
    return () => { active = false }
  }, [sourceMode, retry])
  function invalidate() { generation.current++; setRoute(null); setRouteError(''); setRouteLoading(false) }
  function reset() { invalidate(); setStart(null); setGoal(null); setSelectedSite(null); setEditPoint(null); setStep('base') }
  function changeSource(next) { reset(); setSourceMode(next); setSitesLoading(true); setSitesError(''); setSites([]) }
  function chooseSite(site) { invalidate(); setStart({lat:site.lat,lng:site.lng,name:site.name}); setGoal(null); setSelectedSite(site); setEditPoint(null); setStep('gear') }
  function pointChange(which, point) {
    if (point.lat < 40 || point.lat > 58 || point.lng < -173 || point.lng > -157) { setMapNotice('That spot is outside the area we can plan routes for.'); return }
    setMapNotice(''); invalidate(); if (which === 'start') { setStart({lat:point.lat,lng:point.lng}); setSelectedSite(null); setStep('gear') } else setGoal({lat:point.lat,lng:point.lng}); setEditPoint(null)
  }
  function change(setter, value) { invalidate(); setter(value) }
  async function calculate(overrides = {}) {
    const options = {sourceMode,start,goal,goalType,oxygenHours,batteryWh,localTimeH,avoid,...overrides}
    if (routeLoading || !options.start || (options.goalType === 'manual' && !options.goal)) return
    const current = ++generation.current; setRouteLoading(true); setRouteError(''); setStep('result')
    try { const result = await planRoute(options); if (generation.current === current) setRoute(result) }
    catch(error) { if (generation.current === current) setRouteError(error.message) }
    finally { if (generation.current === current) setRouteLoading(false) }
  }
  function example() { if (!sites[0]) return; const site=sites[0]; const point={lat:site.lat,lng:site.lng,name:site.name}; invalidate(); setStart(point); setSelectedSite(site); setGoal(null); setGoalType('ice'); setOxygenHours('4'); setBatteryWh('1000'); setLocalTimeH('6'); setAvoid([]); void calculate({start:point,goal:null,goalType:'ice',oxygenHours:4,batteryWh:1000,localTimeH:6,avoid:[]}) }
  function guideRoute(result) {
    if (!result) return
    invalidate(); const planned=result.planner ? normalizeRoute(result.planner) : {...result,sourceMode:'live'}; setRoute(planned)
    if (planned.path?.length) setStart({lat:planned.path[0][0],lng:planned.path[0][1],name:'Guide starting point'})
    if (planned.budget) { setOxygenHours(String(planned.budget.oxygen_hours)); setBatteryWh(String(planned.budget.battery_wh)) }
    if (planned.request) { setLocalTimeH(String(planned.request.local_time_h)); setAvoid(planned.request.avoid || []); setGoalType(planned.request.goal_type ? 'ice':'manual') }
    if (planned.route?.destination) setGoal({lat:planned.route.destination.lat,lng:planned.route.destination.lon > 180 ? planned.route.destination.lon - 360 : planned.route.destination.lon})
    setDrawer(null); setStep('result')
  }
  return <div className="revamp-shell">
    <header className="revamp-header"><button className="wordmark" onClick={reset}>OlympusTrail <span>Mars field guide</span></button><nav aria-label="Mission steps">{[['base','Base'],['gear','Gear'],['result','Result']].map(([id,label],i) => <button key={id} type="button" className={step===id?'current':''} aria-current={step===id?'step':undefined} disabled={id!=='base' && !start} onClick={() => setStep(id)}><span>{i+1}</span> {label}</button>)}</nav><button className="guide-trigger" onClick={() => setDrawer('guide')}>Ask the guide</button></header>
    <div className="data-notice">Planning estimates built from NASA data. Not real mission guidance. <button onClick={() => setDrawer('about')}>About this data</button>{sourceMode==='demo' && <strong> Sample mode</strong>}</div>
    <section className="landing-strip"><div><h1>Plan a walk on Mars</h1><p>Choose a base and see if your supplies can get you to ice and back.</p></div><button className="primary-button" onClick={example} disabled={!sites.length || sitesLoading || routeLoading}>Try an example mission</button></section>
    <main className="revamp-workspace">
      <MapView mode={editPoint || !start ? 'route':'sites'} sites={sites} activeLayers={activeLayers} start={start} goal={goalType==='manual'?goal:null} onMapClick={p => pointChange(editPoint || 'start',p)} onStartChange={p => pointChange('start',p)} onGoalChange={p => pointChange('goal',p)} route={route} askRoutePath={route?.path} selectedSite={selectedSite} layerMetadata={layerMetadata} overlayOpacity={overlayOpacity} onSelectSite={setSelectedSite} onUseSite={chooseSite} sourceMode={sourceMode} editPoint={editPoint} />
      {mapNotice && <div className="map-toast" role="status">{mapNotice}<button onClick={() => setMapNotice('')}>Dismiss</button></div>}
      <aside className="mission-sheet" aria-label="Mission planner">
        {step==='base' ? <section><h2>Pick your base</h2><p>Choose a candidate or tap the map to place A, where your walk begins and ends.</p>{sitesLoading && <p role="status">Waking up the planner… this can take up to a minute the first time.</p>}{sitesError && <p role="alert">{sitesError} <button onClick={() => {setSitesLoading(true);setSitesError('');setRetry(n => n+1)}}>Retry</button></p>}<div className="candidate-list">{sites.map(site => <div key={site.id} className={`candidate ${selectedSite?.id===site.id?'selected':''}`}><button type="button" onClick={() => setSelectedSite(site)} aria-pressed={selectedSite?.id===site.id}><b>{site.rank}</b><span>Site {site.rank}<small>{sourceMode==='demo' ? 'Illustrative example' : `Relative ranking ${site.score}/100`}</small></span></button>{selectedSite?.id===site.id && <><p>{sourceMode === 'demo' ? 'Illustrative location, not a calculated site.' : `Ice evidence: ${site.ice_consistency >= .75 ? 'strong' : site.ice_consistency >= .4 ? 'moderate' : 'lower'} · Terrain: ${site.slope_deg < 5 ? 'gentle' : site.slope_deg < 10 ? 'moderate' : 'steep'}`}</p><button type="button" className="primary-button" onClick={() => chooseSite(site)}>Start here</button></>}</div>)}</div><p className="sheet-hint">Site scores compare locations; they do not establish safety.</p></section> : <MissionPanel step={step} onStepChange={setStep} start={start} goal={goal} goalType={goalType} onGoalTypeChange={v=>change(setGoalType,v)} oxygenHours={oxygenHours} onOxygenChange={v=>change(setOxygenHours,v)} batteryWh={batteryWh} onBatteryChange={v=>change(setBatteryWh,v)} localTimeH={localTimeH} onTimeChange={v=>change(setLocalTimeH,v)} avoid={avoid} onAvoidToggle={id=>change(setAvoid,avoid.includes(id)?avoid.filter(v=>v!==id):[...avoid,id])} onSetPoint={pointChange} onEditPoint={setEditPoint} onReset={reset} onPlanRoute={calculate} route={route} routeLoading={routeLoading} routeError={routeError} sourceMode={sourceMode} />}
        <details className="layer-control"><summary>Map layers</summary><label htmlFor="map-layer">Map layer</label><select id="map-layer" value={Object.keys(activeLayers).find(id=>activeLayers[id])||''} onChange={e=>setActiveLayers(Object.fromEntries(layerDefinitions.map(l=>[l.id,l.id===e.target.value])))}><option value="">None</option><option value="ice">Ice evidence</option><option value="slope">Steepness</option><option value="elevation">Elevation</option><option value="dust">Dust in the air</option><option value="temperature">Temperature</option><option value="sunlight">Sunlight</option><option value="aspect">Slope direction</option></select><label>Opacity <input type="range" min="20" max="100" value={overlayOpacity*100} onChange={e=>setOverlayOpacity(Number(e.target.value)/100)} /></label><p>Ice evidence is not a confirmed deposit.</p></details>
      </aside>
    </main>
    {drawer && <div className="drawer-backdrop" onClick={()=>setDrawer(null)}><aside className="info-drawer" role="dialog" aria-modal="true" aria-label={drawer==='guide'?'Ask the guide':'About this data'} onClick={e=>e.stopPropagation()}><button className="close-drawer" onClick={()=>setDrawer(null)}>Close</button>{drawer==='guide'?<AskPanel key={sourceMode} onRoute={guideRoute} getMapStart={()=>start?[start.lat,start.lng]:null} sourceMode={sourceMode}/>:<><h2>About this data</h2><p>Site scores combine observations and modeled conditions. Ice evidence does not confirm an accessible deposit. Mission parameters are illustrative, not validated guidance.</p><p>Radiation uses a uniform Gale crater reference, not a local Arcadia measurement. Cave and shelter candidates are unverified. Regridding does not increase the resolution of the original sources.</p><SourcesPanel/><button onClick={()=>changeSource(sourceMode==='live'?'demo':'live')}>{sourceMode==='live'?'Use illustrative sample mode':'Use real planner'}</button></>}</aside></div>}
  </div>
}
