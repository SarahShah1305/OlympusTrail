import { normalizeRoute, normalizeSites, routeRequest } from "./contract.js";
import { exampleRoute, exampleSites } from "./examples.js";
const apiUrl = (import.meta.env?.VITE_API_URL || "").replace(/\/$/, "");
export const BLOCKED_START =
  "Your starting point is inside an area excluded by your filters. Try another base, move A, or remove a filter.";
export async function request(path, options = {}, baseUrl = apiUrl) {
  let response;
  try {
    response = await fetch(`${baseUrl.replace(/\/$/, "")}${path}`, {
      ...options,
      headers: { "Content-Type": "application/json", ...options.headers },
      signal: AbortSignal.timeout(55000),
    });
  } catch (error) {
    const failure = new Error(
      error?.name === "TimeoutError" || error?.name === "AbortError"
        ? "The planner timed out. Please try again."
        : "The planner could not be reached. Please try again.",
    );
    failure.transient = true;
    throw failure;
  }
  let data;
  try {
    data = await response.json();
  } catch {
    const failure = new Error(
      "The server returned an unreadable response. Please try again.",
    );
    failure.transient = response.status === 502 || response.status === 504;
    throw failure;
  }
  if (!response.ok) {
    const failure = new Error(
      response.status === 422 &&
        data.detail ===
          "Start is blocked by missing data, slope limit, or an avoid constraint"
        ? BLOCKED_START
        : typeof data.detail === "string"
          ? data.detail
          : `The planner rejected this request (${response.status}). Check the selected points and supplies.`,
    );
    failure.transient = response.status === 502 || response.status === 504;
    throw failure;
  }
  return data;
}
export async function getSites(sourceMode = "live") {
  if (sourceMode === "demo") return { sites: exampleSites };
  try {
    return normalizeSites(await request("/sites?min_separation_km=60"));
  } catch (error) {
    if (!error.transient) throw error;
    await new Promise((resolve) => setTimeout(resolve, 300));
    return normalizeSites(await request("/sites?min_separation_km=60"));
  }
}
export async function planRoute(options) {
  if (options.sourceMode === "demo") return exampleRoute(options);
  return normalizeRoute(
    await request("/route", {
      method: "POST",
      body: JSON.stringify(routeRequest(options)),
    }),
  );
}
