import assert from "node:assert/strict";
import test from "node:test";
import { getBriefingMetrics } from "./briefing.js";

test("briefing omits metrics for an infeasible route", () => {
  assert.deepEqual(getBriefingMetrics(null), []);
});

test("briefing omits missing or nonnumeric metrics", () => {
  assert.deepEqual(getBriefingMetrics({ distance_km: Number.NaN, hours: 2 }), [
    { label: "Travel time", value: "2.00", unit: "hours" },
  ]);
});
