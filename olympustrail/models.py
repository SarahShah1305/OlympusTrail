from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Position(StrictModel):
    row: int | None = Field(default=None, ge=0, strict=True)
    col: int | None = Field(default=None, ge=0, strict=True)
    lon: float | None = Field(default=None, ge=-180, le=360)
    lat: float | None = Field(default=None, ge=-90, le=90)

    @model_validator(mode="after")
    def coordinate_pair(self):
        grid_pair = self.row is not None and self.col is not None
        geo_pair = self.lon is not None and self.lat is not None
        if grid_pair and self.lon is None and self.lat is None:
            return self
        if geo_pair and self.row is None and self.col is None:
            return self
        raise ValueError("Supply exactly one complete pair: row/col or lon/lat")


class RiskWeights(StrictModel):
    slope: float = Field(default=0.4, ge=0, le=100)
    radiation: float = Field(default=0.2, ge=0, le=100)
    temperature: float = Field(default=0.25, ge=0, le=100)
    dust: float = Field(default=0.15, ge=0, le=100)

    @model_validator(mode="after")
    def nonzero(self):
        if sum(self.model_dump().values()) <= 0:
            raise ValueError("At least one risk weight must be positive")
        return self


class MissionParameters(StrictModel):
    """Illustrative hackathon settings; replace with Person 5's parameter table."""
    walking_speed_kmh: float = Field(default=3.0, gt=0, le=20)
    base_power_w: float = Field(default=100.0, gt=0, le=5000)
    movement_energy_wh_km: float = Field(default=10.0, ge=0, le=5000)
    cold_power_w_per_k: float = Field(default=2.0, ge=0, le=100)
    cold_reference_k: float = Field(default=230.0, ge=100, le=350)
    max_slope_deg: float = Field(default=15.0, gt=0, le=45)
    max_dust_optical_depth: float = Field(default=1.0, gt=0, le=10)


class RouteRequest(StrictModel):
    start: Position
    goal: Position | None = None
    goal_type: Literal["ice"] | None = None
    ice_min_consistency: float = Field(default=0.75, ge=-1, le=1)
    min_goal_distance_km: float = Field(default=0.0, ge=0, le=1000)
    oxygen_hours: float = Field(default=4.0, gt=0, le=1000)
    battery_wh: float = Field(default=1000.0, gt=0, le=1e7)
    reserve_fraction: float = Field(default=0.2, ge=0, lt=1)
    return_to_start: bool = True
    mode: Literal["scenario", "observations"] = "scenario"
    avoid: list[Literal["steep", "dust", "cold", "unknown_thermal"]] = Field(default_factory=list)
    weights: RiskWeights = Field(default_factory=RiskWeights)
    parameters: MissionParameters = Field(default_factory=MissionParameters)
    max_search_labels: int = Field(default=100000, ge=10, le=300000)

    @model_validator(mode="after")
    def goal_choice(self):
        if (self.goal is None) == (self.goal_type is None):
            raise ValueError("Supply either goal or goal_type='ice', not both")
        return self


class SiteRequest(StrictModel):
    limit: int = Field(default=5, ge=1, le=20)
    min_separation_km: float = Field(default=15.0, ge=0, le=500)
    max_slope_deg: float = Field(default=10.0, gt=0, le=45)
    mode: Literal["scenario", "observations"] = "scenario"
