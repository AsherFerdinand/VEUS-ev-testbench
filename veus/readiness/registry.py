"""One typed registry for API evaluation and user-facing requirements."""

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Capability:
    id: str
    name: str
    description: str
    required_signals: tuple[str, ...]
    optional_signals: tuple[str, ...]
    quality_conditions: tuple[str, ...]
    assumptions: tuple[str, ...]
    workspace: str
    availability_explanation: str
    implemented: bool = True


CAPABILITIES = (
    Capability(
        "recorded_replay",
        "Recorded journey replay",
        "A generic EV illustration follows recorded speed; no predictive physics is run.",
        ("time_s", "vehicle_speed_ms"),
        ("battery_voltage_v", "battery_current_a", "battery_soc"),
        ("valid_speed_intervals",),
        (),
        "analyse",
        "Ready for recorded-speed replay. Distance is derived; this does not validate a vehicle model.",
    ),
    Capability(
        "speed_acceleration",
        "Speed and acceleration analysis",
        "Inspect speed and local finite-difference acceleration, which may amplify noise.",
        ("time_s", "vehicle_speed_ms"),
        ("longitudinal_acceleration_ms2",),
        ("acceleration_stencil",),
        (),
        "analyse",
        "Ready for descriptive speed and estimated acceleration analysis, not accelerometer validation.",
    ),
    Capability(
        "voltage_inspection",
        "Battery voltage inspection",
        "Inspect available voltage samples with their timestamps.",
        ("time_s", "battery_voltage_v"),
        (),
        ("finite_required_samples",),
        (),
        "analyse",
        "Ready to inspect recorded voltage; accuracy is not authenticated.",
    ),
    Capability(
        "current_inspection",
        "Signed battery current inspection",
        "Inspect current without assuming discharge or charge polarity.",
        ("time_s", "battery_current_a"),
        (),
        ("finite_required_samples",),
        (),
        "analyse",
        "Ready to inspect signed current; its physical polarity may remain unknown.",
    ),
    Capability(
        "signed_power",
        "Signed electrical power",
        "Compute samplewise voltage × signed current, without a discharge/regen interpretation.",
        ("time_s", "battery_voltage_v", "battery_current_a"),
        (),
        ("joint_electrical_samples",),
        (),
        "analyse",
        "Ready for the signed V×I calculation. Column co-location does not establish synchronization or accuracy.",
    ),
    Capability(
        "energy_consumption",
        "Electrical energy used / received",
        "Integrate complete V/I recordings only with resolved polarity and stated evidence.",
        ("time_s", "battery_voltage_v", "battery_current_a"),
        (),
        ("complete_electrical_window",),
        (
            "current_polarity",
            "synchronization_confirmed",
            "measurement_quality_documented",
        ),
        "analyse",
        "Complete electrical inputs and asserted evidence are supplied. Energy remains a derived estimate, not proof of measurement validity.",
    ),
    Capability(
        "regenerative_energy",
        "Regeneration-specific energy",
        "Charging energy alone does not identify its source.",
        ("time_s", "vehicle_speed_ms", "battery_voltage_v", "battery_current_a"),
        (),
        ("complete_electrical_window",),
        ("current_polarity", "charging_origin_established"),
        "analyse",
        "VEUS does not implement a regeneration-specific energy total; V/I and deceleration cannot establish the origin of all charging.",
        False,
    ),
    Capability(
        "motor_efficiency",
        "Motor efficiency",
        "Isolated motor efficiency needs electrical motor-boundary power and mechanical output evidence.",
        (
            "time_s",
            "motor_torque_nm",
            "motor_speed_rad_s",
            "battery_voltage_v",
            "battery_current_a",
        ),
        (),
        ("finite_required_samples",),
        ("torque_sign_confirmed", "synchronization_confirmed", "motor_boundary_power"),
        "analyse",
        "Not implemented as a measured-data analysis. Shaft torque/speed and pack V/I do not isolate motor efficiency from inverter, auxiliaries and drivetrain losses.",
        False,
    ),
    Capability(
        "longitudinal_validation",
        "Longitudinal physical-model validation inputs",
        "Check whether a complete explicit Phase 8 experiment can be taken forward; no comparison is executed here.",
        (
            "time_s",
            "vehicle_speed_ms",
            "motor_torque_nm",
            "brake_force_n",
            "road_gradient_rad",
        ),
        ("battery_soc",),
        ("complete_required_window", "nonnegative_drive_torque"),
        (
            "measured_origin",
            "torque_sign_confirmed",
            "synchronization_confirmed",
            "measurement_quality_documented",
            "operating_conditions_documented",
            "phase8_experiment",
        ),
        "validate",
        "Inputs and an explicit experiment are supplied for evaluation. AVAILABLE is not a PASS or a physical-validation conclusion.",
    ),
)


def registry():
    return [asdict(cap) for cap in CAPABILITIES]


SIGNAL_NAMES = {
    "time_s": "timestamp",
    "vehicle_speed_ms": "vehicle speed",
    "battery_voltage_v": "battery voltage",
    "battery_current_a": "battery current",
    "battery_soc": "battery SOC",
    "motor_torque_nm": "motor torque",
    "motor_speed_rad_s": "motor rotational speed",
    "brake_force_n": "brake force",
    "road_gradient_rad": "road gradient",
    "ambient_temperature_c": "outside air temperature",
    "longitudinal_acceleration_ms2": "recorded longitudinal acceleration",
    "battery_power_w": "recorded battery power",
    "position_m": "recorded longitudinal position",
    "energy_wh": "recorded electrical energy",
}
