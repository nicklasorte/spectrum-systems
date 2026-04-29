# PAR-00-01 Red-Team Review: Parallel PR Test Shards

**Batch**: PAR-00-01
**Reviewed**: 2026-04-29
**Reviewer**: Architecture Red-Team

## Summary

This review evaluates the PAR-00-01 parallel PR shard system for failure modes,
authority-shape violations, and governance gaps. The system distributes PR test
execution across parallel shards and aggregates results via a gate script. The
primary risk surface is the aggregator: it consumes shard artifacts and produces
a final gate decision, creating multiple bypass and injection vectors if artifact
validation is insufficient.

Fourteen findings are raised. Eight are must_fix (RT-01 through RT-08), three are
should_fix (RT-09 through RT-11), and three are observations (RT-12 through RT-14).
All must_fix items have corresponding fixes applied in this PR.

---

## Findings

### must_fix

#### RT-01: Missing shard artifact treated as pass

**Attack/failure mode**: A shard job fails to write its output artifact (crash,
OOM, network failure, or deliberate omission). The aggregator attempts to load the
artifact, finds it absent, and — without an explicit existence check — either
silently skips the shard or defaults to a passing state. The final gate passes
despite a shard never executing or reporting.

**Impact**: Complete bypass of a shard's test coverage. A governed surface with
zero test execution passes the PR gate. Silent failure; no observable signal in
the gate output.

**Fix**: The aggregator (`scripts/run_pr_gate.py`) checks file existence for every
required shard artifact before attempting to load it. A missing artifact is treated
as an immediate block with a structured finding. No shard may be implicitly skipped.

---

#### RT-02: Invalid shard JSON treated as pass

**Attack/failure mode**: A shard artifact exists on disk but contains malformed
JSON (truncated write, encoding error, or injected content). The aggregator
attempts to parse it, catches the exception silently or skips validation, and
proceeds as if the shard passed.

**Impact**: Corrupted or adversarially crafted shard artifacts bypass the gate.
Schema constraints are never evaluated. Any downstream consumer reading the
artifact receives invalid data.

**Fix**: The aggregator performs explicit JSON parsing inside a try/except block
before schema validation. A JSON parse error is treated as a block, not a skip.
The block finding includes the artifact path and exception message.

---

#### RT-03: Governed surface selects zero tests

**Attack/failure mode**: A change touches a governed surface (e.g., a workflow
file, a schema, or a script). The selector is invoked but returns an empty
`selected_tests` list — due to a missing mapping, a pattern mismatch, or a
selector bug. The shard proceeds with zero tests and reports a passing result.

**Impact**: A governed surface receives no test coverage but the gate passes.
The `pytest_selection_missing` failure class is not caught. Downstream systems
receive a passing shard result that represents zero validation.

**Fix**: `spectrum_systems/modules/runtime/pr_test_selection.py` enforces a
fail-closed rule in `build_selection_artifact`: if `governed_surfaces` is
non-empty and `selected_tests` is empty, the function raises and the selection
artifact is not produced. The caller blocks.

---

#### RT-04: New test file lacks shard mapping

**Attack/failure mode**: A contributor adds a new test file. No shard mapping
entry is created for it. The drift detector does not catch the gap. The test
file exists in the repo but is never selected by any shard, silently excluded
from all PR runs.

**Impact**: Test coverage drifts from the declared mapping. New tests are never
executed. Coverage reports are inaccurate. The gap persists across all subsequent
PRs until manually discovered.

**Fix**: `scripts/run_ci_drift_detector.py` is updated to enumerate all test
files matching the repo test pattern and cross-check against the shard mapping.
Any test file without a shard mapping entry produces a drift finding and blocks
the detector run.

---

#### RT-05: Governance shard skipped for docs/governance changes

