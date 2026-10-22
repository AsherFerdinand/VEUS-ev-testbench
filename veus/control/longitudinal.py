"""Proportional speed control, PD headway control and latched TTC-based AEB.

These illustrative algorithms do not establish production ADAS safety performance.
"""
from dataclasses import dataclass
import math


@dataclass(frozen=True)
class Observation:
    speed_ms: float
    gap_m: float | None = None
    lead_speed_ms: float = 0.

    def __post_init__(self):
        values = (self.speed_ms, self.lead_speed_ms)
        if self.gap_m is not None:
            values += (self.gap_m,)
        if not all(math.isfinite(v) for v in values) or min(self.speed_ms, self.lead_speed_ms) < 0:
            raise ValueError('Finite observations and nonnegative speeds required')

    @property
    def ttc_s(self) -> float | None:
        closing = self.speed_ms-self.lead_speed_ms
        if self.gap_m is None or closing <= 1e-6:
            return None
        return max(0., self.gap_m)/closing


@dataclass(frozen=True)
class Command:
    acceleration_ms2: float
    state: str


class LongitudinalController:
    def __init__(self, mode: str, target_speed_ms: float, headway_s: float = 1.8,
                 standstill_gap_m: float = 5., max_acceleration_ms2: float = 2.,
                 comfort_deceleration_ms2: float = 3., aeb_ttc_s: float = 2.,
                 emergency_deceleration_ms2: float = 9.81):
        values = (target_speed_ms, headway_s, standstill_gap_m, max_acceleration_ms2,
                  comfort_deceleration_ms2, aeb_ttc_s, emergency_deceleration_ms2)
        if mode not in {'cruise','acc','aeb'} or not all(math.isfinite(v) and v >= 0 for v in values):
            raise ValueError('Invalid controller configuration')
        self.mode = mode
        self.target = target_speed_ms
        self.headway = headway_s
        self.standstill_gap = standstill_gap_m
        self.max_accel = max_acceleration_ms2
        self.comfort_decel = comfort_deceleration_ms2
        self.aeb_ttc = aeb_ttc_s
        self.emergency_decel = emergency_deceleration_ms2
        self.emergency_latched = False

    def update(self, observation: Observation) -> Command:
        o = observation
        speed_accel = 0.7*(self.target-o.speed_ms)
        accel = speed_accel
        state = 'cruise'
        if self.mode == 'acc' and o.gap_m is not None:
            desired_gap = self.standstill_gap+self.headway*o.speed_ms
            gap_accel = 0.3*(o.gap_m-desired_gap)+0.9*(o.lead_speed_ms-o.speed_ms)
            accel = min(speed_accel, gap_accel)
            state = 'following' if gap_accel < speed_accel else 'cruise'
        if self.mode == 'aeb' and o.gap_m is not None:
            risk = ((o.ttc_s is not None and o.ttc_s <= self.aeb_ttc)
                    or o.gap_m <= self.standstill_gap)
            # Latch until reset: no automatic re-acceleration after emergency stop.
            self.emergency_latched |= risk
            if self.emergency_latched:
                return Command(-self.emergency_decel, 'emergency_braking')
        return Command(max(-self.comfort_decel, min(self.max_accel, accel)), state)
