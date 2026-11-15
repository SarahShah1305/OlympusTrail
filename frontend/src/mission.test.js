import test from "node:test";
import assert from "node:assert/strict";
import { presets, timeOfDay, tripVerdict } from "./mission.js";

test("standard preset matches the planner demo supplies", () => {
  assert.equal(presets.standard.oxygen, 4);
  assert.equal(presets.standard.battery, 1000);
});
test("incomplete searches are not described as feasible or infeasible", () => {
  assert.equal(tripVerdict("search_limit").tone, "caution");
  assert.equal(tripVerdict("ok").tone, "go");
  assert.equal(tripVerdict("infeasible").tone, "no-go");
});
test("time of day labels match the planner scenarios", () => {
  assert.deepEqual([0, 6, 12, 18].map(timeOfDay), [
    "Night",
    "Morning",
    "Midday",
    "Evening",
  ]);
});
