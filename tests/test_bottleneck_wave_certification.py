from spectrum_systems.contracts import validate_artifact, load_example

def test_certification_example_valid() -> None:
    validate_artifact(load_example("bottleneck_wave_certification_record"), "bottleneck_wave_certification_record")
