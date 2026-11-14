"""Request and response schemas for the AI guide."""

from typing import Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field


class Coordinates(BaseModel):
    """Longitude and latitude position accepted by the planner."""

    lon: float
    lat: float


class GridPosition(BaseModel):
    """Row and column position accepted by the planner."""

    row: int
    col: int


class ParsedRequest(BaseModel):
    """Normalized user intent and constraints for the planner contract."""

    intent: Literal["route", "sites", "briefing", "unknown"] = "unknown"
    start: Optional[Union[GridPosition, Coordinates]] = None
    goal_type: Optional[Literal["ice", "shelter", "base_site"]] = None
    oxygen_hours: Optional[float] = None
    battery_wh: Optional[float] = None
    battery_pct: Optional[float] = None
    local_time_h: Optional[Literal[0, 6, 12, 18]] = None
    avoid: List[Literal["steep", "dust", "cold", "unknown_thermal"]] = Field(default_factory=list)
    unsupported: List[str] = Field(default_factory=list)
    confidence: float = Field(default=0.5, ge=0, le=1)


class AskRequest(BaseModel):
    """Incoming natural-language map question."""

    question: str
    map_start: Optional[Coordinates] = None


class AskResponse(BaseModel):
    """AI guide answer together with parsed intent and planner output."""

    parsed: ParsedRequest
    route: Optional[Dict] = None
    explanation: str
    source: Literal["llm", "fallback"]
    warnings: List[str] = Field(default_factory=list)
