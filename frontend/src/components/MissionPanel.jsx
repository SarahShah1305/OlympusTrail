import { useState } from 'react'
import { presets, tripVerdict } from '../mission.js'

const duration = value => { const minutes = Math.round(value * 60); return `${Math.floor(minutes / 60)} h ${minutes % 60} min` }
const number = (value) =>
  Number.isFinite(value) ? value.toFixed(2) : 'Not available'

function Point({ title, point, onEdit, onSet }) {
  const [lat, setLat] = useState(point?.lat ?? '')
  const [lon, setLon] = useState(point?.lng == null ? '' : Math.abs(point.lng))
  const valid =
    lat !== '' &&
    lon !== '' &&
    Number(lat) >= 40 &&
    Number(lat) <= 58 &&
    Number(lon) >= 157 &&
    Number(lon) <= 173
  return (
    <div className="mission-point">
      <strong>{title}</strong>
      <p>{point ? point.name || 'Selected map point' : 'Choose a point to continue'}</p>
      {point && (
        <small>
          {point.lat.toFixed(3)}° N, {Math.abs(point.lng).toFixed(3)}°{' '}
          {point.lng < 0 ? 'W' : 'E'}
        </small>
      )}
      <button type="button" className="text-button" onClick={onEdit}>
        {point ? 'Change' : 'Choose on map'}
      </button>
      <details>
        <summary>Enter coordinates instead</summary>
        <label>
          Latitude (40–58°N)
          <input type="number" min="40" max="58" step="any" value={lat} onChange={(e) => setLat(e.target.value)} />
        </label>
        <label>
          Longitude (157–173°W; enter west degrees)
          <input type="number" min="157" max="173" step="any" value={lon} onChange={(e) => setLon(e.target.value)} />
        </label>
        {!valid && <small>Enter a latitude from 40–58°N and west longitude from 157–173°.</small>}
        <button type="button" className="secondary-button" disabled={!valid} onClick={() => onSet({ lat: Number(lat), lng: -Math.abs(Number(lon)) })}>
          Use coordinates
        </button>
      </details>
    </div>
  )
}

