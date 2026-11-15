import test from "node:test";
import assert from "node:assert/strict";
import { request, getSites, BLOCKED_START } from "./client.js";

test("site loading retries a transient failure once", async () => {
  let calls = 0;
  globalThis.fetch = async () => { if (++calls === 1) throw new TypeError("network"); return { ok: true, json: async () => ({ sites: [] }) }; };
  await getSites();
  assert.equal(calls, 2);
});
test("errors distinguish timeout, unreadable response, and blocked start", async () => {
  globalThis.fetch = async () => { throw new DOMException("late", "TimeoutError"); };
  await assert.rejects(request("/route"), /timed out/);
  globalThis.fetch = async () => ({ ok: false, status: 500, json: async () => { throw Error(); } });
  await assert.rejects(request("/route"), /unreadable response/);
  globalThis.fetch = async () => ({ ok: false, status: 422, json: async () => ({ detail: "Start is blocked by missing data, slope limit, or an avoid constraint" }) });
  await assert.rejects(request("/route"), { message: BLOCKED_START });
});
