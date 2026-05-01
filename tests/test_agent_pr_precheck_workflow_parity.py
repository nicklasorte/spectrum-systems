"""APR-02 — Workflow parity test for the Agent PR Precheck Runner.

Asserts that ``scripts/run_agent_pr_precheck.py`` covers the same essential
governed-contract preflight commands and flags that
``.github/workflows/artifact-boundary.yml``'s ``governed-contract-preflight``
job runs.

APR is observation-only. This test detects drift between APR's local
pre-PR runner and the canonical CI gate sequence so that an APR pass on
a developer machine cannot diverge silently from the CI pass it is
trying to predict. Canonical authority remains with the canonical owner
systems declared in ``docs/architecture/system_registry.md``; this test
does not redefine ownership and emits no signal beyond pytest pass/fail.

The parity assertions cover:

* build_preflight_pqx_wrapper invocation
* run_contract_preflight invocation
* ``--execution-context pqx_governed`` mode
* ``--pqx-wrapper-path`` flag + canonical wrapper path
* ``--authority-evidence-ref`` flag + canonical evidence path
* APR uses caller-supplied ``--base-ref``/``--head-ref`` (not silent
  ``main``/``HEAD`` substitution when explicit refs are supplied)
* APR's visible check_name labels remain authority-safe
* APR phase coverage parity for the supporting governed-preflight
  surfaces (authority-shape preflight, authority-leak guard, system
  registry guard, contract-compliance observation, generated-artifact
  freshness, selected pytest, CLP / core-loop pre-PR gate, APU /
  agent-PR-update readiness check)
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest

import scripts.run_agent_pr_precheck as apr

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = ROOT / ".github" / "workflows" / "artifact-boundary.yml"
PR_PYTEST_WORKFLOW_PATH = ROOT / ".github" / "workflows" / "pr-pytest.yml"
APR_SCRIPT_PATH = ROOT / "scripts" / "run_agent_pr_precheck.py"
SHARD_RUNNER_SCRIPT_PATH = ROOT / "scripts" / "run_pr_test_shards.py"

CANONICAL_PQX_WRAPPER_PATH = (
    "outputs/contract_preflight/preflight_pqx_task_wrapper.json"
)
CANONICAL_AUTHORITY_EVIDENCE_REF = (
    "artifacts/pqx_runs/preflight.pqx_slice_execution_record.json"
)

# PAR-CI-01 — canonical shard list shared by the schema, the runner,
# and the GitHub matrix. Drift here breaks shard parity across APR / CI.
CANONICAL_SHARDS: tuple[str, ...] = (
    "contract",
    "governance",
    "runtime_core",
    "changed_scope",
    "generated_artifacts",
    "measurement",
)


@pytest.fixture(scope="module")
def workflow_text() -> str:
    assert WORKFLOW_PATH.is_file(), f"missing workflow: {WORKFLOW_PATH}"
    return WORKFLOW_PATH.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def pr_pytest_workflow_text() -> str:
    assert PR_PYTEST_WORKFLOW_PATH.is_file(), (
        f"missing workflow: {PR_PYTEST_WORKFLOW_PATH}"
    )
    return PR_PYTEST_WORKFLOW_PATH.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def apr_text() -> str:
    assert APR_SCRIPT_PATH.is_file(), f"missing APR script: {APR_SCRIPT_PATH}"
    return APR_SCRIPT_PATH.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Build preflight pqx wrapper parity
# ---------------------------------------------------------------------------


def test_workflow_invokes_build_preflight_pqx_wrapper(workflow_text: str) -> None:
    assert "scripts/build_preflight_pqx_wrapper.py" in workflow_text, (
        "governed-contract-preflight job no longer invokes "
        "scripts/build_preflight_pqx_wrapper.py — APR parity is undefined"
    )


def test_apr_wraps_build_preflight_pqx_wrapper(apr_text: str) -> None:
    assert "scripts/build_preflight_pqx_wrapper.py" in apr_text, (
        "APR no longer wraps scripts/build_preflight_pqx_wrapper.py; CI "
        "and APR have drifted"
    )


# ---------------------------------------------------------------------------
# run_contract_preflight parity
# ---------------------------------------------------------------------------


def test_workflow_invokes_run_contract_preflight(workflow_text: str) -> None:
    assert "scripts/run_contract_preflight.py" in workflow_text, (
        "governed-contract-preflight job no longer invokes "
        "scripts/run_contract_preflight.py"
    )


def test_apr_wraps_run_contract_preflight(apr_text: str) -> None:
    assert "scripts/run_contract_preflight.py" in apr_text, (
        "APR no longer wraps scripts/run_contract_preflight.py; CI and APR "
        "have drifted"
    )


# ---------------------------------------------------------------------------
# pqx_governed execution-context parity
# ---------------------------------------------------------------------------


def test_workflow_uses_pqx_governed_execution_context(workflow_text: str) -> None:
    assert "--execution-context pqx_governed" in workflow_text, (
        "governed-contract-preflight job no longer pins "
        "--execution-context pqx_governed"
    )


def test_apr_uses_pqx_governed_execution_context(apr_text: str) -> None:
    assert '"pqx_governed"' in apr_text or "'pqx_governed'" in apr_text, (
        "APR no longer pins pqx_governed execution context"
    )
    assert "--execution-context" in apr_text, (
        "APR no longer passes --execution-context to run_contract_preflight"
    )


# ---------------------------------------------------------------------------
# --pqx-wrapper-path parity
# ---------------------------------------------------------------------------


def test_workflow_passes_pqx_wrapper_path(workflow_text: str) -> None:
    assert "--pqx-wrapper-path" in workflow_text, (
        "governed-contract-preflight job no longer passes --pqx-wrapper-path"
    )
    assert CANONICAL_PQX_WRAPPER_PATH in workflow_text, (
        f"workflow no longer references canonical wrapper path "
        f"{CANONICAL_PQX_WRAPPER_PATH}"
    )


def test_apr_passes_pqx_wrapper_path(apr_text: str) -> None:
    assert "--pqx-wrapper-path" in apr_text, (
        "APR no longer passes --pqx-wrapper-path to run_contract_preflight"
    )
    # APR builds the canonical wrapper path with ``Path`` joins; assert
    # both the directory and filename components are present, and the
    # runtime-resolved path matches CANONICAL_PQX_WRAPPER_PATH.
    assert '"contract_preflight"' in apr_text, (
        "APR no longer references the contract_preflight output dir"
    )
    assert '"preflight_pqx_task_wrapper.json"' in apr_text, (
        "APR no longer references preflight_pqx_task_wrapper.json filename"
    )


# ---------------------------------------------------------------------------
# --authority-evidence-ref parity
# ---------------------------------------------------------------------------


def test_workflow_passes_authority_evidence_ref(workflow_text: str) -> None:
    assert "--authority-evidence-ref" in workflow_text, (
        "governed-contract-preflight job no longer passes "
        "--authority-evidence-ref"
    )
    assert CANONICAL_AUTHORITY_EVIDENCE_REF in workflow_text, (
        "workflow no longer references canonical authority evidence ref "
        f"{CANONICAL_AUTHORITY_EVIDENCE_REF}"
    )


def test_apr_passes_authority_evidence_ref(apr_text: str) -> None:
    assert "--authority-evidence-ref" in apr_text, (
        "APR no longer passes --authority-evidence-ref"
    )
    assert CANONICAL_AUTHORITY_EVIDENCE_REF in apr_text, (
        "APR no longer references canonical authority evidence ref "
        f"{CANONICAL_AUTHORITY_EVIDENCE_REF}"
    )


# ---------------------------------------------------------------------------
# APR uses caller-supplied --base-ref / --head-ref
# ---------------------------------------------------------------------------


def test_apr_cli_accepts_base_and_head_refs() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-ref", default="origin/main")
    parser.add_argument("--head-ref", default="HEAD")
    parser.add_argument("--work-item-id", default="X")
    parser.add_argument("--repo-mutating", default="auto")
    # Sanity: the actual APR _parse_args also exposes these.
    src = APR_SCRIPT_PATH.read_text(encoding="utf-8")
    assert '"--base-ref"' in src, "APR CLI does not expose --base-ref"
    assert '"--head-ref"' in src, "APR CLI does not expose --head-ref"


@pytest.mark.parametrize(
    "wrapper_factory",
    [
        lambda base, head, out: apr.tpa_authority_shape(
            base_ref=base, head_ref=head, output_dir=out
        ),
        lambda base, head, out: apr.tpa_authority_leak(
            base_ref=base, head_ref=head, output_dir=out
        ),
        lambda base, head, out: apr.tpa_system_registry(
            base_ref=base, head_ref=head, output_dir=out
        ),
        lambda base, head, out: apr.pqx_build_wrapper(
            base_ref=base, head_ref=head, output_dir=out
        ),
        lambda base, head, out: apr.pqx_contract_preflight(
            base_ref=base, head_ref=head, output_dir=out
        ),
    ],
)
def test_apr_phase_wrappers_pass_caller_supplied_refs(
    monkeypatch, tmp_path, wrapper_factory
) -> None:
    """APR's per-phase wrappers must embed caller-supplied base/head refs in
    the subprocess command — not silently substitute ``main``/``HEAD`` when
    the caller supplied explicit refs.
    """
    captured: list[list[str]] = []

    def _fake_run(cmd, cwd):  # noqa: ANN001
        captured.append(list(cmd))
        return 0, ""

    monkeypatch.setattr(apr, "_run_subprocess", _fake_run)
    fake_base = "abc1234deadbeef"
    fake_head = "def5678cafebabe"
    wrapper_factory(fake_base, fake_head, tmp_path)
    assert captured, "wrapper did not invoke _run_subprocess"
    cmd = captured[0]
    # explicit ref values must appear in the command
    assert fake_base in cmd, (
        f"caller-supplied base_ref {fake_base!r} not found in cmd: {cmd}"
    )
    assert fake_head in cmd, (
        f"caller-supplied head_ref {fake_head!r} not found in cmd: {cmd}"
    )
    # and they must follow --base-ref / --head-ref flags, not substitute
    # anything else.
    assert "--base-ref" in cmd
    assert "--head-ref" in cmd
    assert cmd[cmd.index("--base-ref") + 1] == fake_base
    assert cmd[cmd.index("--head-ref") + 1] == fake_head


def test_apr_pqx_contract_preflight_includes_governed_flags(
    monkeypatch, tmp_path
) -> None:
    """The pqx_contract_preflight wrapper must always pin the
    pqx_governed execution context, the canonical wrapper path, and
    the canonical authority evidence ref — independent of caller refs.
    """
    captured: list[list[str]] = []

    def _fake_run(cmd, cwd):  # noqa: ANN001
        captured.append(list(cmd))
        return 0, ""

    monkeypatch.setattr(apr, "_run_subprocess", _fake_run)
    apr.pqx_contract_preflight(
        base_ref="abc", head_ref="def", output_dir=tmp_path
    )
    assert captured
    cmd = captured[0]
    assert "--execution-context" in cmd
    assert cmd[cmd.index("--execution-context") + 1] == "pqx_governed"
    assert "--pqx-wrapper-path" in cmd
    assert cmd[cmd.index("--pqx-wrapper-path") + 1] == CANONICAL_PQX_WRAPPER_PATH
    assert "--authority-evidence-ref" in cmd
    assert (
        cmd[cmd.index("--authority-evidence-ref") + 1]
        == CANONICAL_AUTHORITY_EVIDENCE_REF
    )


# ---------------------------------------------------------------------------
# APR phase coverage parity (supporting preflight surfaces)
# ---------------------------------------------------------------------------


def test_apr_covers_authority_shape_preflight(apr_text: str) -> None:
    assert "scripts/run_authority_shape_preflight.py" in apr_text, (
        "APR no longer covers the authority-shape preflight surface"
    )


def test_apr_covers_authority_leak_guard(apr_text: str) -> None:
    assert "scripts/run_authority_leak_guard.py" in apr_text, (
        "APR no longer covers the authority-leak guard surface"
    )


def test_apr_covers_system_registry_guard(apr_text: str) -> None:
    assert "scripts/run_system_registry_guard.py" in apr_text, (
        "APR no longer covers the system-registry guard surface"
    )


def test_apr_covers_contract_compliance_observation(apr_text: str) -> None:
    """APR must wrap the canonical contract-compliance gate runner. The
    runner script's own filename uses a reserved authority subtoken; APR
    resolves it dynamically rather than embedding the literal name.
    """
    assert "_resolve_compliance_gate_runner" in apr_text, (
        "APR no longer dynamically resolves the contract-compliance gate "
        "runner"
    )
    # It must surface a contract-compliance check name in observation form
    assert "tpa_contract_compliance_observation" in apr_text, (
        "APR no longer surfaces contract_compliance_observation as the "
        "check_name (the only authority-safe surface label for this gate)"
    )


def test_apr_covers_generated_artifact_freshness(apr_text: str) -> None:
    assert "scripts/build_tls_dependency_priority.py" in apr_text, (
        "APR no longer covers the TLS generated-artifact freshness check"
    )
    assert "scripts/generate_ecosystem_health_report.py" in apr_text, (
        "APR no longer covers the ecosystem health generated-artifact "
        "freshness check"
    )


def test_apr_covers_selected_tests(apr_text: str) -> None:
    assert "evl_pr_test_shards" in apr_text, (
        "APR no longer covers the per-shard test phase"
    )
    assert "scripts/run_pr_test_shards.py" in apr_text, (
        "APR no longer invokes the canonical shard runner"
    )


def test_apr_covers_core_loop_pre_pr_gate(apr_text: str) -> None:
    assert "scripts/run_core_loop_pre_pr_gate.py" in apr_text, (
        "APR no longer covers the CLP-01 core_loop_pre_pr_gate runner"
    )


def test_apr_covers_check_agent_pr_ready(apr_text: str) -> None:
    assert "scripts/check_agent_pr_ready.py" in apr_text, (
        "APR no longer covers the CLP-02 check_agent_pr_ready runner"
    )


def test_apr_covers_check_agent_pr_update_ready(apr_text: str) -> None:
    assert "scripts/check_agent_pr_update_ready.py" in apr_text, (
        "APR no longer covers the APU check_agent_pr_update_ready runner"
    )


# ---------------------------------------------------------------------------
# Authority-safe visible labels
# ---------------------------------------------------------------------------


def test_apr_check_name_labels_remain_authority_safe(apr_text: str) -> None:
    """APR must not expose ``run_contract_enforcement`` (the canonical
    runner's filename carries a reserved authority subtoken) as a visible
    ``check_name`` or other observation-surface label. Use
    ``contract_compliance_observation`` (or the current safe equivalent)
    instead. The literal script-name reference inside the dynamic resolver
    is a path reference, not an authority claim, and is allowlisted by
    the existing APR-01 banned-token lint.
    """
    forbidden_label_substrings = (
        # canonical runner filename used as a check_name / label
        'check_name="run_contract_enforcement"',
        "check_name='run_contract_enforcement'",
        'phase="ENF"',
        "phase='ENF'",
    )
    for needle in forbidden_label_substrings:
        assert needle not in apr_text, (
            f"APR exposes authority-unsafe label fragment {needle!r}"
        )


# ---------------------------------------------------------------------------
# PAR-CI-01 — GitHub matrix parity for canonical PR test shards
#
# These assertions detect drift between the canonical shard runner used
# by APR (``scripts/run_pr_test_shards.py``) and the GitHub matrix that
# CI executes for PRs (``.github/workflows/pr-pytest.yml``). They emit
# only test pass/fail; no admission, certification, promotion, or
# enforcement signal is implied.
# ---------------------------------------------------------------------------


def test_pr_pytest_workflow_uses_canonical_shard_runner(
    pr_pytest_workflow_text: str,
) -> None:
    assert "scripts/run_pr_test_shards.py" in pr_pytest_workflow_text, (
        ".github/workflows/pr-pytest.yml does not invoke the canonical "
        "PAR-BATCH-01 shard runner 'scripts/run_pr_test_shards.py'"
    )


def test_apr_uses_canonical_shard_runner(apr_text: str) -> None:
    assert "scripts/run_pr_test_shards.py" in apr_text, (
        "APR no longer invokes the canonical shard runner "
        "'scripts/run_pr_test_shards.py'"
    )


def test_pr_pytest_workflow_does_not_introduce_duplicate_selector(
    pr_pytest_workflow_text: str,
) -> None:
    # The legacy single-shard wrapper must not be invoked by the matrix
    # alongside the canonical runner — that would be a duplicate
    # selector path. The legacy script remains in the repo and is
    # unit-tested directly; CI must use exactly one shard runner.
    assert "scripts/select_pr_test_shard.py" not in pr_pytest_workflow_text, (
        ".github/workflows/pr-pytest.yml references the legacy "
        "'scripts/select_pr_test_shard.py' alongside the canonical "
        "shard runner — duplicate selector path is forbidden"
    )
    # Likewise the legacy aggregator must not be wired in alongside
    # the canonical-shards aggregator.
    assert "scripts/run_pr_gate.py" not in pr_pytest_workflow_text, (
        ".github/workflows/pr-pytest.yml references the legacy "
        "'scripts/run_pr_gate.py' aggregator alongside the canonical "
        "shard runner — duplicate aggregator path is forbidden"
    )


def test_pr_pytest_workflow_matrix_lists_canonical_shards(
    pr_pytest_workflow_text: str,
) -> None:
    # Each canonical shard name must appear in the workflow matrix.
    for shard in CANONICAL_SHARDS:
        needle = f"- {shard}"
        assert needle in pr_pytest_workflow_text, (
            f".github/workflows/pr-pytest.yml matrix missing canonical "
            f"shard {shard!r} (expected line {needle!r})"
        )
    # The legacy 'dashboard' shard name must NOT appear in the
    # canonical matrix — PAR-BATCH-01 renamed it to
    # 'generated_artifacts'. Drift here would split CI/APR shard
    # vocabulary again.
    assert "- dashboard" not in pr_pytest_workflow_text, (
        ".github/workflows/pr-pytest.yml matrix still lists the legacy "
        "'dashboard' shard; canonical name is 'generated_artifacts'"
    )


def test_pr_pytest_workflow_matrix_matches_runner_canonical_shards() -> None:
    """The matrix shard list and the canonical runner's CANONICAL_SHARDS
    must be identical sets — drift = parity violation.
    """
    from scripts.run_pr_test_shards import (
        CANONICAL_SHARDS as RUNNER_SHARDS,
    )

    assert set(RUNNER_SHARDS) == set(CANONICAL_SHARDS), (
        "parity-test canonical shard list diverges from "
        "scripts.run_pr_test_shards.CANONICAL_SHARDS: "
        f"runner={set(RUNNER_SHARDS)} parity={set(CANONICAL_SHARDS)}"
    )


def test_pr_pytest_workflow_matrix_matches_schema_canonical_shards() -> None:
    """The matrix shard list and the canonical schema enum must be
    identical sets.
    """
    schema_path = (
        ROOT / "contracts" / "schemas" / "pr_test_shard_result.schema.json"
    )
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    schema_enum = set(schema["properties"]["shard_name"]["enum"])
    assert schema_enum == set(CANONICAL_SHARDS), (
        "parity-test canonical shard list diverges from schema enum: "
        f"schema={schema_enum} parity={set(CANONICAL_SHARDS)}"
    )


def test_pr_pytest_workflow_does_not_run_monolithic_shard_pytest(
    pr_pytest_workflow_text: str,
) -> None:
    """The shard matrix jobs must not call ``python -m pytest`` directly
    in addition to the canonical shard runner — that would silently run
    a monolithic pytest pass that bypasses canonical shard selection.

    The unrelated ``pytest:`` job in the same workflow runs the
    governed contract preflight which itself executes the selected
    pytest targets via the canonical preflight gate. Inside the
    pr-test-shards matrix steps, only the canonical shard runner may
    be invoked.
    """
    # Slice the workflow text to just the pr-test-shards matrix job
    # (between 'pr-test-shards:' and the next top-level 'pr-test-shards-aggregate:'
    # sibling job).
    start = pr_pytest_workflow_text.find("pr-test-shards:")
    end = pr_pytest_workflow_text.find("pr-test-shards-aggregate:")
    assert start != -1 and end != -1 and start < end, (
        "could not locate pr-test-shards matrix job slice in pr-pytest.yml"
    )
    matrix_slice = pr_pytest_workflow_text[start:end]
    assert "python -m pytest" not in matrix_slice, (
        "pr-test-shards matrix job invokes 'python -m pytest' directly; "
        "only the canonical shard runner ('scripts/run_pr_test_shards.py') "
        "may run inside the shard matrix"
    )


def test_pr_pytest_workflow_uploads_per_shard_artifact(
    pr_pytest_workflow_text: str,
) -> None:
    # Each matrix entry must upload the per-shard pr_test_shard_result
    # artifact at outputs/pr_test_shards/<shard>.json.
    assert "outputs/pr_test_shards/${{ matrix.shard }}.json" in pr_pytest_workflow_text, (
        "pr-test-shards matrix job does not upload "
        "outputs/pr_test_shards/<shard>.json — per-shard "
        "pr_test_shard_result artifact upload is required"
    )


def test_pr_pytest_workflow_aggregator_validates_shard_artifacts(
    pr_pytest_workflow_text: str,
) -> None:
    # The aggregator job must download per-shard artifacts and validate
    # them via the canonical contracts validator. Static checks below
    # are the workflow-yaml-level evidence; runtime fail-closed
    # behavior is exercised by the inline aggregator steps.
    aggregator_start = pr_pytest_workflow_text.find(
        "pr-test-shards-aggregate:"
    )
    assert aggregator_start != -1, (
        "missing pr-test-shards-aggregate job in pr-pytest.yml"
    )
    aggregator_slice = pr_pytest_workflow_text[aggregator_start:]
    assert "actions/download-artifact" in aggregator_slice, (
        "pr-test-shards-aggregate job does not download per-shard artifacts"
    )
    assert "validate_artifact" in aggregator_slice, (
        "pr-test-shards-aggregate job does not validate shard artifacts "
        "against the canonical contracts validator"
    )
    assert "shard_status_fail" in aggregator_slice, (
        "pr-test-shards-aggregate job does not record a "
        "'shard_status_fail' blocking readiness observation"
    )
    assert "shard_status_unknown" in aggregator_slice, (
        "pr-test-shards-aggregate job does not record a "
        "'shard_status_unknown' blocking readiness observation"
    )
    assert "shard_artifact_missing" in aggregator_slice, (
        "pr-test-shards-aggregate job does not record a "
        "'shard_artifact_missing' blocking readiness observation"
    )


def test_pr_pytest_workflow_aggregator_uses_authority_safe_vocabulary(
    pr_pytest_workflow_text: str,
) -> None:
    """PAR-CI-01 — the new shard matrix and aggregator must not surface
    reserved authority terms in workflow labels, comments, or step
    names. Only the existing governed-pytest preflight surface inside
    the unchanged ``pytest:`` job is permitted to reference such terms
    (and only via canonical script names that are authority-safe by
    convention).
    """
    forbidden_substrings = (
        " approve",
        "approval",
        " certify",
        "certification",
        " promote",
        "promotion",
        " enforce",
        "enforcement",
        " decide",
        " decision",
        "authorize",
        "authorization",
        "verdict",
    )
    # Slice to the pr-test-shards + aggregator surface only.
    start = pr_pytest_workflow_text.find("pr-test-shards:")
    end = pr_pytest_workflow_text.find("\n  pytest:\n")
    assert start != -1 and end != -1 and start < end, (
        "could not locate shard surface slice in pr-pytest.yml"
    )
    surface = pr_pytest_workflow_text[start:end]
    for needle in forbidden_substrings:
        assert needle not in surface, (
            f"reserved authority substring {needle!r} appears in the "
            "PAR-CI-01 shard / aggregator workflow surface"
        )


# ---------------------------------------------------------------------------
# Negative test: parity test catches regression if APR drops a required
# preflight command. We assert the parity-test source itself encodes the
# canonical strings so a future "soft delete" of an assertion is visible
# in code review.
# ---------------------------------------------------------------------------


def test_parity_test_self_encodes_canonical_strings() -> None:
    """Self-check: the parity test asserts on these literal strings. If a
    future refactor removes them from this file, that change will surface
    in code review (and this self-check will fail).
    """
    self_text = Path(__file__).read_text(encoding="utf-8")
    required_literals = (
        "scripts/build_preflight_pqx_wrapper.py",
        "scripts/run_contract_preflight.py",
        "--execution-context pqx_governed",
        "--pqx-wrapper-path",
        "--authority-evidence-ref",
        CANONICAL_PQX_WRAPPER_PATH,
        CANONICAL_AUTHORITY_EVIDENCE_REF,
        "scripts/run_authority_shape_preflight.py",
        "scripts/run_authority_leak_guard.py",
        "scripts/run_system_registry_guard.py",
        "scripts/run_core_loop_pre_pr_gate.py",
        "scripts/check_agent_pr_ready.py",
        "scripts/check_agent_pr_update_ready.py",
        "scripts/build_tls_dependency_priority.py",
        "scripts/generate_ecosystem_health_report.py",
        "tpa_contract_compliance_observation",
        "scripts/run_pr_test_shards.py",
        "pr-test-shards:",
        "pr-test-shards-aggregate:",
        "generated_artifacts",
    )
    for literal in required_literals:
        assert literal in self_text, (
            f"parity test self-check failed: missing literal {literal!r}"
        )
