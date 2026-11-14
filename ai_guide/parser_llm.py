"""LLM-backed natural-language request parser."""

from typing import Any, List, Optional

from pydantic import BaseModel, Field

from ai_guide.llm_client import ParserError, complete_json
from ai_guide.schema import Coordinates, GridPosition, ParsedRequest


_SYSTEM_PROMPT = (
    "You convert questions about Mars surface travel into structured requests. "
    "Only extract what the user said. Never invent coordinates or numbers. "
    "If a value is not stated, use null. If the question is not about routes, "
    "sites, or briefings, set intent to unknown."
)
_JSON_SHAPE = (
    'Return one JSON object with this exact shape: '
    '{"intent":"route","start":null,"goal_type":"ice",'
    '"oxygen_hours":null,"battery_wh":null,"battery_pct":null,'
    '"local_time_h":null,"avoid":[],"unsupported":[],"confidence":0.5}. '
    "The start must be null unless the user gives coordinates; otherwise use "
    "either {\"row\": integer, \"col\": integer} or "
    "{\"lon\": number, \"lat\": number}. The avoid list may contain only "
    "steep, dust, cold, or unknown_thermal. Radiation requests go in "
    "unsupported as avoid_radiation, never in avoid. Lava tube or shelter "
    "means goal_type shelter. Best base site means base_site. Where should "
    "we build the base means intent sites."
)
_ALLOWED_AVOID = {"steep", "dust", "cold", "unknown_thermal"}
_ALLOWED_INTENTS = {"route", "sites", "briefing", "unknown"}
_ALLOWED_GOALS = {"ice", "shelter", "base_site"}
_ALLOWED_LOCAL_TIMES = {0, 6, 12, 18}


class _LLMOutput(BaseModel):
    """Loose intermediate response model, sanitized into ParsedRequest."""

    intent: Any = None
    start: Any = None
    goal_type: Any = None
    oxygen_hours: Any = None
    battery_wh: Any = None
    battery_pct: Any = None
    local_time_h: Any = None
    avoid: List[Any] = Field(default_factory=list)
    unsupported: List[Any] = Field(default_factory=list)
    confidence: Any = None

    class Config:
        extra = "ignore"


def _number(value: Any) -> Optional[float]:
    """Return a numeric value as float, or None if it is malformed."""
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _position(value: Any) -> Any:
    """Accept only one complete planner coordinate representation."""
    if not isinstance(value, dict):
        return None
    if set(value) == {"row", "col"}:
        try:
            return GridPosition(row=value["row"], col=value["col"])
        except (TypeError, ValueError):
            return None
    if set(value) == {"lon", "lat"}:
        try:
            return Coordinates(lon=value["lon"], lat=value["lat"])
        except (TypeError, ValueError):
            return None
    return None


async def parse_question(
    question: str,
    map_start: Optional[Coordinates] = None,
) -> ParsedRequest:
    """Parse a question and validate its sanitized result with ParsedRequest."""
    user = f"{_JSON_SHAPE}\nQuestion: {question}"
    if map_start is not None:
        user += "\nApp map position is context only; do not treat it as user-stated start coordinates."
    try:
        raw = await complete_json(_SYSTEM_PROMPT, user, _LLMOutput)
        intent = (
            raw.intent
            if isinstance(raw.intent, str) and raw.intent in _ALLOWED_INTENTS
            else "unknown"
        )
        goal_type = (
            raw.goal_type
            if isinstance(raw.goal_type, str) and raw.goal_type in _ALLOWED_GOALS
            else None
        )
        avoid = [item for item in raw.avoid if isinstance(item, str) and item in _ALLOWED_AVOID]
        unsupported = [item for item in raw.unsupported if isinstance(item, str)]
        confidence = _number(raw.confidence)
        if confidence is None or not 0 <= confidence <= 1:
            confidence = 0.5
        local_time = raw.local_time_h
        if not isinstance(local_time, int) or local_time not in _ALLOWED_LOCAL_TIMES:
            local_time = None

        return ParsedRequest(
            intent=intent,
            start=_position(raw.start),
            goal_type=goal_type,
            oxygen_hours=_number(raw.oxygen_hours),
            battery_wh=_number(raw.battery_wh),
            battery_pct=_number(raw.battery_pct),
            local_time_h=local_time,
            avoid=avoid,
            unsupported=unsupported,
            confidence=confidence,
        )
    except Exception as exc:
        if isinstance(exc, ParserError):
            raise
        raise ParserError("Unable to parse question with the LLM") from exc
