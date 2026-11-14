import test from 'node:test'
import assert from 'node:assert/strict'
import { routeRequest, normalizeSites, normalizeRoute } from './contract.js'
import { exampleRoute } from './examples.js'

test('route requests convert lng to lon and keep ice and manual goals exclusive', () => {
  const start = { lat: 12, lng: 34 }
  const ice = routeRequest({
    start,
    goal: { lat: 56, lng: 78 },
    oxygenHours: '10',
    batteryWh: '200',
    goalType: 'ice',
  })
  assert.deepEqual(ice.start, { lat: 12, lon: 34 })
  assert.equal(ice.goal_type, 'ice')
  assert.equal(ice.min_goal_distance_km, 3)
  assert.equal('goal' in ice, false)

  const manual = routeRequest({
    start,
    goal: { lat: 56, lng: 78 },
    oxygenHours: 10,
    batteryWh: 200,
    goalType: 'manual',
  })
  assert.deepEqual(manual.start, { lat: 12, lon: 34 })
  assert.deepEqual(manual.goal, { lat: 56, lon: 78 })
  assert.equal('goal_type' in manual, false)
  assert.equal('min_goal_distance_km' in manual, false)
})

test('route requests include budgets and return reserve fields', () => {
  const request = routeRequest({
    start: { lat: 1, lng: 2 },
    goal: { lat: 3, lng: 4 },
    oxygenHours: '8',
    batteryWh: '500',
  })
  assert.equal(request.oxygen_hours, 8)
  assert.equal(request.battery_wh, 500)
  assert.equal(request.return_to_start, true)
  assert.equal(request.reserve_fraction, 0.2)
})

test('site normalization ranks backend candidates, scales scores, and converts longitude', () => {
  const normalized = normalizeSites({
    weights: { ice: 0.4, slope: 0.6 },
    sites: [
      {
        position: { lat: 10, lon: 210 },
        score: 0.876,
        ice_consistency: 0.72,
        slope_deg: 5.5,
      },
      {
        position: { lat: -2, lon: -40 },
        score: 0.4,
        ice_consistency: 0.3,
        slope_deg: 2,
      },
    ],
  })
  assert.equal(normalized.sites[0].rank, 1)
  assert.equal(normalized.sites[0].score, 88)
  assert.equal(normalized.sites[0].lng, -150)
  assert.equal(normalized.sites[1].rank, 2)
  assert.equal(normalized.sites[1].score, 40)
  assert.equal(normalized.sites[1].lng, -40)
})

test('route normalization converts GeoJSON lon-lat coordinates into lat-lon path points', () => {
  const normalized = normalizeRoute({
    route: {
      geojson: {
        geometry: {
          coordinates: [
            [210, 12],
            [-40, -2],
          ],
        },
      },
    },
  })
  assert.deepEqual(normalized.path, [
    [12, -150],
    [-2, -40],
  ])
  assert.equal(normalized.sourceMode, 'live')
})

test('an infeasible example route has no path', () => {
  const result = exampleRoute({
    start: { lat: 0, lng: 0 },
    goalType: 'ice',
    oxygenHours: 0.01,
    batteryWh: 1,
  })
  assert.equal(result.status, 'infeasible')
  assert.deepEqual(result.path, [])
})

test('an ok sample round trip uses reported hours as oxygen consumption and stays within usable budgets', () => {
  const result = exampleRoute({
    start: { lat: 46.32, lng: -165.18 },
    goalType: 'ice',
    oxygenHours: 8,
    batteryWh: 1000,
  })
  assert.equal(result.status, 'ok')
  assert.ok(
    Math.abs(
      result.metrics.hours -
        (result.budget.oxygen_hours - result.metrics.oxygen_remaining_hours),
    ) < 1e-12,
  )
  assert.ok(
    result.metrics.hours <=
      result.budget.oxygen_hours * (1 - result.budget.reserve_fraction),
  )
  assert.ok(
    result.metrics.battery_wh <=
      result.budget.battery_wh * (1 - result.budget.reserve_fraction),
  )
})
