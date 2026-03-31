#!/usr/bin/env python3
"""Fail-closed preflight gate for governed contract/schema changes."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from spectrum_systems.contracts import load_schema  # noqa: E402
from spectrum_systems.governance.contract_impact import analyze_contract_impact  # noqa: E402

DEFAULT_REQUIRED_SMOKE_TESTS = [
    "tests/test_roadmap_eligibility.py",
    "tests/test_next_step_decision.py",
    "tests/test_next_step_decision_policy.py",
    "tests/test_cycle_runner.py",
]

MASKING_MARKERS = (
    "schema validation",
    "validationerror",
    "required property",
    "roadmap_eligibility_artifact",
    "next_step_decision_artifact",
)


@dataclass
class CommandResult:
    command: list[str]
    returncode: int
    stdout: str
    stderr: str

    @property
    def combined_output(self) -> str:
        return f"{self.stdout}\n{self.stderr}".strip()


def _run(command: list[str], cwd: Path) -> CommandResult:
    proc = subprocess.run(command, cwd=cwd, check=False, capture_output=True, text=True)
    return CommandResult(command=command, returncode=proc.returncode, stdout=proc.stdout, stderr=proc.stderr)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fail-closed contract/schema preflight gate")
    parser.add_argument("--base-ref", default="origin/main", help="Git base ref used for diff detection")
    parser.add_argument("--head-ref", default="HEAD", help="Git head ref used for diff detection")
    parser.add_argument("--changed-path", action="append", default=[], help="Optional explicit changed paths")
    parser.add_argument("--output-dir", default="outputs/contract_preflight", help="Preflight output directory")
    return parser.parse_args()


def detect_changed_paths(repo_root: Path, base_ref: str, head_ref: str, explicit: list[str] | None = None) -> list[str]:
    if explicit:
        return sorted(set(explicit))

    merge_base = _run(["git", "merge-base", base_ref, head_ref], cwd=repo_root)
    if merge_base.returncode == 0 and merge_base.stdout.strip():
        baseline = merge_base.stdout.strip()
    else:
        baseline = "HEAD~1"

    diff = _run(["git", "diff", "--name-only", f"{baseline}..{head_ref}"], cwd=repo_root)
    if diff.returncode != 0:
        raise RuntimeError(f"unable to detect changed paths: {diff.combined_output}")
    return sorted({line.strip() for line in diff.stdout.splitlines() if line.strip()})


def classify_changed_contracts(changed_paths: list[str]) -> dict[str, list[str]]:
    changed_schemas = sorted(
        path for path in changed_paths if path.startswith("contracts/schemas/") and path.endswith(".schema.json")
    )
    changed_examples = sorted(path for path in changed_paths if path.startswith("contracts/examples/") and path.endswith(".json"))
    governed_defs = sorted(
        path
        for path in changed_paths
        if path.startswith("contracts/") and path.endswith(".schema.json") and not path.startswith("contracts/schemas/")
    )
    return {
        "changed_contract_paths": changed_schemas,
        "changed_example_paths": changed_examples,
        "changed_governed_definitions": governed_defs,
    }


def build_impact_map(repo_root: Path, changed_contract_paths: list[str], changed_example_paths: list[str]) -> dict[str, list[str]]:
    impact = analyze_contract_impact(
        repo_root=repo_root,
        changed_contract_paths=changed_contract_paths,
        changed_example_paths=changed_example_paths,
        baseline_ref="HEAD",
    )

    impacted_tests = set(impact.get("impacted_test_paths", []))
    impacted_runtime = set(impact.get("impacted_runtime_paths", []))
    impacted_scripts = set(impact.get("impacted_script_paths", []))

    producers = sorted(path for path in impacted_runtime if "orchestration" in path or "modules/runtime" in path)
    fixtures = sorted(path for path in impacted_tests if "/fixtures/" in path or "/helpers/" in path)
    consumers = sorted(path for path in impacted_tests if path not in fixtures)

    contract_names = {
        Path(path).name.replace(".schema.json", "")
        for path in changed_contract_paths
        if path.endswith(".schema.json")
    }

    required_smoke_tests: list[str] = []
    if "roadmap_eligibility_artifact" in contract_names:
        required_smoke_tests.extend(DEFAULT_REQUIRED_SMOKE_TESTS)

    required_smoke_tests.extend(path for path in consumers if path.endswith(".py") and Path(path).name.startswith("test_"))

    return {
        "producers": producers,
        "fixtures_or_builders": fixtures,
        "consumers": consumers,
        "scripts": sorted(impacted_scripts),
        "required_smoke_tests": sorted(set(required_smoke_tests)),
        "contract_impact_artifact": impact,
    }


def resolve_test_targets(repo_root: Path, impacted_paths: list[str]) -> list[str]:
    targets: set[str] = set()
    for rel_path in impacted_paths:
        candidate = Path(rel_path)
        if candidate.name.startswith("test_") and candidate.suffix == ".py":
            targets.add(rel_path)
            continue

        if rel_path.startswith("tests/helpers/") or rel_path.startswith("tests/fixtures/"):
            stem = candidate.stem
            search = _run(["rg", "-l", stem, "tests"], cwd=repo_root)
            if search.returncode == 0:
                for line in search.stdout.splitlines():
                    if line.startswith("tests/test_") and line.endswith(".py"):
                        targets.add(line.strip())

    return sorted(targets)


def _schema_name_from_example(path: str) -> str:
    return Path(path).name.replace(".json", "")


def validate_examples(changed_example_paths: list[str]) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    for rel_path in changed_example_paths:
        full_path = REPO_ROOT / rel_path
        if not full_path.exists():
            failures.append({"path": rel_path, "error": "example file missing"})
            continue

        payload = json.loads(full_path.read_text(encoding="utf-8"))
        schema_name = _schema_name_from_example(rel_path)
        try:
            schema = load_schema(schema_name)
        except Exception as exc:
            failures.append({"path": rel_path, "error": f"schema load failed for {schema_name}: {exc}"})
            continue

        validator = Draft202012Validator(schema, format_checker=FormatChecker())
        try:
            validator.validate(payload)
        except Exception as exc:
            failures.append({"path": rel_path, "error": str(exc)})
    return failures


def run_targeted_pytests(paths: list[str]) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    for path in paths:
        cmd = [sys.executable, "-m", "pytest", "-q", path]
        result = _run(cmd, cwd=REPO_ROOT)
        if result.returncode != 0:
            failures.append(
                {
                    "path": path,
                    "command": " ".join(cmd),
                    "returncode": result.returncode,
                    "output": result.combined_output[-4000:],
                }
            )
    return failures


def detect_masked_failures(failures: list[dict[str, Any]]) -> list[dict[str, Any]]:
    masked: list[dict[str, Any]] = []
    for item in failures:
        output = str(item.get("output", "")).lower()
        if any(marker in output for marker in MASKING_MARKERS):
            masked.append(
                {
                    "path": item.get("path"),
                    "classification": "contract masking introduced",
                    "reason": "schema/contract failure signature detected before targeted test assertions",
                }
            )
    return masked


def render_markdown(report: dict[str, Any]) -> str:
    lines = ["# Contract Preflight Report", ""]
    lines.append(f"- **status**: `{report['status']}`")
    lines.append(f"- **changed_contracts**: {len(report['changed_contracts'])}")
    lines.append(f"- **changed_examples**: {len(report['changed_examples'])}")
    lines.append("")

    lines.append("## Impacted seams")
    impact = report["impact"]
    for key in ("producers", "fixtures_or_builders", "consumers", "required_smoke_tests"):
        values = impact.get(key, [])
        lines.append(f"- **{key}** ({len(values)}):")
        for value in values:
            lines.append(f"  - `{value}`")
        if not values:
            lines.append("  - _none_")

    lines.append("")
    lines.append("## Preflight failures")
    for key in ("schema_example_failures", "producer_failures", "fixture_failures", "consumer_failures"):
        values = report.get(key, [])
        lines.append(f"- **{key}**: {len(values)}")

    lines.append("")
    if report.get("masked_failures"):
        lines.append("## Masked downstream failures")
        for item in report["masked_failures"]:
            lines.append(f"- `{item['path']}` — **contract masking introduced**")
    else:
        lines.append("## Masked downstream failures")
        lines.append("- none")

    lines.append("")
    lines.append("## Recommended repair areas")
    for area in report.get("recommended_repair_areas", []):
        lines.append(f"- {area}")
    if not report.get("recommended_repair_areas"):
        lines.append("- none")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    args = _parse_args()
    output_dir = REPO_ROOT / args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    changed_paths = detect_changed_paths(REPO_ROOT, args.base_ref, args.head_ref, args.changed_path)
    classified = classify_changed_contracts(changed_paths)

    changed_contracts = classified["changed_contract_paths"] + classified["changed_governed_definitions"]
    changed_examples = classified["changed_example_paths"]

    if not changed_contracts and not changed_examples:
        report = {
            "status": "skipped",
            "changed_contracts": [],
            "changed_examples": [],
            "impact": {
                "producers": [],
                "fixtures_or_builders": [],
                "consumers": [],
                "required_smoke_tests": [],
            },
            "schema_example_failures": [],
            "producer_failures": [],
            "fixture_failures": [],
            "consumer_failures": [],
            "masked_failures": [],
            "recommended_repair_areas": [],
        }
    else:
        impact = build_impact_map(REPO_ROOT, changed_contracts, changed_examples)

        schema_example_failures = validate_examples(changed_examples)

        producer_targets = resolve_test_targets(REPO_ROOT, impact["producers"] + impact["consumers"])
        fixture_targets = resolve_test_targets(REPO_ROOT, impact["fixtures_or_builders"])
        smoke_targets = sorted(set(impact["required_smoke_tests"]))

        producer_failures = run_targeted_pytests(producer_targets) if producer_targets else []
        fixture_failures = run_targeted_pytests(fixture_targets) if fixture_targets else []
        consumer_failures = run_targeted_pytests(smoke_targets) if smoke_targets else []

        masked_failures = detect_masked_failures(producer_failures + fixture_failures + consumer_failures)

        recommended_areas = []
        if schema_example_failures:
            recommended_areas.append("contracts/examples")
        if producer_failures:
            recommended_areas.append("spectrum_systems/orchestration and runtime producers")
        if fixture_failures:
            recommended_areas.append("tests/fixtures and tests/helpers builders")
        if consumer_failures:
            recommended_areas.append("targeted downstream consumer tests")

        report = {
            "status": "failed" if (schema_example_failures or producer_failures or fixture_failures or consumer_failures) else "passed",
            "changed_contracts": changed_contracts,
            "changed_examples": changed_examples,
            "impact": {
                "producers": impact["producers"],
                "fixtures_or_builders": impact["fixtures_or_builders"],
                "consumers": impact["consumers"],
                "required_smoke_tests": impact["required_smoke_tests"],
            },
            "contract_impact_artifact": impact["contract_impact_artifact"],
            "schema_example_failures": schema_example_failures,
            "producer_failures": producer_failures,
            "fixture_failures": fixture_failures,
            "consumer_failures": consumer_failures,
            "masked_failures": masked_failures,
            "recommended_repair_areas": sorted(set(recommended_areas)),
        }

    json_path = output_dir / "contract_preflight_report.json"
    md_path = output_dir / "contract_preflight_report.md"
    json_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")

    print(json.dumps({"status": report["status"], "json_report": str(json_path), "markdown_report": str(md_path)}, indent=2))

    return 2 if report["status"] == "failed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
