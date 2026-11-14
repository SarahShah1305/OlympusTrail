import { normalizeRoute, normalizeSites, routeRequest } from './contract.js'
import { exampleRoute, exampleSites } from './examples.js'
const apiUrl = (import.meta.env.VITE_API_URL || '').replace(/\/$/, '')
export async function request(path, options = {}) {
  let response
  try {
    response = await fetch(`${apiUrl}${path}`, {
      ...options,
      headers: { 'Content-Type': 'application/json' },
      signal: AbortSignal.timeout(60000),
    })
  } catch {
    throw new Error(
      'The planner is unavailable or took too long. Retry, or explicitly open the sample demonstration.',
    )
  }
  let data
  try {
    data = await response.json()
  } catch {
    throw new Error(
      'The planner did not return a readable result. No sample result has been substituted.',
    )
  }
  if (!response.ok)
    throw new Error(
      typeof data.detail === 'string'
        ? data.detail
        : `The planner rejected this request (${response.status}). Check the selected points and supplies.`,
    )
  return data
}
export async function getSites(sourceMode = 'live') {
  if (sourceMode === 'demo') return { sites: exampleSites }
  return normalizeSites(await request('/sites?min_separation_km=60'))
}
export async function planRoute(options) {
  if (options.sourceMode === 'demo') return exampleRoute(options)
  return normalizeRoute(
    await request('/route', {
      method: 'POST',
      body: JSON.stringify(routeRequest(options)),
    }),
  )
}
