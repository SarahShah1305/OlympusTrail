const UNSUPPORTED_MESSAGE =
  "Voice input is not supported in this browser. Please type your question, or use Chrome or Edge.";

const ERROR_MESSAGES = {
  "not-allowed":
    "Microphone access was blocked. Allow the microphone and try again.",
  "no-speech": "I did not hear anything. Please try again.",
};

function recognitionConstructor() {
  if (typeof window === "undefined") return null;
  return window.SpeechRecognition || window.webkitSpeechRecognition || null;
}

export function isVoiceSupported() {
  return Boolean(recognitionConstructor());
}

export function startListening({ onResult, onError, onEnd } = {}) {
  const Recognition = recognitionConstructor();
  if (!Recognition) {
    onError?.(UNSUPPORTED_MESSAGE);
    return () => {};
  }

  const recognition = new Recognition();
  recognition.lang = "en-US";
  recognition.continuous = false;
  recognition.interimResults = false;
  recognition.maxAlternatives = 1;
  recognition.onresult = (event) => {
    const text = event.results?.[0]?.[0]?.transcript;
    if (text) onResult?.(text);
  };
  recognition.onerror = (event) => {
    onError?.(
      ERROR_MESSAGES[event.error] ||
        "Voice input failed. Please type your question.",
    );
  };
  recognition.onend = () => onEnd?.();

  try {
    recognition.start();
  } catch {
    onError?.("Voice input failed. Please type your question.");
    onEnd?.();
  }

  return () => {
    try {
      recognition.stop();
    } catch {
      // Stopping an inactive recognition session needs no further handling.
    }
  };
}
