# Deployment

## Vercel

The repository root is the project root. `vercel.json` builds the Vite frontend and deploys `index.py` as one Python function. That entry point serves the frontend and both APIs (`/sites`, `/route`, `/health`, and `/ask`) on the same origin. No environment variables are required for a build or for the guide's offline fallback.

In Vercel, import the repository and deploy from its root. Keep the build command from `vercel.json` (`npm ci --prefix frontend && npm run build --prefix frontend`) and use the Python requirements in `requirements.txt`. The function configuration includes the terrain data under `data/person1/arcadia_500m/` and sets a 60-second maximum duration. Vercel plan limits still apply: check the project's current memory and duration limits before increasing workload or function limits.

### Optional environment variables

Add variables in the Vercel project settings for the environments where they should apply. Leave secrets out of source files and Git.

| Variable | When to set it | Behavior |
| --- | --- | --- |
| `LLM_PROVIDER` | Optional | `none` uses the offline parser and template explanation (default). Use `gemini` to enable Gemini. |
| `GEMINI_API_KEY` | Only with Gemini | Secret API key. Store it as a protected environment variable. |
| `GEMINI_MODELS` | Optional with Gemini | Comma-separated model names to try, in order. |
| `PLANNER_MODE` | Optional | `inprocess` calls the planner directly inside the deployed function. `http` calls a planner service over HTTP. `index.py` configures `inprocess` for the single-function deployment; outside that entry point, the default is `http`. |
| `PLANNER_URL` | Optional with HTTP planner mode | Base URL for the planner. If unset on Vercel, the guide uses `VERCEL_PROJECT_PRODUCTION_URL` first, then `VERCEL_URL`. These Vercel values are host names; the guide adds HTTPS. |
| `USE_MOCK` | Optional | `0` uses the configured planner; `1` explicitly switches to sample planner results. Keep this at `0` for live planner data. |

`inprocess` avoids an HTTP request back to the same deployment. Use `http` when the planner is hosted separately, and set `PLANNER_URL` to that service's origin. HTTP planner requests have a 30-second timeout. The frontend's own API requests also need to finish within the function's duration limit.

If Vercel Deployment Protection is enabled, it can block the guide's server-to-server HTTP request to a protected planner deployment. In that setup, use `inprocess` for a single deployment, or configure an authorized planner URL and the platform's supported protection bypass for server requests. Treat any bypass token as a secret; do not add it to frontend variables.

After deployment, open the site and check the About drawer's **Build SHA** against the deployed Git commit. Then check `/health` for an `ok` response, try a planner action, and submit a question in Ask the Map. With `LLM_PROVIDER=none`, guide answers use the offline fallback. Confirm the result is live planner data and not marked as sample data when `USE_MOCK=0`.

## Local development

For development, run the planner on port 8000, the guide on port 8001, and Vite on port 5173 in separate terminals from the repository root. Activate the Python environment in both Python terminals:

```powershell
python -m uvicorn olympustrail.api:app --port 8000
```

```powershell
python -m uvicorn ai_guide.main:app --port 8001
```

```powershell
npm run dev --prefix frontend
```

Vite proxies planner requests to port 8000 and guide requests to port 8001. For the guide, the local HTTP planner default is `http://localhost:8000`. Set `PLANNER_MODE=inprocess` only when running through the single-origin `index.py` entry point.
