"""Offline keyword parser for Mars navigation questions."""

import re

from ai_guide.schema import ParsedRequest


def parse_fallback(question: str) -> ParsedRequest:
    """Extract planner intent and constraints with local keywords only."""
    text = question.lower()
    avoid = []
    unsupported = []

    if re.search(r"\b(steep|slope|slopes)\b", text):
        avoid.append("steep")
    if re.search(r"\b(dust|dusty)\b", text):
        avoid.append("dust")
    if re.search(r"\b(cold|freezing)\b", text):
        avoid.append("cold")
    if re.search(r"\bunknown\s+thermal\b", text):
        avoid.append("unknown_thermal")
    if re.search(r"\bradiation\b", text):
        unsupported.append("avoid_radiation")

    has_ice = bool(re.search(r"\bice\b", text))
    has_shelter = bool(re.search(r"\b(shelter|cave)\b|lava\s+tube", text))
    base_site = bool(re.search(r"\bbest\s+base\b|\bbest\s+site\b|\bbase\s+site\b|\bcolony\s+site\b|\bpick\s+(?:a\s+)?base\b", text))
    asks_where_to_build = bool(
        re.search(r"where\s+(?:should\s+we\s+build|to\s+build)", text)
    )
    site_question = base_site or asks_where_to_build

    if re.search(r"\b(briefing|eva)\b", text):
        intent = "briefing"
    elif site_question:
        intent = "sites"
    elif has_ice or has_shelter:
        intent = "route"
    elif re.search(r"\b(route|path|navigate|travel|go\s+to|take\s+me)\b", text):
        intent = "route"
    else:
        intent = "unknown"

    if has_ice:
        goal_type = "ice"
    elif has_shelter:
        goal_type = "shelter"
    elif site_question:
        goal_type = "base_site"
    else:
        goal_type = None

    oxygen_match = re.search(
        r"\b(\d+(?:\.\d+)?)\s*(?:hours?|hrs?|h)\s*(?:of\s*)?oxygen\b",
        text,
    )
    battery_pct_match = re.search(
        r"\b(\d+(?:\.\d+)?)\s*%\s*battery\b|"
        r"\bbattery\D{0,12}(\d+(?:\.\d+)?)\s*%",
        text,
    )
    battery_wh_match = re.search(r"\b(\d+(?:\.\d+)?)\s*wh\b", text)

    return ParsedRequest(
        intent=intent,
        start=None,
        goal_type=goal_type,
        oxygen_hours=float(oxygen_match.group(1)) if oxygen_match else None,
        battery_wh=float(battery_wh_match.group(1)) if battery_wh_match else None,
        battery_pct=(
            float(battery_pct_match.group(1) or battery_pct_match.group(2))
            if battery_pct_match
            else None
        ),
        avoid=list(dict.fromkeys(avoid)),
        unsupported=unsupported,
        confidence=0.5,
    )
