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
export function startListening({ onResult, onError, onEnd, onStatus } = {}) {
  let cancelled = false;
  let recognition;
  let transcript = "";
  let receivedResult = false;
  let failed = false;
  let audioStarted = false;
  let speechDetected = false;
  let startupTimer;
  const fail = (message) => {
    if (!cancelled) {
      failed = true;
      clearTimeout(startupTimer);
      onError?.(message);
      onEnd?.();
    }
  };
  async function start() {
    onStatus?.("Requesting microphone access…");
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
      recognition.interimResults = true;
      recognition.maxAlternatives = 1;
      onStatus?.("Microphone permission granted. Starting speech recognition…");
      recognition.onstart = () => {
        if (!cancelled) onStatus?.("Speech recognition started. Speak now.");
      };
      recognition.onaudiostart = () => {
        audioStarted = true;
        clearTimeout(startupTimer);
        if (!cancelled)
          onStatus?.("Audio capture started. Waiting for speech…");
      };
      recognition.onspeechstart = () => {
        speechDetected = true;
        if (!cancelled) onStatus?.("Speech detected. Transcribing…");
      };
      recognition.onresult = (event) => {
        if (!cancelled) {
          transcript = Array.from(event.results || [])
            .map((result) => result[0]?.transcript || "")
            .join(" ")
            .trim();
          if (transcript) {
            receivedResult = true;
            onResult?.(transcript);
          }
        }
      };
      recognition.onerror = (event) => {
        console.warn("speech error", event.error, event.message);
        fail(speechErrorMessage(event.error));
      };
      recognition.onend = () => {
        clearTimeout(startupTimer);
        if (!cancelled) {
          if (!failed && !receivedResult) {
            onError?.(
              speechDetected
                ? "Speech was detected, but the browser returned no transcription. Try again and report this message if it repeats."
                : audioStarted
                  ? "Audio capture started, but the speech service detected no speech. Check this browser’s selected input device; permission alone does not confirm sound reached recognition."
                  : "Permission was granted, but the browser ended recognition before audio capture started. Please report your browser name and this message.",
            );
          }
          onEnd?.();
        }
      };
      recognition.start();
      startupTimer = setTimeout(() => {
        if (!cancelled && !audioStarted && !failed && !receivedResult) {
          fail(
            "Microphone permission was granted, but speech recognition did not start audio capture within 15 seconds. Please report your browser name and this message.",
          );
          recognition.abort();
        }
      }, 15000);
    } catch (error) {
      console.warn("speech error", error.name, error.message);
      fail(speechErrorMessage(error.name));
    }
  }
  void start();
  return () => {
    cancelled = true;
    clearTimeout(startupTimer);
    try {
      recognition?.abort();
    } catch {
      /* Already stopped. */
    }
  };
}
