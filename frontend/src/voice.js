export const UNSUPPORTED_MESSAGE =
  "Voice input works in Chrome and Edge on a secure connection. You can type your question instead.";
const permissionMessage =
  "Allow the microphone for this site in the address bar, and check Windows Settings > Privacy & security > Microphone, including desktop app access.";
const ERROR_MESSAGES = {
  network:
    "Voice needs an internet connection and Chrome or Edge; Brave is not supported.",
  "audio-capture": "No microphone found. Check Windows sound settings.",
  "service-not-allowed": permissionMessage,
  "not-allowed": permissionMessage,
  "language-not-supported":
    "The speech service does not support English (US). You can type your question instead.",
  aborted: "Voice input stopped. Press the microphone to try again.",
  "no-speech": "No speech was heard. Check your microphone and try again.",
  NotAllowedError: permissionMessage,
  SecurityError: permissionMessage,
  NotFoundError: "No microphone found. Check Windows sound settings.",
  NotReadableError:
    "The microphone could not be opened. Close other recording apps and check Windows sound settings.",
};
export function speechErrorMessage(code) {
  return (
    ERROR_MESSAGES[code] ||
    "Voice input failed. You can type your question instead."
  );
}
function recognitionConstructor() {
  if (typeof window === "undefined") return null;
  return window.SpeechRecognition || window.webkitSpeechRecognition || null;
}
export function isVoiceSupported() {
  return Boolean(recognitionConstructor());
}
export function startListening({ onResult, onError, onEnd } = {}) {
  let cancelled = false;
  let recognition;
  const fail = (message) => {
    if (!cancelled) {
      onError?.(message);
      onEnd?.();
    }
  };
  async function start() {
    if (!window.isSecureContext) {
      fail(
        "Voice input needs HTTPS or localhost. You can type your question instead.",
      );
      return;
    }
    const Recognition = recognitionConstructor();
    if (!Recognition || !navigator.mediaDevices?.getUserMedia) {
      fail(UNSUPPORTED_MESSAGE);
      return;
    }
    try {
      let permission;
      try {
        permission = await navigator.permissions?.query({ name: "microphone" });
      } catch {
        /* Not supported in every browser. */
      }
      if (cancelled) return;
      if (permission?.state === "denied") {
        fail("Microphone is blocked for this site. " + permissionMessage);
        return;
      }
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      stream.getTracks().forEach((track) => track.stop());
      if (cancelled) return;
      recognition = new Recognition();
      recognition.lang = "en-US";
      recognition.continuous = false;
      recognition.interimResults = false;
      recognition.maxAlternatives = 1;
      recognition.onresult = (event) => {
        if (!cancelled) {
          const text = event.results?.[0]?.[0]?.transcript;
          if (text) onResult?.(text);
        }
      };
      recognition.onerror = (event) => {
        console.warn("speech error", event.error, event.message);
        fail(speechErrorMessage(event.error));
      };
      recognition.onend = () => {
        if (!cancelled) onEnd?.();
      };
      recognition.start();
    } catch (error) {
      console.warn("speech error", error.name, error.message);
      fail(speechErrorMessage(error.name));
    }
  }
  void start();
  return () => {
    cancelled = true;
    try {
      recognition?.abort();
    } catch {
      /* Already stopped. */
    }
  };
}
