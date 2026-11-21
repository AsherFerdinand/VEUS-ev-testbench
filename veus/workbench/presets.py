"""Three fictional VEUS classes assembled from explicit representative components."""

from .catalogue import catalogue
from .design import VehicleDesignV2
from .engineering import evaluate

# No manufacturer affiliation or inferred packaging dimensions/performance.
PRESETS = [
    dict(
        id="s1",
        name="VEUS S1 — Electric Sedan",
        appearance="sedan",
        description="Efficiency-focused everyday sedan: balanced usable energy, mass and motor output.",
        components=dict(
            battery="battery-s1",
            motor="motor-s1",
            inverter="inverter-260",
            body="body-s1",
            charging="charger-11",
            dcdc="dcdc-wide-2",
            gearbox="gearbox-9",
        ),
    ),
    dict(
        id="r1",
        name="VEUS R1 — Performance EV",
        appearance="performance",
        description="Low, wide fictional performance EV with greater declared motor output. No downforce or top-speed claim.",
        components=dict(
            battery="battery-r1",
            motor="motor-r1",
            inverter="inverter-r1",
            body="body-r1",
            charging="charger-wide-22",
            dcdc="dcdc-wide-2",
            gearbox="gearbox-heavy-9",
        ),
    ),
    dict(
        id="x1",
        name="VEUS X1 — Family SUV",
        appearance="suv",
        description="Larger fictional utility EV: more usable battery energy and greater declared body and pack mass.",
        components=dict(
            battery="battery-x1",
            motor="motor-x1",
            inverter="inverter-x1",
            body="body-x1",
            charging="charger-wide-22",
            dcdc="dcdc-wide-2",
            gearbox="gearbox-heavy-9",
        ),
    ),
]


def vehicle_presets():
    records = {record["id"]: record for record in catalogue()["components"]}
    result = []
    for preset in PRESETS:
        snapshot = VehicleDesignV2().model_dump(mode="json")
        snapshot.update(
            name=preset["name"],
            appearance=preset["appearance"],
            component_ids=dict(preset["components"]),
        )
        for kind, id in preset["components"].items():
            snapshot[kind] = dict(records[id]["parameters"])
        snapshot["operating_point"]["dc_voltage_v"] = snapshot["battery"][
            "nominal_voltage_v"
        ]
        vehicle = VehicleDesignV2.model_validate(snapshot)
        evaluated = evaluate(vehicle)
        result.append(
            dict(
                id=preset["id"],
                name=preset["name"],
                appearance=preset["appearance"],
                description=preset["description"],
                classification="illustrative",
                design=evaluated["design"],
                specifications=evaluated["specifications"],
                compatibility_status=evaluated["compatibility_status"],
                checks=evaluated["checks"],
                simulation_readiness=evaluated["simulation_readiness"],
                limitations=[
                    "Original fictional VEUS vehicle; not manufacturer specifications or physical validation.",
                    "Motor output is declared peak shaft power; default Lab experiments use continuous ratings.",
                    "Packaging/body illustration is not CAD or derived from battery capacity.",
                ],
            )
        )
    return dict(
        schema_version=1, catalogue_version=catalogue()["version"], presets=result
    )
