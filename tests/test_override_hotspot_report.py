from spectrum_systems.contracts import load_example, validate_artifact

def test_override_hotspot_example_valid() -> None:
    validate_artifact(load_example("override_hotspot_report"), "override_hotspot_report")
