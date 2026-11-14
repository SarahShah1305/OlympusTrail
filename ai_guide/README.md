# OlympusTrail AI Guide

## What this is

The AI Guide is the question-and-answer helper for OlympusTrail. `POST /ask` turns a typed or spoken question into a structured request, calls the team's planner at `POST /route`, and explains the result in plain language using only numbers returned by the planner.

## How it works

Question → parser (Gemini, with an offline keyword fallback) → planner client (mock or real) → explainer (Gemini, with a template fallback and number post-check) → response.

## Setup on Windows PowerShell

From the project root, activate the virtual environment and install the AI Guide packages:

```powershell
.\.venv\Scripts\Activate.ps1
pip install fastapi uvicorn httpx pydantic python-dotenv pytest
```

Create `ai_guide/.env` with these settings. Replace the placeholder with your own key only on your computer; never put a real key in source files or documentation.

```dotenv
LLM_PROVIDER=none
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODELS=your_gemini_model_name
PLANNER_URL=http://localhost:8000
USE_MOCK=0
DEFAULT_START_ROW=643
DEFAULT_START_COL=1226
```

Never commit `.env`. It contains local configuration and may contain a secret key.

## Run and test

Run the AI Guide from the project root:

```powershell
uvicorn ai_guide.main:app --reload --port 8001
```

Run tests:

```powershell
pytest ai_guide -v
```

Interactive API documentation is at [http://localhost:8001/docs](http://localhost:8001/docs).

## API

### `GET /health`

Returns service status and public configuration. It never returns the API key.

```json
{
  "status": "ok",
  "llm_provider": "none",
  "use_mock": true
}
```

### `POST /ask`

Send a non-empty question of up to 500 characters. `map_start` can be `null` or a position with latitude and longitude.

Request:

```json
{
  "question": "Take me to the nearest ice.",
  "map_start": null
}
```

Response:

```json
{
  "parsed": {
    "intent": "route",
    "start": null,
    "goal_type": "ice",
    "oxygen_hours": null,
    "battery_wh": null,
    "battery_pct": null,
    "local_time_h": null,
    "avoid": [],
    "unsupported": [],
    "confidence": 0.5
  },
  "route": {
    "status": "ok",
    "path": [[52.5719, -157.2302]],
    "planner": {
      "status": "ok",
      "_mock": true,
      "metrics": {
        "distance_km": 6.0,
        "hours": 2.2,
        "oxygen_remaining_hours": 1.8
      }
    }
  },
  "explanation": "This is sample data. The route is feasible; distance: 6 km.",
  "source": "fallback",
  "warnings": ["Using sample data, not live planner results."]
}
```

The example shortens the `planner` object for readability. A route response includes the full planner result. `path` points are `[lat, lon]` pairs. `source` is `llm` or `fallback`.

## Behavior rules

- If no destination is given, the guide assumes the nearest ice and adds a warning.
- Shelter and lava tube destinations are not supported for automatic routing; only ice routing is supported.
- Radiation avoidance is not supported. The guide adds a warning that radiation is a uniform reference value.
- A battery percentage is converted to watt-hours using a 1000 Wh full battery, with a warning.
- Questions outside Mars navigation receive a polite refusal.
- Infeasible and search-limited results are never described as successful trips.

## Offline and demo safety

- Set `LLM_PROVIDER=none` to use the parser and explainer fallbacks without Gemini.
- Set `USE_MOCK=1` to use sample planner data. Mock planner results are marked with `"_mock": true` and the guide identifies them as sample data.

## Limitations

Radiation is a uniform Gale reference value, not a measurement in Arcadia. Temperatures are partly modeled. Battery and walking values are illustrative. The terrain grid is 500 m. Candidate shelters are unverified terrain candidates, not confirmed caves or verified shelters.

## Frontend

The Ask-the-Map panel is in `frontend/src/components/AskPanel.jsx`, with browser speech support in `frontend/src/voice.js`.

Use the panel like this:

```jsx
<AskPanel onRoute={handleRoute} getMapStart={getMapStart} />
```

`onRoute` receives `{status, path, planner}` when a route is available, with `path` formatted as `[[lat, lon], ...]`. It receives `null` when the response has no usable route. `getMapStart` can return `{lat, lon}` or `null`. Voice input requires browser support; Chrome or Edge is recommended.

## Test questions

| # | Question | Expected behavior |
|---:|---|---|
| 1 | What's the safest route with 4 hours of oxygen? | Route request; assumes nearest ice and records the oxygen budget. |
| 2 | Take me to the nearest ice. | Route request to ice. |
| 3 | How do I get from the base to the closest shelter? | Explains that automatic shelter routing is unsupported. |
| 4 | Find a route to ice that avoids radiation. | Routes to ice and warns that radiation avoidance is unsupported. |
| 5 | I only have 2 hours of oxygen and 40% battery. Can I reach ice? | Routes to ice; converts battery percentage to Wh with a warning. |
| 6 | Avoid steep slopes and dust. Go to the best base site. | Base-site request with supported terrain avoidances. |
| 7 | Where should we build the base? | Returns base-site guidance. |
| 8 | What's the shortest path to a lava tube? | Explains that automatic shelter routing is unsupported. |
| 9 | Route me to ice, but I'm worried about the cold. | Route request to ice with cold avoidance. |
| 10 | What's the weather on Earth today? | Polite refusal for an unsupported question. |
