# MarsPath / OlympusTrail: Person 4 (AI Guide) context
Project: a Mars survival navigator. One shared Terrain Cost Grid powers a
Site Selector, a Route Planner, and an Ask-the-Map AI guide.
I own ONLY the ai_guide/ folder, plus frontend/src/voice.js and
frontend/src/components/AskPanel.jsx. Person 1 owns the planner API
(/sites, /route, /briefing-data). Person 3 owns the rest of frontend/
(React + Vite, port 5173). Do not edit their files.

My service: POST /ask on port 8001.
Flow: question -> parse to {start, goal_type, oxygen_hours, avoid}
 -> call Person 1's /route -> LLM explains the result in plain language.

Rules:
- The AI must ONLY explain numbers returned by the planner. Never invent data.
- The keyword fallback parser must work with no internet and no API key.
- Use Python, FastAPI, Pydantic, httpx, and the Gemini REST API via httpx.
- LLM provider is chosen by env LLM_PROVIDER (gemini or none).
- Gemini models to try come from env GEMINI_MODELS (comma-separated, tried in order).
- Read secrets from environment variables, never hardcode keys.
- Support USE_MOCK=1 to use ai_guide/mock_route.json instead of the real planner.
- Allow CORS for http://localhost:5173 and http://127.0.0.1:5173.
- Write small files, add docstrings, and add pytest tests.