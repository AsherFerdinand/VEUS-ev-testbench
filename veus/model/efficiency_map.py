"""Bounded illustrative motor maps; no manufacturer, thermal or calibration claim."""

from bisect import bisect_right
import hashlib
import math
from veus.model.motor import ElectricMotor
from veus.replay.analysis import canonical

RPM_FRACTIONS = [0.0, 0.3, 0.65, 1.0]
TORQUE_FRACTIONS = [0.0, 0.2, 0.6, 1.0]
MOTORING = [
    [0.72, 0.78, 0.81, 0.80],
    [0.78, 0.89, 0.94, 0.925],
    [0.80, 0.91, 0.955, 0.94],
    [0.77, 0.88, 0.93, 0.90],
]
REGENERATION = [
    [0.60, 0.67, 0.70, 0.68],
    [0.69, 0.82, 0.88, 0.86],
    [0.71, 0.85, 0.90, 0.88],
    [0.67, 0.80, 0.86, 0.83],
]
REGEN_TORQUE_FRACTION = 0.7


class UnsupportedOperatingPoint(ValueError):
    """A requested point is not covered; extrapolation is prohibited."""


def bilinear(x, y, x_axis, y_axis, values):
    if (
        not math.isfinite(x)
        or not math.isfinite(y)
        or x < x_axis[0]
        or x > x_axis[-1]
        or y < y_axis[0]
        or y > y_axis[-1]
    ):
        raise UnsupportedOperatingPoint(
            "Operating point outside efficiency-map grid; no extrapolation"
        )
    i = max(0, min(len(x_axis) - 2, bisect_right(x_axis, x) - 1))
    j = max(0, min(len(y_axis) - 2, bisect_right(y_axis, y) - 1))
    a = (x - x_axis[i]) / (x_axis[i + 1] - x_axis[i])
    b = (y - y_axis[j]) / (y_axis[j + 1] - y_axis[j])
    return (1 - a) * ((1 - b) * values[i][j] + b * values[i][j + 1]) + a * (
        (1 - b) * values[i + 1][j] + b * values[i + 1][j + 1]
    )


class IllustrativeMotorMap:
    def __init__(self, motor: ElectricMotor):
        self.motor = motor

    def torque_limit(self, rpm, regenerative=False):
        if not math.isfinite(rpm) or rpm < 0 or rpm > self.motor.max_rpm:
            raise UnsupportedOperatingPoint("Motor speed outside map region")
        return self.motor.max_available_torque(rpm) * (
            REGEN_TORQUE_FRACTION if regenerative else 1
        )

    def efficiency(self, rpm, torque_nm, regenerative=False):
        if not math.isfinite(torque_nm) or torque_nm < 0:
            raise UnsupportedOperatingPoint(
                "Map torque magnitude must be finite and nonnegative"
            )
        limit = self.torque_limit(rpm, regenerative)
        if torque_nm > limit + 1e-7:
            raise UnsupportedOperatingPoint(
                "Torque outside selected constant-torque/power/regen envelope"
            )
        # Only numerical round-off at an accepted boundary is clamped, never requested demand.
        torque_nm = min(torque_nm, limit)
        return bilinear(
            rpm / self.motor.max_rpm,
            torque_nm / self.motor.max_torque_nm,
            RPM_FRACTIONS,
            TORQUE_FRACTIONS,
            REGENERATION if regenerative else MOTORING,
        )

    def metadata(self):
        data = dict(
            id="veus-illustrative-motor-map-v1",
            classification="illustrative",
            source="Original VEUS analytical assumptions; not measured/vendor data",
            rpm_fraction_axis=list(RPM_FRACTIONS),
            torque_fraction_axis=list(TORQUE_FRACTIONS),
            motoring_efficiency=[list(row) for row in MOTORING],
            regenerative_efficiency=[list(row) for row in REGENERATION],
            scaling=dict(
                maximum_rpm=self.motor.max_rpm,
                selected_torque_rating_nm=self.motor.max_torque_nm,
                selected_power_rating_kw=self.motor.max_power_kw,
            ),
            region="0 <= rpm <= selected maximum; |torque| <= retained constant-torque/constant-power envelope; regen torque <= 0.7 of that envelope",
            regenerative_torque_fraction=REGEN_TORQUE_FRACTION,
            interpolation="Bilinear within grid and physical envelope; unsupported points are unavailable, not extrapolated",
            limitations=[
                "Normalized illustrative shape scaled to explicit selected ratings; not technology-derived efficiency or manufacturer calibration.",
                "Zero-power points incur zero conversion power; standstill copper losses are not represented.",
                "Inverter uses the declared constant efficiency in both directions; no phase-current or temperature map.",
            ],
        )
        return data | {"sha256": hashlib.sha256(canonical(data)).hexdigest()}
