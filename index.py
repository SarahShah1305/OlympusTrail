"""Single-origin FastAPI entry point for the Vercel deployment."""

from pathlib import Path
import re
import os

from fastapi import FastAPI

from ai_guide.main import AskPayload, ask
from ai_guide.planner_client import inprocess_planner
from olympustrail.api import app as planner_app

ROOT = Path(__file__).resolve().parent

app = FastAPI(title="OlympusTrail Mars Survival Navigator")

async def static_cache_headers(request, call_next):
    response = await call_next(request)
    if response.status_code == 200 and request.method in ("GET", "HEAD"):
        path = request.url.path
        if re.match(r"^/assets/.+-[A-Za-z0-9_-]{8,}\.[^/]+$", path):
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        elif path.startswith("/layers/"):
            response.headers["Cache-Control"] = "public, max-age=86400, stale-while-revalidate=604800"
        elif path in ("/", "/index.html"):
            response.headers["Cache-Control"] = "no-cache"
    return response

if not os.environ.get("VERCEL"):
    # Root middleware prevents Vercel from promoting the public frontend to
    # its CDN. Use platform headers there and retain local cache behavior here.
    app.middleware("http")(static_cache_headers)

app.include_router(planner_app.router)
async def ask_single_app(payload: AskPayload):
    with inprocess_planner(planner_app):
        return await ask(payload)


app.add_api_route("/ask", ask_single_app, methods=["POST"], response_model=dict)
app.frontend("/", directory=str(ROOT / "frontend" / "dist"), fallback="index.html")
