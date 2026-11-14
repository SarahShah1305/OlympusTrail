# Website usability changes

Work branch: `moiz/website-usability`. Original workspace, main, backend/AI source, datasets and dependency lockfiles were not changed.

## Result
- Clear project purpose and guided base → round trip → review journey.
- Explicit sample mode, with no silent substitution when the real planner fails.
- Strict backend coordinate and response adapters; nearby ice search, oxygen, Wh battery, local time, symmetric return and 20% reserve.
- Ranked-site evidence, clear score limitations, a working “Use as starting base” action from list and map, manual point changes and keyboard coordinate entry.
- Single guide panel, honest connection state, review-before-send examples/voice transcription, failed requests preserve existing route.
- Plain results for successful/infeasible/incomplete searches; whole-trip resource totals, real return checkpoints and printable briefing.
- One map overlay at a time, evidence legend, historical basemap label, data footprint/resolution notes, correct northern planner extent, readable responsive panels and hidden-map resize guards.
- Radiation describes the uniform Gale dose-equivalent reference without promising Arcadia measurements or shielding.

## Validation
- Production Vite build: pass.
- Oxlint: pass without warnings.
- Node API contract tests: 6 pass.
- Browser checks: real top-ranked-base trip (6.00 km, 2.23 h, 411.18 Wh at 06:00); insufficient oxygen rejects departure; guide unavailable preserves route; connected rule-based guide returns real route and updates interpreted settings; phone base selection, mission and map panels.
- NASA basemap depends on an external tile service and may have gaps; display is capped to native zoom 6 while mission markers remain zoomable.

## Local preview
Run backend on 8000, guide on 8001 and Vite from frontend. Vite proxies local API calls; deployment continues using same-origin endpoints. No production deployment or merge has been performed.

Review all frontend diffs together before integrating with any new teammate changes. The original deployment remains unchanged until this branch is approved and integrated.
