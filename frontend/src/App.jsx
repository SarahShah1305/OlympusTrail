import { useCallback, useEffect, useState } from 'react'
import { getSites, planRoute, sendChat } from './api/client'
import { config, layerDefinitions } from './config'
import AskPanel from './components/AskPanel'
import LayerPanel from './components/LayerPanel'
import MapView from './components/MapView'
import MissionPanel from './components/MissionPanel'
import TopBar from './components/TopBar'

const initialMessages = [
  {
    id: 'welcome',
    role: 'assistant',
    text: 'I can help compare candidate sites or check a route against its oxygen budget. Ask a question to get started.',
  },
]

function makeMessage(role, text) {
  return { id: `${Date.now()}-${Math.random()}`, role, text }
}

export default function App() {
  const [mode, setMode] = useState('sites')
  const [mobilePanel, setMobilePanel] = useState('map')
  const [overlayOpacity, setOverlayOpacity] = useState(0.65)
  const [activeLayers, setActiveLayers] = useState(
    Object.fromEntries(
      layerDefinitions.map((layer) => [
        layer.id,
        layer.id === 'slope' || layer.id === 'ice',
      ]),
    ),
  )
  const [layerMetadata, setLayerMetadata] = useState(null)
  const [layerMetadataError, setLayerMetadataError] = useState('')
  const [sites, setSites] = useState([])
  const [sitesLoading, setSitesLoading] = useState(true)
  const [sitesError, setSitesError] = useState('')
  const [start, setStart] = useState(null)
  const [goal, setGoal] = useState(null)
  const [oxygenHours, setOxygenHours] = useState('4')
  const [avoid, setAvoid] = useState([])
  const [route, setRoute] = useState(null)
  const [askRoute, setAskRoute] = useState(null)
  const [routeLoading, setRouteLoading] = useState(false)
  const [routeError, setRouteError] = useState('')
  const [messages, setMessages] = useState(initialMessages)
  const [chatLoading, setChatLoading] = useState(false)
  const [chatError, setChatError] = useState('')
  const [selectedSite, setSelectedSite] = useState(null)

  useEffect(() => {
    let active = true
    fetch(`${import.meta.env.BASE_URL}layers/layers.json`)
      .then((response) => {
        if (!response.ok) throw new Error(`Layer metadata request failed (${response.status}).`)
        return response.json()
      })
      .then((metadata) => {
        if (active) setLayerMetadata(metadata)
      })
      .catch((error) => {
        console.error('Unable to load source layer metadata.', error)
        if (active) setLayerMetadataError('Source layer metadata could not be loaded.')
      })
    return () => {
      active = false
    }
  }, [])

  useEffect(() => {
    let active = true
    getSites()
      .then((response) => {
        if (active) setSites(response.sites || [])
      })
      .catch((error) => {
        console.error('Unable to load candidate sites.', error)
        if (active) setSitesError('Candidate sites could not be loaded.')
      })
      .finally(() => {
        if (active) setSitesLoading(false)
      })
    return () => {
      active = false
    }
  }, [])

  const chooseMode = (nextMode) => {
    setMode(nextMode)
    if (nextMode === 'ask') setMobilePanel('mission')
    if (nextMode === 'route') setMobilePanel('map')
  }

  const handleMapClick = (point) => {
    setAskRoute(null)
    if (!start || goal) {
      setStart({ lat: point.lat, lng: point.lng })
      setGoal(null)
      setRoute(null)
    } else {
      setGoal({ lat: point.lat, lng: point.lng })
    }
  }

  const handleStartChange = (point) => {
    setStart(point)
    setRoute(null)
    setAskRoute(null)
  }
  const handleGoalChange = (point) => {
    setGoal(point)
    setRoute(null)
    setAskRoute(null)
  }

  const handleRoute = (result) => {
    setAskRoute(result)
    setRoute(null)
  }

  const getMapStart = () => start ? [start.lat, start.lng] : null

  const handlePlanRoute = async () => {
    if (!start || !goal) return
    setRouteLoading(true)
    setRouteError('')
    setAskRoute(null)
    try {
      const result = await planRoute({
        start,
        goal,
        oxygenHours: Number(oxygenHours),
        avoid,
      })
      setRoute(result)
    } catch (error) {
      console.error('Unable to plan route.', error)
      setRouteError('The route planner could not complete this request. Please try again.')
    } finally {
      setRouteLoading(false)
    }
  }

  const handleSendMessage = useCallback(async (text) => {
    const question = text.trim()
    if (!question) return
    setMessages((current) => [...current, makeMessage('user', question)])
    setChatLoading(true)
    setChatError('')
    try {
      const fallbackStart = sites[0] || { name: 'Point A', ...config.region, lat: config.region.center[0] - 0.04, lng: config.region.center[1] - 0.04 }
      const fallbackGoal = sites[1] || { name: 'Point B', lat: config.region.center[0] + 0.04, lng: config.region.center[1] + 0.04 }
      const response = await sendChat(question, {
        start: start || fallbackStart,
        goal: goal || fallbackGoal,
        oxygenHours: Number(oxygenHours),
        avoid,
        sites,
      })
      setMessages((current) => [...current, makeMessage('assistant', response.reply)])
      if (response.route) {
        if (!start) setStart(response.route.path?.length ? { lat: response.route.path[0][0], lng: response.route.path[0][1] } : fallbackStart)
        if (!goal) setGoal(response.route.path?.length ? { lat: response.route.path.at(-1)[0], lng: response.route.path.at(-1)[1] } : fallbackGoal)
        setRoute(response.route)
        setMode('route')
      }
    } catch (error) {
      console.error('Unable to send map question.', error)
      setChatError('The map guide could not answer. Check the connection and retry.')
    } finally {
      setChatLoading(false)
    }
  }, [sites, start, goal, oxygenHours, avoid])

  const toggleLayer = (id) => {
    setActiveLayers((current) => ({ ...current, [id]: !current[id] }))
  }

  const toggleAvoid = (id) => {
    setAvoid((current) => current.includes(id) ? current.filter((value) => value !== id) : [...current, id])
  }

  return (
    <div className={`app-shell mobile-view-${mobilePanel}`}>
      <TopBar
        mode={mode}
        onModeChange={chooseMode}
        mobilePanel={mobilePanel}
        onMobilePanelChange={setMobilePanel}
      />
      <main className="workspace">
        <LayerPanel
          activeLayers={activeLayers}
          onToggle={toggleLayer}
          opacity={overlayOpacity}
          onOpacityChange={setOverlayOpacity}
          layerMetadata={layerMetadata}
          layerMetadataError={layerMetadataError}
          sites={sites}
          loading={sitesLoading}
          error={sitesError}
          onSelectSite={(site) => {
            setSelectedSite(site)
            setMode('sites')
            setMobilePanel('map')
          }}
        />
        <MapView
          mode={mode}
          sites={sites}
          activeLayers={activeLayers}
          start={start}
          goal={goal}
          onMapClick={handleMapClick}
          onStartChange={handleStartChange}
          onGoalChange={handleGoalChange}
          route={askRoute ? { path: askRoute.path } : route}
          selectedSite={selectedSite}
          layerMetadata={layerMetadata}
          overlayOpacity={overlayOpacity}
        />
        {mode === 'ask' ? (
          <aside className="side-panel right-panel" aria-label="Ask the map">
            <AskPanel onRoute={handleRoute} getMapStart={getMapStart} />
          </aside>
        ) : (
          <MissionPanel
            mode={mode}
            route={route}
            start={start}
            goal={goal}
            oxygenHours={oxygenHours}
            onOxygenChange={setOxygenHours}
            avoid={avoid}
            onAvoidToggle={toggleAvoid}
            onPlanRoute={handlePlanRoute}
            routeLoading={routeLoading}
            routeError={routeError}
            messages={messages}
            onSendMessage={handleSendMessage}
            chatLoading={chatLoading}
            chatError={chatError}
          />
        )}
      </main>
    </div>
  )
}
