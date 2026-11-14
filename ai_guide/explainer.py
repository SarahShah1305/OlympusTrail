"""Summarize planner results and explain them without adding unsupported facts."""

import json
import re
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any, Dict, Iterable, List, Mapping, Tuple

from ai_guide.llm_client import complete_text


_LIMITS = (
    "Radiation is a uniform reference value, not measured in Arcadia; temperatures "
    "are partly modeled; battery and walking values are illustrative; the grid is "
    "500 m; candidate shelters are unverified terrain candidates."
)
_SYSTEM_PROMPT = (
    "Explain the planner result in plain language using ONLY the numbers given in "
    "the summary. Never invent data. Use the numbers exactly as given in the facts. "
    "Do not recalculate, add digits or round them differently. Keep the answer under "
    "120 words. If status is "
    "not ok, clearly say the trip is NOT possible and why; never describe it as a "
    "successful trip. If _mock is true, say this is sample data. Mention these "
    "limits briefly: radiation is a uniform reference value (not measured in "
    "Arcadia), temperatures are partly modeled, battery and walking values are "
    "illustrative, grid is 500 m, and candidate shelters are unverified terrain "
    "candidates. If the question gives no destination, say the nearest ice was "
    "assumed."
)
_NUMBER_RE = re.compile(
    r"(?<![A-Za-z0-9_])[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?(?![A-Za-z0-9_])"
)
_LIST_MARKER_RE = re.compile(r"(?m)^[ \t]*(?:[-*][ \t]*)?\d+[.)](?:[ \t]+|$)")
_QUESTION_BUDGET_PATTERNS = (
    re.compile(r"\b(\d+(?:\.\d+)?)\s*(?:hours?|hrs?|h)\s*(?:of\s*)?oxygen\b", re.I),
    re.compile(r"\b(\d+(?:\.\d+)?)\s*%\s*battery\b", re.I),
    re.compile(r"\bbattery\D{0,16}(\d+(?:\.\d+)?)\s*%", re.I),
    re.compile(r"\b(\d+(?:\.\d+)?)\s*wh\b", re.I),
)


def summarize_result(result: dict) -> dict:
    """Return only the concise planner facts needed for an explanation."""
    status = result.get("status")
    if status not in {"ok", "infeasible", "search_limit"}:
        status = "search_limit"
    summary: Dict[str, Any] = {"status": status, "_mock": bool(result.get("_mock", False))}
    if status != "ok":
        summary["reason"] = result.get("reason")
        return summary

    metrics = result.get("metrics") or {}
    for field in (
        "distance_km",
        "hours",
        "oxygen_remaining_hours",
        "battery_remaining_wh",
        "maximum_slope_deg",
        "minimum_temperature_k",
        "maximum_dust_optical_depth",
        "radiation_reference_msv",
    ):
        if field in metrics:
            places = 2 if field in {"maximum_dust_optical_depth", "radiation_reference_msv"} else 1
            summary[field] = _rounded_number(metrics[field], places)

    turn_back = result.get("turn_back") or {}
    turnaround = turn_back.get("turnaround")
    if isinstance(turnaround, Mapping):
        for field in ("distance_km", "elapsed_hours"):
            if field in turnaround:
                summary[f"turnaround_{field}"] = _rounded_number(turnaround[field], 1)
    for field in ("oxygen_reserve_hours", "battery_reserve_wh"):
        if field in turn_back:
            summary[field] = _rounded_number(turn_back[field], 1)
    candidates = turn_back.get("candidate_shelters")
    if candidates is not None:
        summary["candidate_shelters_count"] = len(candidates)
    return summary


def _rounded_number(value: Any, places: int) -> int | float | None:
    """Round a numeric fact and use an integer when its rounded value is whole."""
    if value is None or isinstance(value, bool):
        return None
    try:
        quantum = Decimal(1).scaleb(-places)
        rounded = Decimal(str(value)).quantize(quantum, rounding=ROUND_HALF_UP)
    except (InvalidOperation, TypeError, ValueError):
        return None
    if not rounded.is_finite():
        return None
    if rounded == rounded.to_integral_value():
        return int(rounded)
    return float(rounded)


def _get_parsed(parsed: Any, field: str, default: Any = None) -> Any:
    """Read a parser field from either a mapping or model-like object."""
    return parsed.get(field, default) if isinstance(parsed, Mapping) else getattr(parsed, field, default)


def _numbers_in(value: Any) -> Iterable[float]:
    """Yield numeric values recursively from the summary."""
    if isinstance(value, bool) or value is None:
        return
    if isinstance(value, (int, float)):
        yield float(value)
    elif isinstance(value, Mapping):
        for child in value.values():
            yield from _numbers_in(child)
    elif isinstance(value, (list, tuple)):
        for child in value:
            yield from _numbers_in(child)


def _question_budget_numbers(question: str) -> set[float]:
    """Allow question numbers and Wh derived from explicitly stated battery percent."""
    clean_question = _LIST_MARKER_RE.sub("", question)
    numbers = {float(token) for token in _NUMBER_RE.findall(clean_question)}
    percentages = {
        float(match.group(1) or match.group(2))
        for pattern in _QUESTION_BUDGET_PATTERNS[1:3]
        for match in pattern.finditer(question)
    }
    numbers.update(percent * 10 for percent in percentages)
    return numbers


