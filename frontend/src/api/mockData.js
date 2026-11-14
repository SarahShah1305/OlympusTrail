const delay = (duration = 320) =>
  new Promise((resolve) => window.setTimeout(resolve, duration))

export const mockSites = [
  {
    id: 'site-01',
    rank: 1,
    name: 'Central basin bench',
    lat: 46.32,
    lng: -165.18,
    score: 94,
    reasons: [
      'Preview score favors shallow-ice access',
      'Preview score favors gentle regional slope',
      'Preview score favors daylight potential',
      'Illustrative terrain-shielding estimate',
    ],
  },
  {
    id: 'site-02',
    rank: 2,
    name: 'Northern plain',
    lat: 46.68,
    lng: -163.92,
    score: 89,
    reasons: [
      'Preview score favors shallow-ice access',
      'Preview score favors level terrain',
      'Preview score favors daylight potential',
      'Illustrative radiation estimate',
    ],
  },
  {
    id: 'site-03',
    rank: 3,
    name: 'Western basin edge',
    lat: 45.72,
    lng: -167.1,
    score: 85,
    reasons: [
      'Preview score favors shallow-ice access',
      'Preview score favors gentle regional slope',
      'Preview score favors daylight potential',
      'Illustrative terrain-shielding estimate',
    ],
  },
  {
    id: 'site-04',
    rank: 4,
    name: 'Eastern terrace',
    lat: 46.14,
    lng: -161.96,
    score: 81,
    reasons: [
      'Preview score favors shallow-ice access',
      'Preview score favors gentle regional slope',
      'Preview score favors daylight potential',
      'Illustrative dust exposure estimate',
    ],
  },
  {
    id: 'site-05',
    rank: 5,
    name: 'Southern ridge saddle',
    lat: 41.88,
    lng: -169.28,
    score: 76,
    reasons: [
      'Preview score favors shallow-ice access',
      'Preview score favors level terrain',
      'Preview score favors daylight potential',
      'Illustrative radiation estimate',
    ],
  },
]

const distanceBetween = (start, goal) => {
  const latKm = (goal.lat - start.lat) * 59.3
  const lngKm =
    (goal.lng - start.lng) * 59.3 * Math.cos((start.lat * Math.PI) / 180)
  return Math.sqrt(latKm ** 2 + lngKm ** 2)
}

export async function mockPlanRoute({
  start,
  goal,
  oxygenHours = 4,
  avoid = [],
}) {
  await delay()
  const distance = Math.max(0.8, distanceBetween(start, goal) * 1.24)
  const duration = Number((distance / 4.1 + (avoid.length ? 0.2 : 0)).toFixed(1))
  const status =
    oxygenHours < duration * 1.25
      ? 'turn_back'
      : oxygenHours < duration * 1.65
        ? 'reroute'
        : 'ok'
  const bend = 0.018 + avoid.length * 0.004
  const path = [
    [start.lat, start.lng],
    [
      start.lat + (goal.lat - start.lat) * 0.28 + bend,
      start.lng + (goal.lng - start.lng) * 0.28 - bend,
    ],
    [
      start.lat + (goal.lat - start.lat) * 0.58 - bend * 0.65,
      start.lng + (goal.lng - start.lng) * 0.58 + bend,
    ],
    [
      start.lat + (goal.lat - start.lat) * 0.82 + bend * 0.4,
      start.lng + (goal.lng - start.lng) * 0.82,
    ],
    [goal.lat, goal.lng],
  ]
  const message =
    status === 'turn_back'
      ? 'Oxygen reserve is below the modeled return threshold. Turn back at the marked abort point.'
      : status === 'reroute'
        ? 'The direct route is tight on oxygen. Use the marked sheltered reroute and reassess at the abort point.'
        : 'Route is within the submitted oxygen budget. Continue to monitor reserves at the marked shelter.'
  const abortPoint = {
    lat: path[2][0],
    lng: path[2][1],
    label: 'Abort point · midpoint check',
  }
  return {
    status,
    path,
    distance_km: Number(distance.toFixed(1)),
    duration_h: duration,
    oxygen_used_h: Number((duration * 1.45).toFixed(1)),
    oxygen_total_h: Number(oxygenHours),
    battery_used_pct: Math.min(92, Math.round(24 + distance * 1.6)),
    abort_points: [abortPoint],
    shelters: [],
    hazards: avoid.map((type) => ({
      type,
      label: `Modeled ${type.replaceAll('_', ' ')} exposure`,
    })),
    message,
    ...(status === 'reroute'
      ? {
          alternative_path: [
            [start.lat, start.lng],
            [path[1][0] + bend * 0.8, path[1][1] + bend],
            [path[2][0] + bend, path[2][1] + bend * 0.8],
            [goal.lat, goal.lng],
          ],
        }
      : {}),
  }
}

export async function mockSendChat(message, context = {}) {
  const question = message.toLowerCase()
  const sites = context.sites?.length ? context.sites : mockSites
  const asksForRoute = /route|safest|oxygen|battery|travel|go to|reach/.test(
    question,
  )

  if (/\b(slope|steepness|gradient)\b/.test(question)) {
    return {
      reply: 'Slope measures how steep the ground is, in degrees. Arcadia’s MOLA slope layer ranges from about 0° to 10.56° on a 3 km grid, so it describes regional terrain, not rover-scale hazards.',
    }
  }

  if (asksForRoute) {
    const start = context.start || sites[0]
    const goal = context.goal || sites[1]
    const oxygenHours =
      Number(question.match(/(\d+(?:\.\d+)?)\s*(?:hours?|hrs?|h)\b/)?.[1]) ||
      Number(context.oxygenHours) ||
      4
    const route = await mockPlanRoute({
      start,
      goal,
      oxygenHours,
      avoid: context.avoid || [],
    })
    return {
      route,
      reply: `For ${start.name || 'point A'} to ${goal.name || 'point B'}, the planner returns ${route.status.replace('_', ' ')}: ${route.distance_km} km, about ${route.duration_h} h, and ${route.oxygen_used_h} h of modeled oxygen use from a ${route.oxygen_total_h} h budget. ${route.message}`,
    }
  }

  if (/ice|base|site|colony/.test(question)) {
    const best = sites[0]
    return {
      reply: `The current preview site ranking puts ${best.name} at rank ${best.rank} with a score of ${best.score}/100. Its listed factors are ${best.reasons.join('; ')}.`,
    }
  }

  await delay()
  return {
    reply:
      'I can explain the ranked base sites or ask the route planner about oxygen, battery, hazards, or the safest route. This preview uses the configured sample planner and is not operational guidance.',
  }
}
