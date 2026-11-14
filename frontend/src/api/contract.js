export function routeRequest({
  start,
  goal,
  goalType = 'ice',
  oxygenHours,
  batteryWh,
  localTimeH = 6,
  avoid = [],
}) {
  const position = (point) => ({ lat: point.lat, lon: point.lng })
  return {
    start: position(start),
    ...(goalType === 'ice'
      ? { goal_type: 'ice', min_goal_distance_km: 3 }
      : { goal: position(goal) }),
    oxygen_hours: Number(oxygenHours),
    battery_wh: Number(batteryWh),
    local_time_h: Number(localTimeH),
    return_to_start: true,
    reserve_fraction: 0.2,
    mode: 'scenario',
    avoid,
  }
}
export function normalizeSites(data) {
  return {
    ...data,
    sites: (data.sites || []).map((site, i) => ({
      ...site,
      id: `site-${i + 1}`,
      rank: i + 1,
      name: `Candidate base ${i + 1}`,
      lat: site.position.lat,
      lng:
        site.position.lon > 180 ? site.position.lon - 360 : site.position.lon,
      score: Math.round(site.score * 100),
      reasons: [
        `Ice evidence index ${site.ice_consistency.toFixed(2)}; not a confirmed deposit`,
        `Regional terrain slope ${site.slope_deg.toFixed(1)}°`,
        ...Object.entries(data.weights || {}).map(
          ([key, weight]) =>
            `${key}: ${Math.round(weight * 100)}% of ranking weight`,
        ),
        'Radiation shielding is excluded from this ranking.',
      ],
    })),
  }
}
export function normalizeRoute(data) {
  const points = data.route?.geojson?.geometry?.coordinates
  const path = points
    ? points.map(([lon, lat]) => [lat, lon > 180 ? lon - 360 : lon])
    : []
  return {
    ...data,
    path,
    sourceMode: 'live',
    metrics: data.metrics
      ? {
          ...data.metrics,
          oxygen_remaining_hours: data.budget.oxygen_hours - data.metrics.hours,
          battery_remaining_wh:
            data.budget.battery_wh - data.metrics.battery_wh,
        }
      : null,
  }
}