def _is_verified_number(number: float, decimal_places: int, allowed: set[float]) -> bool:
    """Match a displayed value to facts rounded to its displayed precision."""
    try:
        quantum = Decimal(1).scaleb(-min(decimal_places, 2))
        displayed = Decimal(str(number)).quantize(quantum, rounding=ROUND_HALF_UP)
        return any(
            displayed == Decimal(str(item)).quantize(quantum, rounding=ROUND_HALF_UP)
            for item in allowed
        )
    except (InvalidOperation, TypeError, ValueError):
        return False


def _append_unverified_warning(warnings: Any) -> None:
    """Append the standard warning when a mutable warning list was supplied."""
    warning = "Some numbers in the explanation could not be verified."
    if isinstance(warnings, list) and warning not in warnings:
        warnings.append(warning)


def _postcheck_numbers(text: str, summary: dict, question: str, warnings: Any) -> None:
    """Warn when the explanation contains a number absent from trusted inputs."""
    allowed = set(_numbers_in(summary)) | _question_budget_numbers(question) | {500.0}
    clean_text = _LIST_MARKER_RE.sub("", text)
    for token in _NUMBER_RE.findall(clean_text):
        try:
            number = float(token)
        except ValueError:
            _append_unverified_warning(warnings)
            return
        decimal_part = token.lower().split("e", 1)[0].partition(".")[2]
        if not _is_verified_number(number, len(decimal_part), allowed):
            _append_unverified_warning(warnings)
            return


def _format_number(summary: dict, key: str, places: int = 1) -> str | None:
    """Format an available numeric summary value without inventing defaults."""
    value = summary.get(key)
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return None
    rounded = _rounded_number(value, places)
    return str(rounded) if rounded is not None else None


def _assumed_ice(warnings: Any) -> bool:
    """Check whether the caller recorded the assumed nearest-ice destination."""
    return isinstance(warnings, list) and any(
        "no destination was given" in str(warning).lower() for warning in warnings
    )


def template_explanation(summary: dict, warnings: List[str]) -> str:
    """Build a fixed, non-LLM explanation for either successful or failed plans."""
    status = summary.get("status")
    sample = "This is sample data. " if summary.get("_mock") else ""
    if status != "ok":
        reason = summary.get("reason") or "the planner could not find a feasible route"
        text = (
            f"{sample}The trip is NOT possible ({reason}). Try with more oxygen or "
            f"battery and check the plan again. {_LIMITS}"
        )
        if _assumed_ice(warnings):
            text += " The nearest ice was assumed."
        return text

    details = []
    for key, label, places in (
        ("distance_km", "distance", 1),
        ("hours", "travel time", 1),
        ("oxygen_remaining_hours", "oxygen remaining", 1),
        ("battery_remaining_wh", "battery remaining", 1),
        ("maximum_slope_deg", "maximum slope", 1),
        ("minimum_temperature_k", "minimum temperature", 1),
        ("maximum_dust_optical_depth", "maximum dust optical depth", 2),
        ("radiation_reference_msv", "radiation reference", 2),
        ("oxygen_reserve_hours", "oxygen reserve", 1),
        ("battery_reserve_wh", "battery reserve", 1),
        ("turnaround_distance_km", "turnaround distance", 1),
        ("turnaround_elapsed_hours", "turnaround time", 1),
    ):
        value = _format_number(summary, key, places)
        if value is not None:
            details.append(f"{label}: {value}")
    candidate_count = summary.get("candidate_shelters_count")
    if isinstance(candidate_count, int):
        details.append(f"candidate shelters: {candidate_count} unverified terrain candidates")
    text = (
        f"{sample}The route is feasible. "
        + ("; ".join(details) + ". " if details else "")
        + _LIMITS
    )
    if _assumed_ice(warnings):
        text += " The nearest ice was assumed."
    return text


async def explain(question: str, parsed: Any, result: dict, warnings: List[str]) -> Tuple[str, str]:
    """Explain a planner result, falling back to a fixed template on any failure."""
    try:
        summary = summarize_result(result)
        if summary["status"] in {"infeasible", "search_limit"}:
            return template_explanation(summary, warnings), "fallback"

        user = json.dumps({"summary": summary, "question": question}, ensure_ascii=False)
        text = await complete_text(_SYSTEM_PROMPT, user)
        if not isinstance(text, str) or not text.strip():
            raise ValueError("LLM returned no explanation")
        text = text.strip()
        lowered_text = text.lower()
        if any(phrase in lowered_text for phrase in ("not possible", "cannot reach", "infeasible")):
            return template_explanation(summary, warnings), "fallback"
        _postcheck_numbers(text, summary, question, warnings)

        no_destination = (
            _get_parsed(parsed, "intent") == "route"
            and _get_parsed(parsed, "goal_type") is None
        )
        if no_destination and "nearest ice" not in text.lower():
            text += " The nearest ice was assumed."
        return text, "llm"
    except Exception:
        try:
            summary = summarize_result(result)
            text = template_explanation(summary, warnings)
            no_destination = (
                _get_parsed(parsed, "intent") == "route"
                and _get_parsed(parsed, "goal_type") is None
            )
            if no_destination and "nearest ice" not in text.lower():
                text += " The nearest ice was assumed."
            return text, "fallback"
        except Exception:
            return "The planner result could not be explained safely.", "fallback"
