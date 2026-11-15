"""Client for Person 1's route and site planner endpoints."""

import json
import os
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
from typing import Any, Dict, Mapping

import httpx
from anyio import to_thread
from dotenv import load_dotenv


class PlannerError(Exception):
    """Raised when the planner rejects a request or returns an error."""


_GUIDE_DIR = Path(__file__).resolve().parent
load_dotenv(_GUIDE_DIR / ".env")
_CONNECTION_ERROR_MESSAGE = "I could not reach the route planner. Please check that it is running."
_SINGLE_APP = ContextVar("single_app_planner", default=None)
_BLOCKED_START = "Start is blocked by missing data, slope limit, or an avoid constraint"
_BLOCKED_MESSAGE = "Your starting point is inside an area excluded by your filters. Try another base, move A, or remove a filter."


@contextmanager
def inprocess_planner(app):
    """Select the co-mounted planner for this request, without global env mutation."""
    token = _SINGLE_APP.set(app)
    try:
        yield
    finally:
        _SINGLE_APP.reset(token)


def _inprocess_app():
    mode = os.getenv("PLANNER_MODE", "inprocess" if _SINGLE_APP.get() is not None else "http").strip().lower()
    if mode == "http":
        return None
    if mode != "inprocess":
        raise PlannerError("PLANNER_MODE must be http or inprocess.")
    app = _SINGLE_APP.get()
    if app is None:
        from olympustrail.api import app
    return app


def _status_error(status, detail=None):
    if status == 422:
        return PlannerError(_BLOCKED_MESSAGE if detail == _BLOCKED_START else "The route request was rejected. Check the start position and constraints.")
    if status == 503:
        return PlannerError("The planner's terrain data is temporarily unavailable.")
    return PlannerError(f"The planner returned an unexpected HTTP {status} response.")


async def _local_call(app, request=None):
    """Run synchronous planner work off the guide event loop."""
    from fastapi import HTTPException
    from pydantic import ValidationError
    from olympustrail.models import RouteRequest, SiteRequest

    def calculate():
        try:
            result = (app.state.terrain().sites(SiteRequest()) if request is None
                      else app.state.calculate(RouteRequest(**request)))
            return dict(result, _mock=False)
        except ValidationError as exc:
            raise _status_error(422) from exc
        except HTTPException as exc:
            raise _status_error(exc.status_code, exc.detail) from exc
        except Exception as exc:
            raise _status_error(500) from exc
    return await to_thread.run_sync(calculate)
_ALLOWED_FIELDS = {
    "start", "goal_type", "oxygen_hours", "battery_wh", "reserve_fraction",
    "return_to_start", "local_time_h", "mode", "min_goal_distance_km", "avoid",
}
_ALLOWED_AVOID = {"steep", "dust", "cold", "unknown_thermal"}


def _value(source: Any, name: str, default: Any = None) -> Any:
    """Read a field from either a mapping or a Pydantic-style object."""
    if isinstance(source, Mapping):
        return source.get(name, default)
    return getattr(source, name, default)


def _int_setting(name: str, default: int) -> int:
    """Read an integer setting, using the documented default if invalid."""
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def _position_dict(value: Any) -> Dict[str, float | int] | None:
    """Keep exactly one supported coordinate pair and discard extra keys."""
    if hasattr(value, "model_dump"):
        value = value.model_dump()
    elif hasattr(value, "dict") and not isinstance(value, Mapping):
        value = value.dict()
    if not isinstance(value, Mapping):
        return None
    if "row" in value and "col" in value:
        return {"row": int(value["row"]), "col": int(value["col"])}
    if "lon" in value and "lat" in value:
        return {"lon": float(value["lon"]), "lat": float(value["lat"])}
    return None


