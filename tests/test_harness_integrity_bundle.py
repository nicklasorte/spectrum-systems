from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "run_harness_integrity_bundle",
        Path("scripts/run_harness_integrity_bundle.py"),
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_verify_only_fails_when_review_exists_and_outputs_missing(tmp_path: Path, monkeypatch) -> None:
    module = _load_module()
    review = tmp_path / "harness_integrity_review.md"
    review.write_text("review exists", encoding="utf-8")
    monkeypatch.setattr(module, "REVIEW_DOC_PATH", review)

    rc = module.main(["--verify-only", "--output-dir", str(tmp_path / "missing")])
    assert rc == 2


def test_run_bundle_emits_required_outputs(tmp_path: Path, monkeypatch) -> None:
    module = _load_module()
    review = tmp_path / "harness_integrity_review.md"
    review.write_text("review exists", encoding="utf-8")
    monkeypatch.setattr(module, "REVIEW_DOC_PATH", review)

    out_dir = tmp_path / "bundle"
    rc = module.main(["--output-dir", str(out_dir)])
    assert rc == 0

    for name in module.REQUIRED_OUTPUTS:
        assert (out_dir / name).exists(), f"missing output {name}"
