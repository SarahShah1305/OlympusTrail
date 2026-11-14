"""Single-origin FastAPI entry point for the Vercel deployment."""

from pathlib import Path

from fastapi import FastAPI

from ai_guide.main import AskPayload, ask
from olympustrail.api import app as planner_app

ROOT = Path(__file__).resolve().parent

app = FastAPI(title="OlympusTrail Mars Survival Navigator")
app.include_router(planner_app.router)
app.add_api_route("/ask", ask, methods=["POST"], response_model=dict)
app.frontend("/", directory=str(ROOT / "frontend" / "dist"), fallback="index.html")
