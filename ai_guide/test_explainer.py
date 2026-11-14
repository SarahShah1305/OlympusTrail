"""Offline tests for planner-result summaries and explanations."""

import asyncio
import json
from collections.abc import Mapping
from decimal import Decimal
from pathlib import Path

import pytest

from ai_guide import explainer


_GUIDE_DIR = Path(__file__).resolve().parent


def _load(name):
    """Load one checked-in mock planner response."""
    with (_GUIDE_DIR / name).open(encoding="utf-8") as source:
        return json.load(source)


@pytest.fixture(autouse=True)
def disable_llm(monkeypatch):
    """Keep tests offline unless a test replaces the LLM function."""
    monkeypatch.setenv("LLM_PROVIDER", "none")


def test_ok_summary_contains_planner_facts_without_abort_destination():
    """Successful summary uses metrics and does not expose last_reachable."""
    result = _load("mock_route.json")
    result["_mock"] = True
    summary = explainer.summarize_result(result)
    assert summary["status"] == "ok"
    assert summary["distance_km"] == 6
    assert summary["hours"] == 2.2
    assert summary["oxygen_remaining_hours"] == 1.8
    assert summary["battery_remaining_wh"] == 588.8
    assert summary["maximum_slope_deg"] == 0.8
    assert summary["minimum_temperature_k"] == 201.2
    assert summary["maximum_dust_optical_depth"] == 0.25
    assert summary["radiation_reference_msv"] == 0.06
    assert summary["oxygen_reserve_hours"] == 0.8
    assert summary["battery_reserve_wh"] == 200
    assert summary["candidate_shelters_count"] == len(result["turn_back"]["candidate_shelters"])
    assert summary["_mock"] is True
    assert "last_reachable" not in summary


def test_summary_numbers_have_at_most_two_decimal_places():
    """All numeric summary facts use the specified concise precision."""
    summary = explainer.summarize_result(_load("mock_route.json"))

    def check(value):
        if isinstance(value, Mapping):
            for child in value.values():
                check(child)
        elif isinstance(value, list):
            for child in value:
                check(child)
        elif isinstance(value, (int, float)) and not isinstance(value, bool):
            assert max(0, -Decimal(str(value)).as_tuple().exponent) <= 2

    check(summary)


def test_summary_has_no_coordinate_keys_or_objects():
    """Summary remains flat and never includes coordinate keys or dicts."""
    summary = explainer.summarize_result(_load("mock_route.json"))

    def check(value):
        if isinstance(value, Mapping):
            for key, child in value.items():
                assert key.lower() not in {"lat", "lon", "row", "col"}
                check(child)
        elif isinstance(value, list):
            for child in value:
                check(child)
        else:
            assert not isinstance(value, dict)

    check(summary)


def test_infeasible_summary_contains_only_status_reason_and_mock_flag():
    """Failed summary excludes route and last-reachable details."""
    result = _load("mock_infeasible.json")
    summary = explainer.summarize_result(result)
    assert summary == {
        "status": "infeasible",
        "_mock": False,
        "reason": "no_feasible_route",
    }


def test_ok_template_mentions_distance_and_sample_data():
    """Successful fallback template identifies sample output and distance."""
    summary = explainer.summarize_result(_load("mock_route.json"))
    summary["_mock"] = True
    text = explainer.template_explanation(summary, [])
    assert "distance: 6" in text
    assert "sample data" in text
    assert not any(token in text.lower() for token in ("{", "}", "lat", "lon"))


def test_infeasible_template_says_trip_is_not_possible():
    """Failed fallback template says not possible and includes planner reason."""
    summary = explainer.summarize_result(_load("mock_infeasible.json"))
    text = explainer.template_explanation(summary, [])
    assert "NOT possible" in text
    assert "no_feasible_route" in text
    assert "more oxygen or battery" in text