export default function MissionPanel(props) {
  const {
    start, goal, goalType, onGoalTypeChange, oxygenHours, onOxygenChange,
    batteryWh, onBatteryChange, localTimeH, onTimeChange, avoid,
    onAvoidToggle, onEditPoint, onSetPoint, onReset, onPlanRoute,
    route, routeLoading, routeError, sourceMode,
  } = props
  const [internalStep, setInternalStep] = useState(route ? 'result' : 'gear')
  const step = props.step || internalStep
  const setStep = props.onStepChange || setInternalStep
  const [custom, setCustom] = useState(false)
  const validSupplies = Number(oxygenHours) > 0 && Number(oxygenHours) <= 1000 && Number(batteryWh) > 0 && Number(batteryWh) <= 1e7
  const ready = start && (goalType === 'ice' || goal) && validSupplies
  const metrics = route?.metrics
  const oxygenLeft = Number.isFinite(metrics?.oxygen_remaining_hours) ? Math.max(0, (metrics.oxygen_remaining_hours / Number(oxygenHours)) * 100) : null
  const batteryLeft = Number.isFinite(metrics?.battery_remaining_wh) ? Math.max(0, (metrics.battery_remaining_wh / Number(batteryWh)) * 100) : null
  const status = route?.status
  const verdict = tripVerdict(status)
  const retryWithMoreSupplies = () => {
    const oxygen = String(Math.min(1000, Number(oxygenHours) * 1.25))
    const battery = String(Math.min(1e7, Number(batteryWh) * 1.25))
    onOxygenChange(oxygen)
    onBatteryChange(battery)
    onPlanRoute({ oxygenHours: oxygen, batteryWh: battery })
  }
  const applyPreset = (id) => {
    const preset = presets[id]
    onOxygenChange(String(preset.oxygen))
    onBatteryChange(String(preset.battery))
    setCustom(false)
  }
  const reasons = {
    no_feasible_route: 'The terrain rules, destination and round-trip reserve did not yield a route.',
    search_label_limit: 'The search reached its computation limit; a feasible route has not been established.',
  }
  const reason = reasons[route?.reason] || (route?.reason ? route.reason.replaceAll('_', ' ') : '')

  return (
    <section className="panel-section mission-form" aria-labelledby="mission-title">
      {step === 'gear' ? (
        <>
          <h2 id="mission-title">Choose your gear</h2>
          <Point key={`start-${start?.lat}-${start?.lng}`} title="A · You are here" point={start} onEdit={() => onEditPoint('start')} onSet={(p) => onSetPoint('start', p)} />
          <label htmlFor="destination-type">Destination</label>
          <select id="destination-type" value={goalType} onChange={(e) => onGoalTypeChange(e.target.value)}>
            <option value="ice">Find nearby strong ice evidence</option>
            <option value="manual">I’ll pick on the map</option>
          </select>
          {goalType === 'ice' ? <p className="muted-copy">B will appear after you check the trip. Ice evidence is not a confirmed accessible deposit.</p> : <Point key={`goal-${goal?.lat}-${goal?.lng}`} title="B · Destination" point={goal} onEdit={() => onEditPoint('goal')} onSet={(p) => onSetPoint('goal', p)} />}
          <fieldset className="gear-presets">
            <legend>Trip supplies</legend>
            {Object.entries(presets).map(([id, preset]) => (
              <button type="button" key={id} className="secondary-button" aria-pressed={Number(oxygenHours) === preset.oxygen && Number(batteryWh) === preset.battery} onClick={() => applyPreset(id)}>
                {preset.label}<small title={`${preset.battery} Wh battery capacity`}>{preset.oxygen} hours of air · {id === 'short' ? 'smaller' : id === 'standard' ? 'standard' : 'larger'} battery</small>
              </button>
            ))}
          </fieldset>
          <details open={custom} onToggle={(e) => setCustom(e.currentTarget.open)}>
            <summary>Customize supplies</summary>
            <div className="supplies-grid">
              <label>Oxygen: hours of air<input type="number" min="0.1" max="1000" step="0.1" value={oxygenHours} onChange={(e) => onOxygenChange(e.target.value)} /></label>
              <label>Battery (Wh)<input type="number" min="1" max="10000000" value={batteryWh} onChange={(e) => onBatteryChange(e.target.value)} /></label>
            </div>
          </details>
          <details>
            <summary>Advanced planning settings</summary>
            <label>Time of day<select value={localTimeH} onChange={(e) => onTimeChange(e.target.value)}>{[0, 6, 12, 18].map((h) => <option key={h} value={h}>{({0:'Night',6:'Morning',12:'Midday',18:'Evening'})[h]}</option>)}</select></label>
            <p className="muted-copy">Static climate scenario, not current weather or a forecast. Conditions do not evolve during the trip.</p>
            <fieldset><legend>Exclude challenging conditions</legend>{[['steep', 'Steep slopes'], ['dust', 'High dust'], ['cold', 'Cold conditions'], ['unknown_thermal', 'No observed temperature']].map(([id, label]) => <label className="check-label" key={id}><input type="checkbox" checked={avoid.includes(id)} onChange={() => onAvoidToggle(id)} />{label}</label>)}</fieldset>
          </details>
          <button type="button" className="primary-button plan-button" disabled={!ready || routeLoading} onClick={() => { onPlanRoute(); setStep('result') }}>{routeLoading ? 'Checking the trip…' : 'Check the trip'}</button>
          {!ready && <p className="muted-copy" role="status">{!start ? 'Choose a starting base first.' : goalType === 'manual' && !goal ? 'Choose destination B on the map.' : 'Enter positive oxygen and battery supplies.'}</p>}
          {routeError && <p className="inline-error" role="alert">{routeError}</p>}
          <button type="button" className="text-button" onClick={onReset}>Reset mission</button>
        </>
      ) : (
        <section className={`mission-result result-${status || 'pending'}`} aria-live="polite" aria-labelledby="result-title">
          <h2 id="mission-title">Trip result</h2>
          {routeLoading && <p role="status">Checking the route and supplies…</p>}
          {routeError && <p className="inline-error" role="alert">{routeError}</p>}
          {route && <>
            <div className={`result-verdict status-${verdict.tone}`}>
              <span className="verdict-icon" aria-hidden="true">{verdict.icon}</span>
              <div><h3 id="result-title">{verdict.title}</h3><p>{verdict.text}</p></div>
            </div>
            <p className="muted-copy">{sourceMode === 'demo' ? 'Illustrative sample calculation.' : 'Planner estimate.'} These results do not establish astronaut safety.</p>
            <dl className="result-metrics">
              {Number.isFinite(metrics?.distance_km) && <div><dt>Whole trip</dt><dd>{number(metrics.distance_km)} km · about {duration(metrics.hours)}</dd></div>}
              {oxygenLeft !== null && <div><dt>Oxygen left on return</dt><dd>{oxygenLeft.toFixed(0)}%</dd><progress aria-label="Oxygen remaining" max="100" value={Math.min(100, oxygenLeft)} /></div>}
              {batteryLeft !== null && <div><dt>Battery left on return</dt><dd>{batteryLeft.toFixed(0)}%</dd><progress aria-label="Battery remaining" max="100" value={Math.min(100, batteryLeft)} /></div>}
              {Number.isFinite(metrics?.maximum_slope_deg) && <div><dt>Steepest part</dt><dd>{metrics.maximum_slope_deg < 5 ? 'Gentle' : metrics.maximum_slope_deg < 10 ? 'Moderate' : 'Steep'}</dd></div>}
            </dl>
            {reason && <div><strong>Why</strong><p>{reason}</p></div>}
            {status === 'ok' && <p>The return retraces the outbound path. Ice evidence is not a confirmed accessible deposit.</p>}
            {route.turn_back?.abort_points?.length > 0 && <details><summary>Turn back by</summary><ul>{route.turn_back.abort_points.map((p, i) => <li key={i}>Checkpoint {i + 1}: {number(p.elapsed_hours)} h after departure</li>)}</ul><p>Calculated checkpoints are not confirmed shelters.</p></details>}
            {status !== 'ok' && <div className="result-actions"><button type="button" className="secondary-button" disabled={routeLoading} onClick={retryWithMoreSupplies}>Add 25% supplies and retry</button><p className="muted-copy">A retry with more supplies may help, but does not address terrain or search limits.</p></div>}
            <p>{route.example_note || 'Terrain and ice observations are combined with climate models. Radiation uses an extrapolated regional reference; shelters are unverified.'}</p>
          </>}
          {!route && !routeLoading && <p>Check a trip to see its result here.</p>}
          <div className="result-actions">
            <button type="button" className="secondary-button" onClick={() => setStep('gear')}>Change plan</button>
            {route && <button type="button" className="text-button print-button" onClick={() => window.print()}>Print briefing</button>}
          </div>
          <button type="button" className="text-button" onClick={onReset}>Reset mission</button>
        </section>
      )}
    </section>
  )
}
