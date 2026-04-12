from __future__ import annotations

import json
from pathlib import Path

from scripts import build_preflight_pqx_wrapper as wrapper_builder
from scripts.run_contract_preflight import ChangedPathDetectionResult


def _detection(
    *,
    changed_paths: list[str],
    mode: str = "base_head_diff",
    trust_level: str = "normal",
    fallback_used: bool = False,
    reason_codes: list[str] | None = None,
) -> ChangedPathDetectionResult:
    return ChangedPathDetectionResult(
        changed_paths=changed_paths,
        changed_path_detection_mode=mode,
        refs_attempted=["base..head"],
        fallback_used=fallback_used,
        warnings=[],
        ref_resolution_records=[{"ref": "base..head", "status": "succeeded"}],
        trust_level=trust_level,
        bounded_runtime=True,
        reason_codes=reason_codes or [],
    )


def _template() -> dict[str, object]:
    return {
        "artifact_type": "codex_pqx_task_wrapper",
        "execution_intent": {},
        "governance": {},
        "changed_paths": [],
    }


def test_builder_fails_fast_for_invalid_refs_insufficient_evidence(monkeypatch, tmp_path: Path) -> None:
    output_path = tmp_path / "wrapper.json"
    trace_path = tmp_path / "trace.json"
    template_path = tmp_path / "template.json"
    template_path.write_text(json.dumps(_template()), encoding="utf-8")

    monkeypatch.setattr(
        wrapper_builder,
        "_parse_args",
        lambda: type(
            "Args",
            (),
            {
                "base_ref": "bad-base",
                "head_ref": "bad-head",
                "changed_path": [],
                "output_path": str(output_path),
                "template_path": str(template_path),
                "trace_output_path": str(trace_path),
            },
        )(),
    )
    monkeypatch.setattr(
        wrapper_builder,
        "detect_changed_paths",
        lambda **_kwargs: _detection(
            changed_paths=[],
            mode="insufficient_diff_evidence",
            trust_level="insufficient",
            fallback_used=True,
            reason_codes=["invalid_git_ref_range", "insufficient_changed_path_evidence"],
        ),
    )

    assert wrapper_builder.main() == 2
    assert not output_path.exists()


def test_builder_marks_degraded_fallback_explicitly() -> None:
    detection = _detection(
        changed_paths=["contracts/schemas/a.schema.json"],
        mode="base_to_current_head_fallback",
        trust_level="degraded",
        fallback_used=True,
        reason_codes=["degraded_changed_path_mode"],
    )
    payload = wrapper_builder.build_wrapper_payload(
        template_payload=_template(),
        detection=detection,
    )

    trace = wrapper_builder._changed_path_trace(detection)
    assert payload["changed_paths"] == ["contracts/schemas/a.schema.json"]
    assert trace["changed_path_detection_mode"] == "base_to_current_head_fallback"
    assert trace["trust_level"] == "degraded"
    assert trace["fallback_used"] is True
    assert trace["reason_codes"] == ["degraded_changed_path_mode"]


def test_builder_rejects_empty_changed_paths() -> None:
    try:
        wrapper_builder.build_wrapper_payload(
            template_payload=_template(),
            detection=_detection(changed_paths=[]),
        )
    except wrapper_builder.WrapperBuildError as exc:
        assert "changed_paths resolved to empty" in str(exc)
    else:
        raise AssertionError("expected empty changed_paths to fail closed")


def test_builder_output_is_deterministic(monkeypatch, tmp_path: Path) -> None:
    output_path = tmp_path / "wrapper.json"
    trace_path = tmp_path / "trace.json"
    template_path = tmp_path / "template.json"
    template_path.write_text(json.dumps(_template()), encoding="utf-8")

    monkeypatch.setattr(
        wrapper_builder,
        "_parse_args",
        lambda: type(
            "Args",
            (),
            {
                "base_ref": "base",
                "head_ref": "head",
                "changed_path": [],
                "output_path": str(output_path),
                "template_path": str(template_path),
                "trace_output_path": str(trace_path),
            },
        )(),
    )
    monkeypatch.setattr(
        wrapper_builder,
        "detect_changed_paths",
        lambda **_kwargs: _detection(
            changed_paths=[
                "contracts/examples/z.json",
                "contracts/schemas/a.schema.json",
                "contracts/examples/z.json",
            ],
            mode="base_head_diff",
            trust_level="normal",
            fallback_used=False,
        ),
    )

    assert wrapper_builder.main() == 0
    first = output_path.read_text(encoding="utf-8")
    assert wrapper_builder.main() == 0
    second = output_path.read_text(encoding="utf-8")

    assert first == second
    payload = json.loads(first)
    assert payload["changed_paths"] == ["contracts/examples/z.json", "contracts/schemas/a.schema.json"]
