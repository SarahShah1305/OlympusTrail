import { useCallback, useEffect, useRef, useState } from 'react'

function BudgetBar({ label, value, total, unit, kind }) {
  const percent = total > 0 ? Math.max(0, Math.min(100, (value / total) * 100)) : 0
  const urgent = percent <= 20
  return (
    <div className={`budget-item ${urgent ? 'is-urgent' : ''}`}>
      <div className="budget-label">
        <span>{label}</span>
        <strong>{value}{unit} left</strong>
      </div>
      <div
        className={`budget-track budget-track--${kind}`}
        role="progressbar"
        aria-label={`${label} remaining`}
        aria-valuenow={Math.round(percent)}
        aria-valuemin="0"
        aria-valuemax="100"
      >
        <span style={{ width: `${percent}%` }} />
      </div>
      {urgent && <span className="urgent-note">Reserve below 20%</span>}
    </div>
  )
}

function StatusBanner({ route }) {
  if (!route || route.status === 'ok') return null
  const point = route.abort_points?.[0]
  return (
    <div className="status-banner" role="alert">
      <span className="status-mark" aria-hidden="true">!</span>
      <div>
        <strong>{route.status === 'turn_back' ? 'Turn back now' : 'Reroute recommended'}</strong>
        <p>{route.message}</p>
        {point && <span>Abort point: {point.label}</span>}
      </div>
    </div>
  )
}

function VoiceButton({ onTranscript }) {
  const [listening, setListening] = useState(false)
  const [supported] = useState(
    typeof window !== 'undefined' &&
      Boolean(window.SpeechRecognition || window.webkitSpeechRecognition),
  )
  const recognitionRef = useRef(null)

  useEffect(() => {
    const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition
    if (!Recognition) return undefined
    const recognition = new Recognition()
    recognition.lang = 'en-US'
    recognition.interimResults = false
    recognition.onresult = (event) => {
      const transcript = event.results?.[0]?.[0]?.transcript
      if (transcript) onTranscript(transcript)
    }
    recognition.onerror = (event) => {
      console.warn('Speech recognition failed.', event.error)
      setListening(false)
    }
    recognition.onend = () => setListening(false)
    recognitionRef.current = recognition
    return () => recognition.stop()
  }, [onTranscript])

  function toggleListening() {
    if (!recognitionRef.current) return
    if (listening) {
      recognitionRef.current.stop()
      setListening(false)
      return
    }
    try {
      recognitionRef.current.start()
      setListening(true)
    } catch (error) {
      console.warn('Speech recognition could not start.', error)
      setListening(false)
    }
  }

  return (
    <button
      type="button"
      className={`voice-button ${listening ? 'is-listening' : ''}`}
      onClick={toggleListening}
      disabled={!supported}
      title={supported ? (listening ? 'Stop listening' : 'Ask using your voice') : 'Voice input is not supported in this browser'}
      aria-label={supported ? (listening ? 'Stop voice input' : 'Start voice input') : 'Voice input is not supported in this browser'}
      aria-pressed={listening}
    >
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <rect x="9" y="3" width="6" height="12" rx="3" />
        <path d="M5.5 11.5a6.5 6.5 0 0 0 13 0M12 18v3m-4 0h8" />
      </svg>
    </button>
  )
}

