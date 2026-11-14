"""Offline tests for the fallback parser and the Person 1 request contract."""

import pytest

from ai_guide.parser_fallback import parse_fallback
from ai_guide.schema import ParsedRequest


EXISTING_CASES = [
    ("What's the safest route with 4 hours of oxygen?", "route", None, 4, None, None, [], []),
    ("Take me to the nearest ice.", "route", "ice", None, None, None, [], []),
    ("How do I get from the base to the closest shelter?", "route", "shelter", None, None, None, [], []),
    ("Find a route to ice that avoids radiation.", "route", "ice", None, None, None, [], ["avoid_radiation"]),
    ("I only have 2 hours of oxygen and 40% battery. Can I reach ice?", "route", "ice", 2, None, 40, [], []),
    ("Avoid steep slopes and dust. Go to the best base site.", "sites", "base_site", None, None, None, ["steep", "dust"], []),
    ("Where should we build the base?", "sites", "base_site", None, None, None, [], []),
    ("What's the shortest path to a lava tube?", "route", "shelter", None, None, None, [], []),
    ("Route me to ice, but I'm worried about the cold.", "route", "ice", None, None, None, ["cold"], []),
    ("What's the weather on Earth today?", "unknown", None, None, None, None, [], []),
    ("Take me from the base to the nearest ice.", "route", "ice", None, None, None, [], []),
]

SAMPLE_QUESTIONS = [
    ("What's the safest route with 4 hours of oxygen?", "route", None, 4, None, None, [], []),
    ("Take me to the nearest ice.", "route", "ice", None, None, None, [], []),
    ("How do I get from the base to the closest shelter?", "route", "shelter", None, None, None, [], []),
    ("Find a route to ice that avoids radiation.", "route", "ice", None, None, None, [], ["avoid_radiation"]),
    ("I only have 2 hours of oxygen and 40% battery. Can I reach ice?", "route", "ice", 2, None, 40, [], []),
    ("Avoid steep slopes and dust. Go to the best base site.", "sites", "base_site", None, None, None, ["steep", "dust"], []),
    ("Where should we build the base?", "sites", "base_site", None, None, None, [], []),
    ("What's the shortest path to a lava tube?", "route", "shelter", None, None, None, [], []),
    ("Route me to ice, but I'm worried about the cold.", "route", "ice", None, None, None, ["cold"], []),
    ("What's the weather on Earth today?", "unknown", None, None, None, None, [], []),
]


@pytest.mark.parametrize(
    "question,intent,goal_type,oxygen,battery_wh,battery_pct,avoid,unsupported",
    EXISTING_CASES,
)
def test_existing_sample_questions(
    question, intent, goal_type, oxygen, battery_wh, battery_pct, avoid, unsupported
):
    """Keep prior sample coverage aligned with the backend contract."""
    parsed = parse_fallback(question)
    assert parsed.intent == intent
    assert parsed.start is None
    assert parsed.goal_type == goal_type
    assert parsed.oxygen_hours == oxygen
    assert parsed.battery_wh == battery_wh
    assert parsed.battery_pct == battery_pct
    assert parsed.local_time_h is None
    assert parsed.avoid == avoid
    assert parsed.unsupported == unsupported
    assert parsed.confidence == 0.5


@pytest.mark.parametrize(
    "question,intent,goal_type,oxygen,battery_wh,battery_pct,avoid,unsupported",
    SAMPLE_QUESTIONS,
)
def test_requested_ten_questions(
    question, intent, goal_type, oxygen, battery_wh, battery_pct, avoid, unsupported
):
    """Check all ten requested questions against the offline keyword parser."""
    parsed = parse_fallback(question)
    assert parsed.intent == intent
    assert parsed.goal_type == goal_type
    assert parsed.oxygen_hours == oxygen
    assert parsed.battery_wh == battery_wh
    assert parsed.battery_pct == battery_pct
    assert parsed.avoid == avoid
    assert parsed.unsupported == unsupported


@pytest.mark.parametrize(
    "question,expected_avoid",
    [
        ("The route has a steep slope.", ["steep"]),
        ("It's dusty along the path.", ["dust"]),
        ("The route will be freezing.", ["cold"]),
        ("Avoid unknown thermal coverage.", ["unknown_thermal"]),
    ],
)
def test_contract_avoid_values(question, expected_avoid):
    """Map supported terrain terms only to the contract's avoid values."""
    assert parse_fallback(question).avoid == expected_avoid


def test_battery_wh_and_radiation_are_separated():
    """Parse Wh while keeping radiation in the unsupported list."""
    parsed = parse_fallback("Route to ice with 850 Wh and avoid radiation.")
    assert parsed.battery_wh == 850
    assert parsed.unsupported == ["avoid_radiation"]
    assert "radiation" not in parsed.avoid


def test_parsed_request_has_only_contract_fields():
    """Protect the exact ParsedRequest field names expected by the API."""
    expected = {
        "intent", "start", "goal_type", "oxygen_hours", "battery_wh",
        "battery_pct", "local_time_h", "avoid", "unsupported", "confidence",
    }
    fields = getattr(ParsedRequest, "model_fields", None) or ParsedRequest.__fields__
    assert set(fields) == expected
