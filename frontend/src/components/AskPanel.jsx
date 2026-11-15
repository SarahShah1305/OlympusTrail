import { useEffect, useRef, useState } from "react";
import * as config from "../config";
import {
  isVoiceSupported,
  startListening,
  UNSUPPORTED_MESSAGE,
} from "../voice";

const API_URL = config.AI_API_URL;
const EXAMPLE_QUESTIONS = [
  "Plan a route that fits 4 hours of oxygen.",
  "How can I reach the nearest ice?",
  "Compare areas for a possible base.",
];

const statusLabels = {
  unchecked: "Ready",
  checking: "Thinking…",
  connected: "Ready",
  unavailable: "Guide is offline",
  demo: "Sample mode",
};

export default function AskPanel({
  onRoute,
  getMapStart,
  sourceMode = "live",
}) {
  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const [answer, setAnswer] = useState(null);
  const [error, setError] = useState("");
  const [voiceError, setVoiceError] = useState("");
  const [listening, setListening] = useState(false);
  const [voiceStatus, setVoiceStatus] = useState("");
  const [connectionState, setConnectionState] = useState("unchecked");
  const stopListeningRef = useRef(null);
  const requestVersion = useRef(0);
  const voiceSupported = isVoiceSupported();
  const isDemo = sourceMode === "demo";

  useEffect(
    () => () => {
      requestVersion.current++;
      stopListeningRef.current?.();
    },
    [],
  );

  async function submitQuestion(value = question) {
    const text = value.trim();
    if (!text || loading) return;

    setQuestion(text);
    setError("");
    setVoiceError("");

    if (isDemo) {
      setConnectionState("demo");
      setError(
        "The guide needs a live planner. You can still build a route with the manual planner.",
      );
      return;
    }

    const version = ++requestVersion.current;
    setLoading(true);
    setConnectionState("checking");

    try {
      const mapStart = getMapStart?.();
      const response = await fetch(
        `${API_URL ? API_URL.replace(/\/$/, "") : ""}/ask`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          signal: AbortSignal.timeout(60000),
          body: JSON.stringify({
            question: text,
            map_start: mapStart ? { lon: mapStart[1], lat: mapStart[0] } : null,
          }),
        },
      );
      if (!response.ok) throw new Error("Planner request failed");

      const data = await response.json();
      if (version !== requestVersion.current) return;
      setAnswer(data);
      setConnectionState(
        data.route?.status === "error" ? "unavailable" : "connected",
      );

      const route = data?.route;
      if (
        route?.status === "ok" &&
        Array.isArray(route.path) &&
        route.path.length > 0
      ) {
        onRoute?.(route);
      }
    } catch {
      if (version !== requestVersion.current) return;
      setConnectionState("unavailable");
      setError(
        "The guide could not answer. Check your trip with the planner or try again.",
      );
    } finally {
      if (version === requestVersion.current) setLoading(false);
    }
  }

  function toggleListening() {
    if (!voiceSupported) return;
    setVoiceError("");
    if (listening) {
      stopListeningRef.current?.();
      stopListeningRef.current = null;
      setListening(false);
      return;
    }

    setListening(true);
    setVoiceStatus("Starting voice input…");
    stopListeningRef.current = startListening({
      onStatus: setVoiceStatus,
      onResult: (spokenText) => {
        setQuestion(spokenText.slice(0, 500));
        setVoiceError(
          "Review the transcription, then press Send when you are ready.",
        );
      },
      onError: (message) => {
        setVoiceError(message);
        setListening(false);
        stopListeningRef.current = null;
      },
      onEnd: () => {
        setListening(false);
        stopListeningRef.current = null;
      },
    });
  }

  function chooseExample(example) {
    setQuestion(example);
    setError("");
  }

  const sourceLabel =
    answer?.source === "llm" ? "AI guide" : "Rule-based guide";

  return (
    <section className="panel-section chat-section" aria-label="Ask the map">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Mission assistant</p>
          <h2>Ask the map</h2>
        </div>
        <span
          role="status"
          aria-live="polite"
          style={{
            fontSize: 13,
            fontWeight: 600,
            color: "var(--muted, #5d584e)",
          }}
        >
          {statusLabels[isDemo ? "demo" : connectionState] ||
            statusLabels.unchecked}
        </span>
      </div>

      <p style={{ margin: "8px 0 10px", fontSize: 14, lineHeight: 1.5 }}>
        {isDemo
          ? "The guide is unavailable in sample mode. You can still plan a trip using the controls."
          : "When you press Send, your question and the selected map starting point are sent to the live planner. Without a selected base, the guide uses its configured default starting point, which will appear in the result. Example prompts fill the box; they do not send automatically."}
      </p>

      <form
        className="chat-form"
        onSubmit={(event) => {
          event.preventDefault();
          void submitQuestion();
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
          className={`voice-button ${listening ? "is-listening" : ""}`}
          onClick={toggleListening}
          aria-label={listening ? "Stop voice input" : "Start voice input"}
          aria-pressed={listening}
          title={
            voiceSupported
              ? "Transcribe a question for review"
              : UNSUPPORTED_MESSAGE
          }
          disabled={!voiceSupported || loading}
          style={{ minWidth: 40, minHeight: 40 }}
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
        >
          {loading ? "Sending…" : "Send"}
        </button>
      </form>

      {!voiceSupported && <p role="status">{UNSUPPORTED_MESSAGE}</p>}

      {listening && (
        <p role="status" style={{ marginTop: 8, fontSize: 14 }}>
          {voiceStatus || "Listening…"}
        </p>
      )}
      {loading && (
        <p role="status" style={{ marginTop: 8, fontSize: 14 }}>
          Waiting for the planner…
        </p>
      )}
      {voiceError && (
        <p role="status" style={{ marginTop: 8, fontSize: 14 }}>
          {voiceError}
        </p>
      )}
      {error && (
        <p className="inline-error" role="alert" style={{ fontSize: 14 }}>
          {error}
        </p>
      )}

      <div
        aria-label="Example questions"
        style={{ display: "flex", flexWrap: "wrap", gap: 8, marginTop: 10 }}
      >
        {EXAMPLE_QUESTIONS.map((example) => (
          <button
            key={example}
            type="button"
            onClick={() => chooseExample(example)}
            disabled={loading}
            style={{
              minHeight: 38,
              padding: "6px 10px",
              border: "1px solid var(--border)",
              borderRadius: 5,
              background: "var(--cream-chat)",
              color: "var(--navy)",
              fontSize: 13,
              lineHeight: 1.35,
              textAlign: "left",
              cursor: loading ? "not-allowed" : "pointer",
            }}
          >
            {example}
          </button>
        ))}
      </div>

      {answer && (
        <div
          className="chat-message assistant"
          style={{ maxWidth: "100%", marginTop: 12 }}
        >
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              gap: 8,
            }}
          >
            <span className="message-author" style={{ marginBottom: 0 }}>
              Map guide
            </span>
            <span
              style={{
                padding: "3px 8px",
                borderRadius: 9,
                background: "var(--coral)",
                color: "var(--navy)",
                fontSize: 12,
                fontWeight: 700,
              }}
            >
              {sourceLabel}
            </span>
          </div>
          {answer.route?.status === "ok" ? (
            <>
              <p>
                The planner found a round trip within its configured limits.
                Review the distance, supplies, scenario time and reserve in the
                mission result before comparing options.
              </p>
              <details>
                <summary>How the guide interpreted your request</summary>
                <p>
                  Oxygen:{" "}
                  {answer.route.planner?.budget?.oxygen_hours ?? "not supplied"}{" "}
                  Earth hours. Battery:{" "}
                  {answer.route.planner?.budget?.battery_wh ?? "not supplied"}{" "}
                  Wh. These are the guide’s interpreted settings; they replace
                  the manual form only when a route succeeds.
                </p>
                <p style={{ fontSize: 14, lineHeight: 1.55 }}>
                  {answer.explanation}
                </p>
              </details>
            </>
          ) : (
            <p style={{ marginTop: 8, fontSize: 14, lineHeight: 1.55 }}>
              {answer.explanation}
            </p>
          )}
          {answer.warnings?.length > 0 && (
            <ul
              style={{
                margin: "8px 0 0",
                paddingLeft: 20,
                fontSize: 13,
                lineHeight: 1.5,
              }}
            >
              {answer.warnings.map((warning, index) => (
                <li key={`${warning}-${index}`}>{warning}</li>
              ))}
            </ul>
          )}
        </div>
      )}
    </section>
  );
}