**Attack/failure mode**: A PR modifies files under `docs/governance/`. The shard
routing logic does not trigger the governance shard because the routing condition
checks only code paths (e.g., `spectrum_systems/`, `scripts/`), missing the
`docs/governance/` prefix. The governance shard is never enqueued and never
reports. The aggregator, lacking the shard result, either skips it (RT-01 vector)
or passes without it.

**Impact**: Governance document changes ship without governance shard coverage.
Authority mappings, policy documents, and ownership declarations are modified
without any gated test signal.

**Fix**: `spectrum_systems/modules/runtime/pr_test_selection.py` shard routing
explicitly includes `docs/governance/` as a trigger condition for the governance
shard. The routing table is exhaustive; any change to `docs/governance/` enqueues
the governance shard unconditionally.

---

#### RT-06: Authority-shape bypass via shard result

**Attack/failure mode**: A shard result artifact omits the `authority_scope` field
or sets it to a value other than `"observation_only"`. The aggregator consumes the
artifact without validating the field. The shard result is treated as authoritative
evidence rather than observation evidence, potentially allowing downstream consumers
to treat it as a control input.

**Impact**: Shard artifacts acquire implicit authority beyond their declared scope.
The boundary between observation evidence and control inputs is violated. Downstream
systems (CDE, SEL, TPA) may misclassify the artifact's authority.

**Fix**: `contracts/schemas/pr_test_shard_result.schema.json` declares
`authority_scope` as a required field with `"const": "observation_only"`. Any
shard artifact missing the field or carrying a different value fails schema
validation and is rejected by the aggregator.

---

#### RT-07: Shard claims approval/certification/enforcement authority

**Attack/failure mode**: A shard result artifact includes fields named
`approved`, `certified`, `enforce`, `allow`, or similar terms that imply
the shard is making a control or enforcement decision. The aggregator or a
downstream consumer reads these fields and treats them as authoritative signals,
bypassing CDE, SEL, or certification systems.

**Impact**: Shards usurp canonical authority. The control loop (CDE), enforcement
(SEL), and certification systems are bypassed. The governed runtime's authority
structure is undermined by shard-level claims.

**Fix**: `contracts/schemas/pr_test_shard_result.schema.json` uses
`"additionalProperties": false` and does not include any approve, certify,
promote, or enforce fields. Schema validation rejects any shard artifact that
carries such fields. Combined with the RT-06 fix, the schema enforces
`authority_scope = "observation_only"` and prohibits authority-claiming fields.

---

#### RT-08: Aggregator reimplements selection logic

**Attack/failure mode**: The aggregator (`scripts/run_pr_gate.py`) contains inline
logic that recomputes which tests should have run for a given shard, rather than
consuming the pre-computed selection artifact produced by the canonical selector.
This creates a second, divergent implementation of selection logic that can produce
different results from the canonical selector, opening a gap between what was
selected and what the aggregator believes was selected.

**Impact**: Two implementations of selection logic diverge silently. The aggregator
may declare coverage for tests that the selector never selected, or miss coverage
for tests the selector did select. The canonical selector's authority is shadowed
by the aggregator's inline logic.

**Fix**: The aggregator reads the pre-computed `selection_artifact` emitted by
`spectrum_systems/modules/runtime/pr_test_selection.py`. It does not call selector
functions or recompute selections inline. All selection logic lives in the canonical
module; the aggregator is a consumer only.

---

### should_fix

#### RT-09: Dashboard shard passes while governance shard fails and final gate allows

**Attack/failure mode**: The aggregator uses OR logic or a weighted threshold
rather than strict AND logic across required shards. The governance shard fails,
but the dashboard shard and runtime shard pass. The aggregator's threshold is
met, and the final gate emits allow. The governance shard failure is logged but
does not block.

**Impact**: A failing governance shard does not block promotion. Changes to
governed surfaces ship without passing governance coverage. The AND requirement
across required shards is effectively optional.

**Fix**: The aggregator uses AND logic across all required shards. Every required
shard must pass; a single required shard failure produces a block regardless of
other shard results. The aggregation algorithm is explicit in the code and tested.

