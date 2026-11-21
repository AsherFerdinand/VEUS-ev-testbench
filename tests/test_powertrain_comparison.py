"""The optional map changes only the selected loss model under matched inputs."""

from veus.workbench.powertrain_comparison import compare_models, ModelComparison
from veus.workbench.presets import vehicle_presets
from veus.workbench.adapter import ACKNOWLEDGEMENTS


def test_same_design_full_profile_model_comparison_is_reproducible():
    request = ModelComparison(
        vehicle=vehicle_presets()["presets"][0]["design"],
        acknowledgements=ACKNOWLEDGEMENTS,
        profile_id="urban",
    )
    result = compare_models(request)
    a, b = result["legacy"], result["mapped"]
    assert a["request"]["vehicle"] == b["request"]["vehicle"]
    assert a["request"]["profile_id"] == b["request"]["profile_id"]
    assert a["cycle"]["samples_simulated"] == b["cycle"]["samples_simulated"] == 601
    assert a["cycle"]["summary"]["maximum_energy_balance_error_j"] < 0.01
    assert b["cycle"]["summary"]["maximum_energy_balance_error_j"] < 0.01
    assert "efficiency_model" not in a["request"]
    assert b["request"]["efficiency_model"] == "illustrative_map"
    assert result == compare_models(request)
