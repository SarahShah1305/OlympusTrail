# Local deployment validation

Verified locally on Windows on 2026-11-15. **Unverified on Vercel.** No deployment, dashboard settings, environment variables, production branch, or deployment protection settings were changed for this task.

## Checks

- Clean-copy frontend `npm ci`, production build, lint, and 14 unit tests passed.
- Backend `pytest tests/ ai_guide/`: 137 passed; two existing Pydantic deprecation warnings.
- All seven Playwright regressions passed, including the existing live planner smoke test.
- Five real-data golden `/route` responses saved before the memory changes match exactly: default ice from candidate 1, steep avoidance, dust avoidance, manual goal, and infeasible supplies. Comparison includes all fields, metrics and path points, stronger than the requested 0.01 km distance tolerance.
- A separate resource-heavy search (1,000 hours oxygen and 1,000,000 Wh) returned the same `search_limit` response and candidate paths before and after; its full JSON was compared locally outside the repository.

## Trimmed-bundle Uvicorn simulation

The original code at `0491347` and modified code were copied into separate scratch bundles, excluding every directory listed in `vercel.json`. The same built frontend was copied to both. Each ran via `uvicorn index:app` on a separate local port, with `PLANNER_URL`, `VERCEL_URL`, `VERCEL_PROJECT_PRODUCTION_URL`, and `PLANNER_MODE` unset; `USE_MOCK=0` and `LLM_PROVIDER=none` were explicit. The guide used the fallback parser. Both guide requests returned `route.status=ok`. The old guide could reach the already running local planner on port 8000; that is not a reproduction of deployment protection or cold-start failures.

The new guide uses the co-mounted planner in process. An offline test replaces the HTTP client with a failing sentinel and confirms successful in-process results; mocked-transport tests verify the explicit HTTP fallback and 422/503/unexpected-error mapping. The synchronous calculation runs in a worker thread.

| Request | Before HTTP | Before seconds | After HTTP | After seconds |
| --- | --- | --- | --- | --- |
| health | 200 | 1.482 | 200 | 0.028 |
| sites | 200 | 1.624 | 200 | 2.224 |
| default | 200 | 0.338 | 200 | 0.526 |
| heavy | 200 | 0.308 | 200 | 0.417 |
| ask | 200 | 0.642 | 200 | 0.388 |
| asset | 200 | 0.309 | 200 | 0.198 |

The simulation's heavy request used 1,000 hours oxygen with the default 1,000 Wh battery at 43 N, 170 W. It returned `infeasible`; the separate larger-energy stress case above reached `search_limit`. These workload details matter when comparing with the reviewer's Linux measurements.

## Memory method and results

This host has no WSL/Linux installation, so `/proc/<pid>/status` and Linux `VmHWM` could not be measured. The values below are Windows resident working set and peak working set (MiB), from `GetProcessMemoryInfo` **inside the actual Uvicorn Python worker**, using a scratch-only probe. Reading the venv launcher's PID gives an irrelevant ~9.5 MiB value, so it was rejected. The probe was not added to project code or API routes.

| Stage | Before resident MiB | After resident MiB |
| --- | ---: | ---: |
| After module import | 81.18 | 81.29 |
| After health | 520.25 | 81.36 |
| After sites | 563.58 | 260.09 |
| After all requests | 567.59 | 286.57 |
| Peak working set | 1013.14 | 472.34 |

Startup and health remain below 250 MiB; peak is below 700 MiB for these local single-request workloads. Loaded steady-state is about 287 MiB, not below 250 MiB. Linux/Vercel memory and concurrent-request peak remain unmeasured. Rasters load on use at original float32 precision where possible, coordinate projection uses bounded chunks, health reads metadata, and routing/ranking arithmetic retains float64 precision. The route search algorithm and limits were not changed.

## Static headers

The asset response changed from no explicit cache policy to `public, max-age=31536000, immutable`. Root/index are `no-cache`; layer assets/metadata use `public, max-age=86400, stale-while-revalidate=604800`. A local test checks all four paths. Vercel routing remains unchanged; see [the preview-only CDN proposal](vercel-static-hosting.md). No CDN performance claim follows from these local results.

## Needs Moiz on Vercel

Check the actual `/ask` response, deployed commit/build stamp, Deployment Protection, Fluid compute/function memory, environment variables (`LLM_PROVIDER`, `GEMINI_API_KEY`, `USE_MOCK`, `PLANNER_MODE`), and runtime logs for import errors, out-of-memory or killed processes. A successful cheap `/health` is not a full terrain check; also request `/sites` and a route.

Backend-owner follow-up: `/sites` ranking does not apply route avoid filters. Four of five candidates remain in the east strip; markers and ranking were not moved or fabricated.
