import { useState } from 'react'
const number = (value) =>
  Number.isFinite(value) ? value.toFixed(2) : 'Not available'
function Point({ title, point, onEdit, onSet }) {
  const [lat, setLat] = useState(point?.lat ?? '')
  const [lon, setLon] = useState(point?.lng ?? '')
  const valid =
    lat !== '' &&
    lon !== '' &&
    Number(lat) >= 40 &&
    Number(lat) <= 58 &&
    Number(lon) >= -173 &&
    Number(lon) <= -157
  return (
    <div className="mission-point">
      <strong>{title}</strong>
      <p>
        {point
          ? point.name || 'Selected map point'
          : 'Choose a point to continue'}
      </p>
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
          <input
            type="number"
            min="40"
            max="58"
            step="any"
            value={lat}
            onChange={(e) => setLat(e.target.value)}
          />
        </label>
        <label>
          Longitude (−173 to −157°E)
          <input
            type="number"
            min="-173"
            max="-157"
            step="any"
            value={lon}
            onChange={(e) => setLon(e.target.value)}
          />
        </label>
        <button
          type="button"
          className="secondary-button"
          disabled={!valid}
          onClick={() => onSet({ lat: Number(lat), lng: Number(lon) })}
        >
          Use coordinates
        </button>
      </details>
    </div>
  )
}
export default function MissionPanel(props) {
  const {
    start,
    goal,
    goalType,
    onGoalTypeChange,
    oxygenHours,
    onOxygenChange,
    batteryWh,
    onBatteryChange,
    localTimeH,
    onTimeChange,
    avoid,
    onAvoidToggle,
    onEditPoint,
    onSetPoint,
    onReset,
    onPlanRoute,
    route,
    routeLoading,
    routeError,
    sourceMode,
  } = props
  const validSupplies =
    Number(oxygenHours) > 0 &&
    Number(oxygenHours) <= 1000 &&
    Number(batteryWh) > 0 &&
    Number(batteryWh) <= 1e7
  const ready = start && (goalType === 'ice' || goal) && validSupplies
  const metrics = route?.metrics
  const reasons = {
    no_feasible_route:
      'No route was found that satisfies the selected terrain rules, round-trip supplies and reserve. Try a closer destination, increase supplies, or review the exclusions.',
    search_label_limit:
      'The search reached its computation limit. A feasible route has not been established.',
  }
  const reason =
    reasons[route?.reason] ||
    (route?.reason ? route.reason.replaceAll('_', ' ') : '')
  return (
    <section
      className="panel-section mission-form"
      aria-labelledby="mission-title"
    >
      <p className="eyebrow">2. Plan a walking round trip</p>
      <h2 id="mission-title">Can we get there and back?</h2>
      <Point
        key={`start-${start?.lat}-${start?.lng}`}
        title="A · Starting base"
        point={start}
        onEdit={() => onEditPoint('start')}
        onSet={(p) => onSetPoint('start', p)}
      />
      <label htmlFor="destination-type">Destination</label>
      <select
        id="destination-type"
        value={goalType}
        onChange={(e) => onGoalTypeChange(e.target.value)}
      >
        <option value="ice">Find nearby strong ice evidence</option>
        <option value="manual">Choose a destination on the map</option>
      </select>
      {goalType === 'ice' ? (
        <p className="muted-copy">
          Search for reachable cells with an ice consistency index ≥ 0.75, at
          least 3 km away. This indicates evidence, not a confirmed accessible
          ice deposit.
        </p>
      ) : (
        <Point
          key={`goal-${goal?.lat}-${goal?.lng}`}
          title="B · Destination"
          point={goal}
          onEdit={() => onEditPoint('goal')}
          onSet={(p) => onSetPoint('goal', p)}
        />
      )}
      <div className="supplies-grid">
        <label>
          Oxygen supply (Earth hours)
          <input
            type="number"
            min="0.1"
            max="1000"
            step="0.1"
            value={oxygenHours}
            onChange={(e) => onOxygenChange(e.target.value)}
          />
        </label>
        <label>
          Battery capacity (Wh)
          <input
            type="number"
            min="1"
            max="10000000"
            value={batteryWh}
            onChange={(e) => onBatteryChange(e.target.value)}
          />
        </label>
      </div>
      <p className="reserve-note">
        Includes the walk back to A, plus a 20% oxygen and battery reserve.
        These supplies and walking assumptions are illustrative.
      </p>
      <details>
        <summary>Advanced planning settings</summary>
        <label>
          Local solar time
          <select
            value={localTimeH}
            onChange={(e) => onTimeChange(e.target.value)}
          >
            {[0, 6, 12, 18].map((h) => (
              <option key={h} value={h}>
                {String(h).padStart(2, '0')}:00
              </option>
            ))}
          </select>
        </label>
        <p className="muted-copy">
          Static Mars Climate Database scenario at solar longitude 90°, not
          current weather or a forecast. Conditions do not evolve during the
          trip.
        </p>
        <fieldset>
          <legend>Exclude challenging conditions</legend>
          {[
            ['steep', 'Steep slopes'],
            ['dust', 'High atmospheric dust'],
            ['cold', 'Cold conditions'],
            ['unknown_thermal', 'Areas without observed temperature'],
          ].map(([id, label]) => (
            <label className="check-label" key={id}>
              <input
                type="checkbox"
                checked={avoid.includes(id)}
                onChange={() => onAvoidToggle(id)}
              />
              {label}
            </label>
          ))}
          <label className="check-label">
            <input type="checkbox" disabled />
            High radiation (unavailable)
          </label>
          <p className="muted-copy">
            No local radiation variation or validated shelter protection is
            available. Sample mode does not evaluate these filters.
          </p>
        </fieldset>
      </details>
      <button
        type="button"
        className="primary-button plan-button"
        disabled={!ready || routeLoading}
        onClick={onPlanRoute}
      >
        {routeLoading ? 'Checking route and supplies…' : 'Check round trip'}
      </button>
      {!ready && (
        <p className="muted-copy" role="status">
          {!start
            ? 'First choose a starting base from the list or map.'
            : goalType === 'manual' && !goal
              ? 'Choose destination B on the map.'
              : 'Enter positive oxygen and battery supplies within the displayed limits.'}
        </p>
      )}
      <button type="button" className="text-button" onClick={onReset}>
        Reset mission
      </button>
      {routeError && (
        <p className="inline-error" role="alert">
          {routeError}
        </p>
      )}
      {route && (
        <section
          className={`mission-result result-${route.status}`}
          aria-live="polite"
          aria-labelledby="result-title"
        >
          <p className="eyebrow">
            3. Review before departure ·{' '}
            {sourceMode === 'demo' ? 'sample calculation' : 'planner result'}
          </p>
          <button
            type="button"
            className="text-button print-button"
            onClick={() => window.print()}
          >
            Print mission briefing
          </button>
          <h3 id="result-title">
            {route.status === 'ok'
              ? 'Round trip fits the configured limits'
              : route.status === 'search_limit'
                ? 'Search incomplete — no trip confirmed'
                : 'No feasible round trip found — do not start'}
          </h3>
          <p>
            Starting point: {start?.lat.toFixed(3)}°N,{' '}
            {Math.abs(start?.lng).toFixed(3)}°{start?.lng < 0 ? 'W' : 'E'}.
            Scenario time: {localTimeH}:00 local solar time.
          </p>
          {reason && <p>{reason}</p>}
          {metrics && (
            <dl className="result-metrics">
              <div>
                <dt>Whole trip distance</dt>
                <dd>{number(metrics.distance_km)} km</dd>
              </div>
              <div>
                <dt>Travel time / oxygen used</dt>
                <dd>{number(metrics.hours)} h</dd>
              </div>
              <div>
                <dt>Oxygen left on return</dt>
                <dd>{number(metrics.oxygen_remaining_hours)} h</dd>
              </div>
              <div>
                <dt>Battery used</dt>
                <dd>{number(metrics.battery_wh)} Wh</dd>
              </div>
              <div>
                <dt>Battery left on return</dt>
                <dd>{number(metrics.battery_remaining_wh)} Wh</dd>
              </div>
              {Number.isFinite(metrics.maximum_slope_deg) && (
                <div>
                  <dt>Steepest traversed slope</dt>
                  <dd>{number(metrics.maximum_slope_deg)}°</dd>
                </div>
              )}
            </dl>
          )}
          {route.status === 'ok' && (
            <p>
              The return retraces the outbound path. Keep at least{' '}
              {number(route.budget?.oxygen_hours * 0.2)} h oxygen and{' '}
              {number(route.budget?.battery_wh * 0.2)} Wh battery in reserve.
            </p>
          )}
          <p>
            {route.example_note ||
              'Terrain and ice observations are combined with climate models. Radiation uses an extrapolated regional reference; shelters are unverified. These estimates do not establish astronaut safety.'}
          </p>
          {route.turn_back?.abort_points?.length > 0 && (
            <details>
              <summary>
                Return checkpoints ({route.turn_back.abort_points.length})
              </summary>
              <p>
                Calculated outbound checks reserve enough supplies to reverse
                the route. These are not confirmed shelters.
              </p>
              <ul>
                {route.turn_back.abort_points.map((p, i) => (
                  <li key={i}>
                    Checkpoint {i + 1}: {number(p.elapsed_hours)} h after
                    departure
                  </li>
                ))}
              </ul>
            </details>
          )}
        </section>
      )}
    </section>
  )
}