def test_postcheck_adds_warning_for_invented_number(monkeypatch):
    """An LLM number absent from the summary is flagged for the caller."""
    async def fake_complete_text(system, user):
        return "The distance is 999 km."

    monkeypatch.setattr(explainer, "complete_text", fake_complete_text)
    warnings = []
    text, source = asyncio.run(
        explainer.explain("Find ice.", {"intent": "route", "goal_type": "ice"}, _load("mock_route.json"), warnings)
    )
    assert "999" in text
    assert source == "llm"
    assert warnings == ["Some numbers in the explanation could not be verified."]


def test_postcheck_flags_invented_77_point_3(monkeypatch):
    """A plausible-looking but unsupported metric remains flagged."""
    async def fake_complete_text(system, user):
        return "The estimated value is 77.3."

    monkeypatch.setattr(explainer, "complete_text", fake_complete_text)
    warnings = []
    asyncio.run(
        explainer.explain(
            "Find ice.",
            {"intent": "route", "goal_type": "ice"},
            _load("mock_route.json"),
            warnings,
        )
    )
    assert warnings == ["Some numbers in the explanation could not be verified."]


def test_postcheck_allows_grid_size_from_fixed_limits(monkeypatch):
    """The fixed 500 m limitation does not create a false warning."""
    async def fake_complete_text(system, user):
        return "The grid is 500 m."

    monkeypatch.setattr(explainer, "complete_text", fake_complete_text)
    warnings = []
    asyncio.run(
        explainer.explain(
            "Find ice.",
            {"intent": "route", "goal_type": "ice"},
            _load("mock_route.json"),
            warnings,
        )
    )
    assert warnings == []


def test_postcheck_allows_question_budget_and_derived_battery_wh(monkeypatch):
    """Question numbers and Wh derived from battery percent are trusted."""
    async def fake_complete_text(system, user):
        return "You have 4 hours of oxygen and 400 Wh of battery."

    monkeypatch.setattr(explainer, "complete_text", fake_complete_text)
    warnings = []
    asyncio.run(
        explainer.explain(
            "Can I go with 4 hours of oxygen and 40% battery?",
            {"intent": "route", "goal_type": "ice"},
            _load("mock_route.json"),
            warnings,
        )
    )
    assert warnings == []


def test_postcheck_ignores_list_markers_and_numbers_inside_words(monkeypatch):
    """List ordinals and identifiers such as EVA2 are not factual quantities."""
    async def fake_complete_text(system, user):
        return "1. First step.\n2. Next step for EVA2."

    monkeypatch.setattr(explainer, "complete_text", fake_complete_text)
    warnings = []
    asyncio.run(
        explainer.explain(
            "Find ice.",
            {"intent": "route", "goal_type": "ice"},
            _load("mock_route.json"),
            warnings,
        )
    )
    assert warnings == []


def test_postcheck_accepts_numbers_found_in_summary(monkeypatch):
    """Rounded planner facts in the LLM response do not create a warning."""
    async def fake_complete_text(system, user):
        return "The route covers 6 km, takes 2.2 hours, and has dust depth 0.25."

    monkeypatch.setattr(explainer, "complete_text", fake_complete_text)
    warnings = []
    text, source = asyncio.run(
        explainer.explain("Find ice.", {"intent": "route", "goal_type": "ice"}, _load("mock_route.json"), warnings)
    )
    assert "6 km" in text
    assert source == "llm"
    assert warnings == []


def test_explain_returns_template_when_llm_fails(monkeypatch):
    """A failing LLM is handled with the local template, never raised."""
    async def failing_complete_text(system, user):
        raise RuntimeError("LLM unavailable")

    monkeypatch.setattr(explainer, "complete_text", failing_complete_text)
    text, source = asyncio.run(
        explainer.explain("Find ice.", {"intent": "route", "goal_type": "ice"}, _load("mock_route.json"), [])
    )
    assert source == "fallback"
    assert "feasible" in text
    assert "distance: 6" in text