---

#### RT-10: CI mode and precheck mode diverge silently

**Attack/failure mode**: The shard system operates in two modes: full CI mode
(all shards run) and precheck mode (subset of shards run based on changed paths).
The two modes use different shard lists and different pass thresholds. Over time,
the two modes drift: a fix applied in CI mode is not applied in precheck mode, or
the shard list in one mode grows while the other does not. The divergence is not
detected until a precheck mode run passes something that CI mode would fail.

**Impact**: Precheck mode becomes a weaker gate than CI mode. Contributors learn
to rely on precheck results that do not represent full CI coverage. PRs are merged
based on precheck signals that would fail under CI.

**Fix**: A parity artifact is produced on each run declaring the active mode and
the shard list used. The aggregator checks parity: if the shard lists for CI and
precheck mode have diverged beyond the expected subset relationship, the run
blocks with a parity finding. The parity check is explicitly tested.

---

#### RT-11: runtime_core/measurement deferred but deep validation silently removed

**Attack/failure mode**: The nightly deep validation workflow that runs full
`runtime_core` and measurement layer tests is removed or weakened as part of
the PR shard refactor. The rationale is that shards cover these tests during
PR runs. However, the nightly workflow covered additional integration paths,
long-running tests, and cross-system scenarios that are excluded from PR shards
for latency reasons. The removal is not announced and no equivalent coverage is
added.

**Impact**: Integration and long-running tests stop running. Regressions in
`runtime_core` and the measurement layer are not caught until they surface in
production or through manual investigation. The coverage gap is invisible because
no artifact records the removed workflow.

**Fix**: The nightly deep validation workflow is preserved as a separate workflow
file. It is not replaced by PR shards. Its continued existence and last-run status
are tracked in the observability layer.

---

### observation

#### RT-12: Matrix cancellation hides failure

**Description**: GitHub Actions matrix cancellation (`cancel-in-progress: true`
or `fail-fast: true`) can terminate passing shards when one shard fails. The
cancelled shards never produce output artifacts. The aggregator sees missing
artifacts for the cancelled shards (RT-01 vector) but the root failure is in a
different shard. The cancellation hides the actual failing shard by making multiple
shards appear to have not run.

**Impact**: Debugging is harder. The failure signal is diluted across multiple
missing artifacts rather than pointing to the one failing shard. Not a security
or authority risk, but an observability gap.

**Acknowledgement**: Matrix cancellation behavior is a CI platform concern. The
aggregator's RT-01 fix (missing artifact = block) ensures cancellation does not
silently pass, but the diagnostic experience remains poor. Improving shard failure
attribution is deferred to a future observability work item.

---

#### RT-13: Shard writes to shared output path

**Description**: Multiple shards write their output artifacts to a shared
directory path with predictable names. If two shards run concurrently and both
attempt to write to the same path (due to a naming collision or configuration
error), one artifact may overwrite the other. The aggregator reads only one
artifact and the other shard's result is silently lost.

**Impact**: Low probability under correct configuration, but possible during
refactors or when shard names are changed without updating the output path
conventions. Not a security risk but a reliability risk.

**Acknowledgement**: Shard output paths should include the shard identifier as
a component to prevent collisions. This is a configuration hygiene item deferred
to a follow-up cleanup task.

---

#### RT-14: Nightly deep workflow removed or weakened

**Description**: Observation that nightly workflow files covering deep integration
tests may be silently removed or have their test scope reduced over time as PR
shards expand. Unlike RT-11 (which addresses a specific removal in this PR), this
is a general pattern risk: the nightly workflow surface is not formally inventoried,
so incremental removals are not caught by the drift detector.

**Impact**: Deep integration coverage erodes over time without a visible signal.
The gap is only discovered when a regression occurs that PR shards do not cover.

**Acknowledgement**: A formal inventory of nightly workflows and their test scope
is a governance hygiene item. Adding nightly workflows to the drift detector's
scope is a future work item.