export default function MissionPanel({
  mode,
  route,
  start,
  goal,
  oxygenHours,
  onOxygenChange,
  avoid,
  onAvoidToggle,
  onPlanRoute,
  routeLoading,
  routeError,
  messages,
  onSendMessage,
  chatLoading,
  chatError,
}) {
  const [input, setInput] = useState('')
  const messageEndRef = useRef(null)
  const inputRef = useRef(null)

  useEffect(() => {
    messageEndRef.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
  }, [messages, chatLoading])
  useEffect(() => {
    if (mode === 'ask') inputRef.current?.focus()
  }, [mode])

  const transcript = useCallback((text) => setInput(text), [])
  const submitChat = (event) => {
    event.preventDefault()
    const message = input.trim()
    if (!message || chatLoading) return
    onSendMessage(message)
    setInput('')
  }

  return (
    <aside className="side-panel right-panel" aria-label="Mission planner and map guide">
      <section className="panel-section budget-section">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Expedition resources</p>
            <h2>Budget</h2>
          </div>
          {route && <span className={`route-status status-${route.status}`}>{route.status.replace('_', ' ')}</span>}
        </div>
        {route ? (
          <>
            <BudgetBar
              label="Oxygen"
              value={Number(Math.max(0, route.oxygen_total_h - route.oxygen_used_h).toFixed(1))}
              total={route.oxygen_total_h}
              unit=" h"
              kind="oxygen"
            />
            <BudgetBar
              label="Battery"
              value={Math.max(0, 100 - route.battery_used_pct)}
              total={100}
              unit="%"
              kind="battery"
            />
            <div className="route-summary">
              <div><span>Distance</span><strong>{route.distance_km} km</strong></div>
              <div><span>Est. time</span><strong>{route.duration_h} h</strong></div>
              <div><span>Oxygen used</span><strong>{route.oxygen_used_h} h</strong></div>
            </div>
            <StatusBanner route={route} />
          </>
        ) : (
          <div className="budget-empty">
            <span className="empty-icon" aria-hidden="true">↗</span>
            <p>Plan a route to see modeled oxygen and battery reserves.</p>
          </div>
        )}
      </section>

      <section className="panel-section route-section">
        <div className="section-heading">
          <div>
            <p className="eyebrow">EVA planning</p>
            <h2>Survival route</h2>
          </div>
        </div>
        <div className="endpoint-summary">
          <span className={start ? 'endpoint-chip set' : 'endpoint-chip'}><b>A</b>{start ? 'Start set' : 'Choose start'}</span>
          <span className="endpoint-link" aria-hidden="true" />
          <span className={goal ? 'endpoint-chip set' : 'endpoint-chip'}><b>B</b>{goal ? 'Goal set' : 'Choose goal'}</span>
        </div>
        <div className="route-controls">
          <label className="field-label" htmlFor="oxygen-hours">Oxygen budget</label>
          <div className="input-with-unit">
            <input
              id="oxygen-hours"
              type="number"
              min="0.5"
              max="24"
              step="0.5"
              value={oxygenHours}
              onChange={(event) => onOxygenChange(event.target.value)}
            />
            <span>hours</span>
          </div>
        </div>
        <fieldset className="avoid-options">
          <legend>Avoid</legend>
          {[
            ['steep_slopes', 'Steep slopes'],
            ['high_radiation', 'High radiation'],
            ['dust', 'Dust risk'],
          ].map(([id, label]) => (
            <label key={id}>
              <input type="checkbox" checked={avoid.includes(id)} onChange={() => onAvoidToggle(id)} />
              <span>{label}</span>
            </label>
          ))}
        </fieldset>
        <button
          type="button"
          className="primary-button"
          disabled={!start || !goal || routeLoading}
          onClick={onPlanRoute}
        >
          {routeLoading ? <><span className="spinner" /> Planning route…</> : 'Plan route'}
        </button>
        {routeError && <p className="inline-error" role="alert">{routeError}</p>}
      </section>

      <section className="panel-section chat-section">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Mission assistant</p>
            <h2>Ask the map</h2>
          </div>
          <span className="assistant-dot" title="Map guide ready" />
        </div>
        <div className="chat-messages" role="log" aria-live="polite" aria-label="Conversation">
          {messages.map((message) => (
            <div className={`chat-message ${message.role}`} key={message.id}>
              <span className="message-author">{message.role === 'user' ? 'You' : 'Map guide'}</span>
              <p>{message.text}</p>
            </div>
          ))}
          {chatLoading && (
            <div className="chat-message assistant thinking" role="status">
              <span className="message-author">Map guide</span>
              <p>Checking the planner<span className="thinking-dots">…</span></p>
            </div>
          )}
          {chatError && (
            <div className="chat-error" role="alert">
              <span>{chatError}</span>
              <button type="button" onClick={() => onSendMessage(messages.at(-1)?.text || '')}>Retry</button>
            </div>
          )}
          <div ref={messageEndRef} />
        </div>
        <form className="chat-form" onSubmit={submitChat}>
          <label className="visually-hidden" htmlFor="map-question">Ask a question about this map</label>
          <input
            ref={inputRef}
            id="map-question"
            type="text"
            value={input}
            onChange={(event) => setInput(event.target.value)}
            placeholder="Ask about a route or site…"
            disabled={chatLoading}
          />
          <VoiceButton onTranscript={transcript} />
          <button className="send-button" type="submit" disabled={!input.trim() || chatLoading} aria-label="Send question">
            <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 12 20 4l-5 16-3-7-8-1Zm8 1 8-9" /></svg>
          </button>
        </form>
        <p className="chat-footnote">Answers use preview site and route data until the live API is connected.</p>
      </section>
    </aside>
  )
}
