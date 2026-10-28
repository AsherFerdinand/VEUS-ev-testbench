"""Illustrative configurations, not manufacturer specifications or calibration."""

from veus.sim.session import RunConfig


def vehicle_presets():
    specs = [
        ("hatch", "Mica", "Compact hatchback", 1350, 100, 220, 42, "#a3dfbd"),
        ("sedan", "Linea", "Electric sedan", 1800, 150, 300, 60, "#8ebce8"),
        ("coupe", "Velo", "Performance coupe", 1700, 250, 450, 72, "#e7a578"),
        ("suv", "Terra", "Electric SUV", 2250, 200, 400, 85, "#c2b1e6"),
    ]
    return [
        dict(
            id=key,
            name=name,
            category=category,
            color=color,
            classification="Illustrative preset; not calibrated manufacturer data",
            drivetrain="Existing simplified equivalent motor and two-ratio drivetrain",
            maximum_speed_kmh=None,
            config=RunConfig(
                mass_kg=mass,
                max_power_kw=power,
                max_torque_nm=torque,
                battery_capacity_kwh=capacity,
                duration_s=120,
            ).model_dump(mode="json"),
        )
        for key, name, category, mass, power, torque, capacity, color in specs
    ]
