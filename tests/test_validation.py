import pytest
from veus.validation.physics import physics_references


def test_analytical_reference_bounds_and_convergence():
    coarse = {t.name: t for t in physics_references(0.01)}
    fine = {t.name: t for t in physics_references(0.005)}
    assert len(coarse) == 11
    for name, trace in coarse.items():
        assert trace.max_error <= trace.tolerance, name
        assert fine[name].max_error <= fine[name].tolerance, name
    for name in (
        "acceleration_position",
        "braking_position",
        "gradient_position",
        "coasting_speed",
        "coasting_position",
    ):
        assert coarse[name].max_error / fine[name].max_error == pytest.approx(
            2, rel=0.02
        )
    assert coarse["braking_position"].reference[-1] == 25
    assert coarse["acceleration_position"].reference[-1] == 8
    assert coarse["coasting_speed"].reference[-1] < 20


@pytest.mark.parametrize("dt", [0, -0.1, float("nan"), 0.2, 0.03])
def test_invalid_reference_step(dt):
    with pytest.raises(ValueError):
        physics_references(dt)
