// Examples are never substituted for failed planner requests.
export const exampleSites = [
  {
    id: 'example-1',
    rank: 1,
    name: 'Example starting base',
    lat: 46.32,
    lng: -165.18,
    score: '—',
    reasons: [
      'Illustrative location only. No site ranking or ice deposit has been calculated.',
    ],
  },
]
export function exampleRoute({
  start,
  goal,
  goalType,
  oxygenHours,
  batteryWh,
}) {
  const end =
    goalType === 'ice' ? { lat: start.lat, lng: start.lng + 0.073 } : goal
  const r = (d) => (d * Math.PI) / 180
  const a =
    Math.sin(r(end.lat - start.lat) / 2) ** 2 +
    Math.cos(r(start.lat)) *
      Math.cos(r(end.lat)) *
      Math.sin(r(end.lng - start.lng) / 2) ** 2
  const distance = 2 * 3396.19 * 2 * Math.asin(Math.sqrt(Math.min(1, a)))
  const hours = distance / 3
  const energy = hours * 100 + distance * 10
  const fits =
    hours <= Number(oxygenHours) * 0.8 && energy <= Number(batteryWh) * 0.8
  return {
    status: fits ? 'ok' : 'infeasible',
    sourceMode: 'demo',
    path: fits
      ? [
          [start.lat, start.lng],
          [end.lat, end.lng],
          [start.lat, start.lng],
        ]
      : [],
    reason: fits
      ? null
      : 'The sample round trip exceeds the usable supplies after keeping a 20% reserve.',
    budget: {
      oxygen_hours: Number(oxygenHours),
      battery_wh: Number(batteryWh),
      reserve_fraction: 0.2,
      return_to_start: true,
    },
    metrics: {
      distance_km: distance,
      hours,
      battery_wh: energy,
      oxygen_remaining_hours: Number(oxygenHours) - hours,
      battery_remaining_wh: Number(batteryWh) - energy,
    },
    example_note:
      'Illustrative straight-line round trip at 3 km/h, 100 W plus 10 Wh/km. No terrain, ice, dust, temperature or avoidance analysis. The example target is not verified ice.',
  }
}
