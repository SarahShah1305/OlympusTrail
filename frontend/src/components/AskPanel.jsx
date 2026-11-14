import { useEffect, useRef, useState } from 'react'
import * as config from '../config'
import { isVoiceSupported, startListening } from '../voice'

const API_URL = config.AI_API_URL || 'http://localhost:8001'
const EXAMPLE_QUESTIONS = [
  "What's the safest route with 4 hours of oxygen?",
  'Take me to the nearest ice.',
  'Where should we build the base?',
]

const compactButtonStyle = {
  width: 'auto',
  minHeight: 31,
  padding: '0 11px',
  fontSize: 10,
  whiteSpace: 'nowrap',
}

export default function AskPanel({ onRoute, getMapStart }) {
  const [question, setQuestion] = useState('')
  const [loading, setLoading] = useState(false)
  const [answer, setAnswer] = useState(null)
  const [error, setError] = useState('')
  const [voiceError, setVoiceError] = useState('')
  const [listening, setListening] = useState(false)
  const stopListeningRef = useRef(null)

  useEffect(() => () => stopListeningRef.current?.(), [])

  async function submitQuestion(value = question) {
    const text = value.trim()
    if (!text || loading) return

    setQuestion(text)
    setLoading(true)
    setError('')
    setVoiceError('')
    setAnswer(null)

    try {
      const response = await fetch(`${API_URL.replace(/\/$/, '')}/ask`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          question: text,
          map_start: (() => {
            const mapStart = getMapStart?.()
            return mapStart ? { lon: mapStart[1], lat: mapStart[0] } : null
          })(),
        }),
      })
      if (!response.ok) throw new Error('AI guide request failed')

      const data = await response.json()
      setAnswer(data)
      const route = data.route
      if (route?.status === 'ok' && Array.isArray(route.path) && route.path.length > 0) {
        onRoute?.(route)
      } else {
        onRoute?.(null)
      }
    } catch {
      setAnswer(null)
      setError('I could not reach the AI guide. Please check that it is running.')
      onRoute?.(null)
    } finally {
      setLoading(false)
    }
  }

  function toggleListening() {
    setVoiceError('')
    if (listening) {
      stopListeningRef.current?.()
      stopListeningRef.current = null
      setListening(false)
      return
    }

    setListening(true)
    stopListeningRef.current = startListening({
      onResult: (spokenText) => {
        setQuestion(spokenText.slice(0, 500))
        void submitQuestion(spokenText.slice(0, 500))
      },
      onError: (message) => {
        setVoiceError(message)
        setListening(false)
        stopListeningRef.current = null
      },
      onEnd: () => {
        setListening(false)
        stopListeningRef.current = null
      },
    })
  }

  function chooseExample(example) {
    setQuestion(example)
    void submitQuestion(example)
  }

  const sourceLabel = answer?.source === 'llm' ? 'AI' : 'Offline guide'

  return (
    <section className="panel-section chat-section" aria-label="Ask the map">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Mission assistant</p>
          <h2>Ask the map</h2>
        </div>
        <span className="assistant-dot" title="Map guide ready" />
      </div>

      <form
        className="chat-form"
        onSubmit={(event) => {
          event.preventDefault()
          void submitQuestion()
        }}
      >
        <label className="visually-hidden" htmlFor="ask-map-question">
          Ask a question about Mars navigation
        </label>
        <input
          id="ask-map-question"
          type="text"
          maxLength={500}
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          placeholder="Ask about a route or site…"
          disabled={loading}
        />
        <button
          type="button"
          className={`voice-button ${listening ? 'is-listening' : ''}`}
          onClick={toggleListening}
          aria-label={listening ? 'Stop voice input' : 'Start voice input'}
          aria-pressed={listening}
          title={isVoiceSupported() ? 'Ask using your voice' : 'Voice input is not supported'}
          style={listening ? { background: 'var(--navy)', color: 'var(--cream)' } : undefined}
        >
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <rect x="9" y="3" width="6" height="12" rx="3" />
            <path d="M5.5 11.5a6.5 6.5 0 0 0 13 0M12 18v3m-4 0h8" />
          </svg>
        </button>
        <button
          type="submit"
          className="primary-button"
          disabled={!question.trim() || loading}
          style={compactButtonStyle}
        >
          Send
        </button>
      </form>

      {listening && <p className="eyebrow" role="status" style={{ marginTop: 7 }}>Listening…</p>}
      {loading && <p className="eyebrow" role="status" style={{ marginTop: 7 }}>Thinking...</p>}
      {voiceError && <p className="inline-error" role="alert">{voiceError}</p>}
      {error && <p className="inline-error" role="alert">{error}</p>}

      <div
        aria-label="Example questions"
        style={{ display: 'flex', flexWrap: 'wrap', gap: 5, marginTop: 9 }}
      >
        {EXAMPLE_QUESTIONS.map((example) => (
          <button
            key={example}
            type="button"
            onClick={() => chooseExample(example)}
            disabled={loading}
            style={{
              padding: '4px 7px',
              border: '1px solid var(--border)',
              borderRadius: 5,
              background: 'var(--cream-chat)',
              color: 'var(--navy)',
              fontSize: 9,
              textAlign: 'left',
              cursor: loading ? 'not-allowed' : 'pointer',
            }}
          >
            {example}
          </button>
        ))}
      </div>

      {answer && (
        <div className="chat-message assistant" style={{ maxWidth: '100%', marginTop: 10 }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
            <span className="message-author" style={{ marginBottom: 0 }}>Map guide</span>
            <span
              style={{
                padding: '2px 6px',
                borderRadius: 9,
                background: 'var(--coral)',
                color: 'var(--navy)',
                fontSize: 9,
                fontWeight: 700,
              }}
            >
              {sourceLabel}
            </span>
          </div>
          <p style={{ marginTop: 7 }}>{answer.explanation}</p>
          {answer.warnings?.length > 0 && (
            <ul style={{ margin: '6px 0 0', paddingLeft: 16, fontSize: 9, lineHeight: 1.45 }}>
              {answer.warnings.map((warning, index) => <li key={`${warning}-${index}`}>{warning}</li>)}
            </ul>
          )}
        </div>
      )}
    </section>
  )
}
