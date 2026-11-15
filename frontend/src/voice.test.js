import test from "node:test";
import assert from "node:assert/strict";
import { speechErrorMessage } from "./voice.js";
test("speech errors provide actionable causes", () => {
  assert.match(speechErrorMessage("network"), /internet.*Chrome or Edge/);
  assert.match(speechErrorMessage("audio-capture"), /microphone.*Windows/);
  for (const code of [
    "not-allowed",
    "service-not-allowed",
    "NotAllowedError",
    "SecurityError",
  ])
    assert.match(speechErrorMessage(code), /address bar.*Windows/);
  assert.match(speechErrorMessage("NotReadableError"), /other recording apps/);
  assert.match(speechErrorMessage("language-not-supported"), /English/);
  assert.match(speechErrorMessage("aborted"), /stopped/);
  assert.match(speechErrorMessage("no-speech"), /No speech/);
});
