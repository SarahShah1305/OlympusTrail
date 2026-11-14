import { mockPlanRoute, mockSendChat, mockSites } from './mockData'

const apiUrl =
  import.meta.env.VITE_API_URL ||
  (import.meta.env.DEV ? 'http://localhost:8000' : '')
const useMock =
  (import.meta.env.VITE_USE_MOCK || (import.meta.env.PROD ? 'false' : 'true')).toLowerCase() !==
  'false'

async function request(path, options = {}, fallback) {
  if (useMock) return fallback()

  try {
    const response = await fetch(`${apiUrl}${path}`, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
    })
    if (!response.ok) {
      throw new Error(`API request failed (${response.status} ${response.statusText})`)
    }
    return await response.json()
  } catch (error) {
    console.warn(`API ${path} failed; using labeled preview data.`, error)
    return fallback()
  }
}

export const isMockMode = () => useMock

export function getSites() {
  return request('/sites', {}, async () => {
    await new Promise((resolve) => window.setTimeout(resolve, 320))
    return { sites: mockSites }
  })
}

export function planRoute({ start, goal, oxygenHours, avoid = [] }) {
  return request(
    '/route',
    {
      method: 'POST',
      body: JSON.stringify({
        start,
        goal,
        oxygen_hours: oxygenHours,
        avoid,
      }),
    },
    () => mockPlanRoute({ start, goal, oxygenHours, avoid }),
  )
}

export function sendChat(message, context) {
  return request(
    '/chat',
    {
      method: 'POST',
      body: JSON.stringify({ message, context }),
    },
    () => mockSendChat(message, context),
  )
}
