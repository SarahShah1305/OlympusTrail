"""Gemini REST client used by the AI guide's LLM parser."""

import json
import os
from pathlib import Path
from typing import Any, Dict, Type, TypeVar

import httpx
from dotenv import load_dotenv
from pydantic import BaseModel


class ParserError(Exception):
    """Raised when an LLM response cannot be obtained or validated."""


T = TypeVar("T", bound=BaseModel)
_GUIDE_DIR = Path(__file__).resolve().parent
load_dotenv(_GUIDE_DIR / ".env")


def _models() -> list[str]:
    """Return configured Gemini models in their configured order."""
    configured = os.getenv("GEMINI_MODELS", "")
    if not configured.strip():
        configured = os.getenv("GEMINI_MODEL", "")
    return [model.strip() for model in configured.split(",") if model.strip()]


def _extract_text(payload: Dict[str, Any]) -> str:
    """Extract candidate text from a Gemini response."""
    try:
        parts = payload["candidates"][0]["content"]["parts"]
        result = "".join(part.get("text", "") for part in parts)
    except (KeyError, IndexError, TypeError) as exc:
        raise ParserError("Gemini returned no usable text") from exc
    if not result:
        raise ParserError("Gemini returned empty text")
    return result


def _strip_markdown_fence(text: str) -> str:
    """Remove an optional Markdown code fence around returned JSON."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned[3:]
        if cleaned[:4].lower() == "json":
            cleaned = cleaned[4:]
        cleaned = cleaned.lstrip("\r\n \t")
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
    return cleaned.strip()


def _as_number(value: Any) -> float | None:
    """Convert a JSON number to float, returning None for invalid values."""
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _coordinates(value: Any) -> Dict[str, float] | None:
    """Keep a coordinate object only when both fields are valid numbers."""
    if not isinstance(value, dict):
        return None
    lat, lon = _as_number(value.get("lat")), _as_number(value.get("lon"))
    if lat is None or lon is None:
        return None
    return {"lat": lat, "lon": lon}


def _validated_json(text: str, schema: Type[T]) -> T:
    """Parse JSON and populate a model from recognized, valid fields."""
    try:
        value = json.loads(_strip_markdown_fence(text))
    except json.JSONDecodeError as exc:
        raise ParserError("Gemini returned text that is not valid JSON") from exc

    if not isinstance(value, dict):
        value = {}
    if schema.__name__ == "ParsedRequest":
        from ai_guide.schema import ParsedRequest

        allowed_intents = {"route", "sites", "briefing", "unknown"}
        allowed_goals = {"ice", "base_site", "shelter", "coordinates"}
        allowed_avoid = {"steep_slopes", "radiation", "dust", "cold"}
        intent = value.get("intent")
        if not isinstance(intent, str):
            intent = "unknown"
        start_value = value.get("start", "current")
        start = start_value if isinstance(start_value, str) else _coordinates(start_value)
        if start is None:
            start = "current"
        goal_type = value.get("goal_type")
        if not isinstance(goal_type, str) or goal_type not in allowed_goals:
            goal_type = None
        goal = _coordinates(value.get("goal"))
        avoid = value.get("avoid", [])
        if not isinstance(avoid, list):
            avoid = []
        confidence = _as_number(value.get("confidence"))
        if confidence is None or confidence < 0 or confidence > 1:
            confidence = 0.5
        parsed_data = {
            "intent": intent if intent in allowed_intents else "unknown",
            "start": start,
            "goal_type": goal_type,
            "goal": goal,
            "oxygen_hours": _as_number(value.get("oxygen_hours")),
            "battery_pct": _as_number(value.get("battery_pct")),
            "avoid": [
                item for item in avoid
                if isinstance(item, str) and item in allowed_avoid
            ],
            "confidence": confidence,
        }
        return ParsedRequest(**parsed_data)  # type: ignore[return-value]

    fields = getattr(schema, "model_fields", None) or getattr(schema, "__fields__", {})
    recognized = {name: item for name, item in value.items() if name in fields}
    try:
        if hasattr(schema, "model_validate"):
            return schema.model_validate(recognized)
        return schema.parse_obj(recognized)
    except (ValueError, TypeError) as exc:
        raise ParserError("Gemini returned JSON that could not be validated") from exc


async def _call_model(
    client: httpx.AsyncClient,
    model: str,
    api_key: str,
    system: str,
    user: str,
    json_mode: bool = False,
) -> tuple[int, str]:
    """Call one Gemini model and return its status and response body."""
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:generateContent"
    )
    prompt = f"System instructions:\n{system}\n\nUser:\n{user}"
    body: Dict[str, Any] = {"contents": [{"parts": [{"text": prompt}]}]}
    if json_mode:
        body["generationConfig"] = {"responseMimeType": "application/json"}

    response = await client.post(
        url,
        headers={"x-goog-api-key": api_key},
        json=body,
    )
    return response.status_code, response.text


async def _generate(system: str, user: str, json_mode: bool = False) -> str:
    """Try configured Gemini models in order and return the first text result."""
    provider = os.getenv("LLM_PROVIDER", "none").strip().lower()
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if provider != "gemini":
        raise ParserError("LLM provider is not configured for Gemini")
    if not api_key:
        raise ParserError("GEMINI_API_KEY is not configured")
    models = _models()
    if not models:
        raise ParserError("No Gemini models are configured")

    last_error: Exception | None = None
    async with httpx.AsyncClient(timeout=8.0) as client:
        for model in models:
            try:
                status, body = await _call_model(
                    client, model, api_key, system, user, json_mode
                )
                if status != 200:
                    last_error = ParserError(
                        f"Gemini model {model} returned HTTP {status}"
                    )
                    continue
                try:
                    return _extract_text(json.loads(body))
                except (json.JSONDecodeError, ParserError) as exc:
                    last_error = exc
            except httpx.TimeoutException as exc:
                last_error = exc
            except httpx.HTTPError as exc:
                last_error = exc

    raise ParserError("All configured Gemini models failed") from last_error


async def complete_text(system: str, user: str) -> str:
    """Generate plain text using the configured Gemini model list."""
    return await _generate(system, user)


async def complete_json(system: str, user: str, schema: Type[T]) -> T:
    """Generate and validate JSON using the supplied Pydantic schema."""
    raw_text = await _generate(system, user, json_mode=True)
    return _validated_json(raw_text, schema)
