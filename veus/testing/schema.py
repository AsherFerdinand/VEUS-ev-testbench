"""Versioned, strict scenario/result contracts; JSON uses SI-labelled fields."""

from typing import Literal
from pydantic import Field, model_validator
from veus.contracts import StrictModel
from veus.sim.session import Controls, RunConfig

MetricName = Literal[
    "collision_count",
    "minimum_separation_m",
    "minimum_ttc_s",
    "impact_ego_speed_kmh",
    "impact_closing_speed_kmh",
    "braking_distance_m",
    "brake_onset_time_s",
    "stop_time_s",
    "aeb_detection_time_s",
    "controller_response_s",
    "final_speed_error_kmh",
    "final_gap_error_m",
    "max_energy_balance_error_j",
    "acc_target_speed_error_kmh",
    "speed_mae_ms",
    "speed_max_abs_error_ms",
    "radar_distance_mae_m",
    "radar_distance_max_abs_error_m",
    "radar_closing_speed_mae_ms",
    "speed_unavailable_fraction",
    "radar_unavailable_fraction",
    "controller_fallback_fraction",
    "fault_activation_count",
    "minimum_separation_delta_m",
    "aeb_detection_delay_vs_ideal_s",
]
UNITS = dict(
    collision_count="count",
    minimum_separation_m="m",
    minimum_ttc_s="s",
    impact_ego_speed_kmh="km/h",
    impact_closing_speed_kmh="km/h",
    braking_distance_m="m",
    brake_onset_time_s="s",
    stop_time_s="s",
    aeb_detection_time_s="s",
    controller_response_s="s",
    final_speed_error_kmh="km/h",
    final_gap_error_m="m",
    max_energy_balance_error_j="J",
    acc_target_speed_error_kmh="km/h",
    speed_mae_ms="m/s",
    speed_max_abs_error_ms="m/s",
    radar_distance_mae_m="m",
    radar_distance_max_abs_error_m="m",
    radar_closing_speed_mae_ms="m/s",
    speed_unavailable_fraction="fraction",
    radar_unavailable_fraction="fraction",
    controller_fallback_fraction="fraction",
    fault_activation_count="count",
    minimum_separation_delta_m="m",
    aeb_detection_delay_vs_ideal_s="s",
)


class ControlEvent(StrictModel):
    time_s: float = Field(ge=0)
    controls: Controls


class Criterion(StrictModel):
    id: str = Field(min_length=1, max_length=100)
    description: str = Field(min_length=1, max_length=500)
    metric: MetricName
    operator: Literal["<=", ">=", "=="]
    threshold: float
    rationale: str = Field(min_length=1, max_length=2000)


class Scenario(StrictModel):
    schema_version: Literal[1] = 1
    id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{0,63}$")
    description: str = Field(min_length=1, max_length=2000)
    config: RunConfig
    controls: list[ControlEvent] = Field(default_factory=list)
    criteria: list[Criterion] = Field(default_factory=list)

    @model_validator(mode="after")
    def consistent(self):
        if self.controls and self.config.mode != "manual":
            raise ValueError("Timed pedal commands are supported only in manual mode")
        times = [e.time_s for e in self.controls]
        if times != sorted(set(times)):
            raise ValueError("Control event times must be strictly increasing")
        for value in [
            self.config.duration_s,
            self.config.detection_delay_s,
            self.config.actuation_delay_s,
            self.config.lead_brake_start_s,
            *times,
        ]:
            if abs(value / 0.01 - round(value / 0.01)) > 1e-7:
                raise ValueError(
                    "Scenario times/delays must lie on the 0.01 s physics grid"
                )
        if times and times[-1] >= self.config.duration_s:
            raise ValueError("Control events must precede the run horizon")
        if len({r.id for r in self.criteria}) != len(self.criteria):
            raise ValueError("Requirement IDs must be unique within a scenario")
        if (
            self.config.mode == "aeb"
            and self.config.lead_brake_start_s >= self.config.duration_s
        ):
            raise ValueError("AEB lead-braking event must occur before the run horizon")
        return self


class Metrics(StrictModel):
    collision_count: int
    minimum_separation_m: float | None
    minimum_ttc_s: float | None
    impact_ego_speed_kmh: float | None
    impact_closing_speed_kmh: float | None
    braking_distance_m: float | None
    brake_onset_time_s: float | None
    stop_time_s: float | None
    aeb_detection_time_s: float | None
    controller_response_s: float | None
    final_speed_error_kmh: float | None
    final_gap_error_m: float | None
    max_energy_balance_error_j: float
    acc_target_speed_error_kmh: float | None = None
    speed_mae_ms: float | None = None
    speed_max_abs_error_ms: float | None = None
    radar_distance_mae_m: float | None = None
    radar_distance_max_abs_error_m: float | None = None
    radar_closing_speed_mae_ms: float | None = None
    speed_unavailable_fraction: float | None = None
    radar_unavailable_fraction: float | None = None
    controller_fallback_fraction: float | None = None
    fault_activation_count: int = 0
    minimum_separation_delta_m: float | None = None
    aeb_detection_delay_vs_ideal_s: float | None = None


class RequirementResult(StrictModel):
    id: str
    description: str
    metric: MetricName
    measured: float | None
    unit: str
    operator: str
    threshold: float
    rationale: str
    status: Literal["PASS", "FAIL", "INCONCLUSIVE"]
    evidence: str


class IdealBaseline(StrictModel):
    config: RunConfig
    metrics: Metrics
    termination: Literal["completed", "collision"]
    duration_executed_s: float
    telemetry: list[dict]


class ScenarioResult(StrictModel):
    schema_version: Literal[1] = 1
    scenario_id: str
    status: Literal["PASS", "FAIL", "INCONCLUSIVE"]
    termination: Literal["completed", "collision"]
    duration_executed_s: float
    metrics: Metrics
    requirements: list[RequirementResult]
    telemetry: list[dict]
    sensor_fault_events: list[dict] = Field(default_factory=list)
    ideal_baseline: IdealBaseline | None = None