def build_route_request(parsed: Any, map_start: Any = None) -> dict:
    """Build a strict /route payload without AI-only or unknown fields."""
    start = _position_dict(_value(parsed, "start"))
    if start is None and map_start is not None:
        if hasattr(map_start, "model_dump"):
            map_start = map_start.model_dump()
        elif hasattr(map_start, "dict") and not isinstance(map_start, Mapping):
            map_start = map_start.dict()
        if isinstance(map_start, Mapping) and "lat" in map_start and "lon" in map_start:
            start = {"lon": float(map_start["lon"]), "lat": float(map_start["lat"])}
    if start is None:
        start = {
            "row": _int_setting("DEFAULT_START_ROW", 643),
            "col": _int_setting("DEFAULT_START_COL", 1226),
        }

    oxygen_hours = _value(parsed, "oxygen_hours")
    if oxygen_hours is None:
        oxygen_hours = 4

    battery_wh = _value(parsed, "battery_wh")
    if battery_wh is None:
        battery_pct = _value(parsed, "battery_pct")
        battery_wh = float(battery_pct) / 100 * 1000 if battery_pct is not None else 1000

    local_time_h = _value(parsed, "local_time_h")
    if local_time_h is None:
        local_time_h = 12

    avoid = _value(parsed, "avoid", []) or []
    if not isinstance(avoid, (list, tuple, set)):
        avoid = []

    request = {
        "start": start,
        "goal_type": "ice",
        "oxygen_hours": float(oxygen_hours),
        "battery_wh": float(battery_wh),
        "reserve_fraction": 0.2,
        "return_to_start": True,
        "local_time_h": int(local_time_h),
        "mode": "scenario",
        "min_goal_distance_km": 3,
        "avoid": list(dict.fromkeys(item for item in avoid if item in _ALLOWED_AVOID)),
    }
    return {key: value for key, value in request.items() if key in _ALLOWED_FIELDS}


def _use_mock() -> bool:
    """Return whether planner calls should use local mock data."""
    return os.getenv("USE_MOCK", "0").strip() == "1"


def _mock_route(request: Mapping[str, Any]) -> dict:
    """Load the appropriate real-contract mock response and mark its source."""
    filename = "mock_infeasible.json" if float(request.get("oxygen_hours", 4)) < 1 else "mock_route.json"
    with (_GUIDE_DIR / filename).open(encoding="utf-8") as mock_file:
        result = json.load(mock_file)
    result["_mock"] = True
    return result


def _planner_url() -> str:
    """Return the configured planner base URL without a trailing slash."""
    configured = os.getenv("PLANNER_URL")
    if configured:
        return configured.rstrip("/")
    # HTTP is retained for separate local processes or an explicit override.
    # Prefer the production alias over a potentially protected deployment URL.
    vercel_url = os.getenv("VERCEL_PROJECT_PRODUCTION_URL") or os.getenv("VERCEL_URL")
    if vercel_url:
        return f"https://{vercel_url}".rstrip("/")
    return "http://localhost:8000"


async def call_planner(request: dict) -> dict:
    """POST a route request, using mock output only when explicitly configured."""
    if _use_mock():
        return _mock_route(request)

    app = _inprocess_app()
    if app is not None:
        return await _local_call(app, request)

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(f"{_planner_url()}/route", json=request)
    except (httpx.TimeoutException, httpx.ConnectError) as exc:
        raise PlannerError(_CONNECTION_ERROR_MESSAGE) from exc

    if response.status_code < 200 or response.status_code >= 300:
        try:
            detail = response.json().get("detail")
        except (ValueError, AttributeError):
            detail = None
        raise _status_error(response.status_code, detail)
    try:
        result = response.json()
    except ValueError as exc:
        raise PlannerError("The planner returned an invalid response.") from exc
    if not isinstance(result, dict):
        raise PlannerError("The planner returned an invalid response.")
    result["_mock"] = False
    return result


def to_ui_path(result: dict) -> list:
    """Convert outbound and return coordinates into UI [lat, lon] pairs."""
    if result.get("status") != "ok":
        return []
    route = result.get("route") or {}
    outbound = route.get("outbound") or []
    return_path = route.get("return_path") or []
    points = outbound + return_path[1:]
    return [[point["lat"], point["lon"]] for point in points]


def _mock_sites() -> dict:
    """Return a small sites response with a best-base grid position."""
    position = {
        "row": _int_setting("DEFAULT_START_ROW", 643),
        "col": _int_setting("DEFAULT_START_COL", 1226),
    }
    return {
        "sites": [{"rank": 1, "position": position}],
        "best_base_position": position,
        "_mock": True,
    }


async def get_sites() -> dict:
    """Fetch candidate sites, using built-in mock data only in mock mode."""
    if _use_mock():
        return _mock_sites()
    app = _inprocess_app()
    if app is not None:
        return await _local_call(app)
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(f"{_planner_url()}/sites")
        response.raise_for_status()
        result = response.json()
        if not isinstance(result, dict):
            raise PlannerError("The site planner returned an invalid response.")
        result["_mock"] = False
        return result
    except (httpx.TimeoutException, httpx.ConnectError) as exc:
        raise PlannerError(_CONNECTION_ERROR_MESSAGE) from exc
    except httpx.HTTPError as exc:
        raise PlannerError("The site planner returned an error.") from exc
    except ValueError as exc:
        raise PlannerError("The site planner returned an invalid response.") from exc
