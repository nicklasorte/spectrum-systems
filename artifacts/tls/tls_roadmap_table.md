| ID | Phase | What It Builds | Why It Matters | Dependencies | Next Step |
| --- | --- | --- | --- | --- | --- |
| TLS-FX-01 | Boundary map bundle | Boundary map artifact with allowed and blocked interfaces. | Defines clear boundary before any integration execution. | artifacts/tls/tls_roadmap_initial.json | TLS-RT-01 |
| TLS-RT-01 | Boundary red-team round | Red-team findings on boundary abuse paths. | Finds fail-open seams before integration. | TLS-FX-01 | TLS-FIX-01 |
| TLS-FIX-01 | Boundary fix bundle | Updated boundary map and blocked-key list. | Ensures boundary hardening closes observed failure modes. | TLS-RT-01 | TLS-FX-02 |
| TLS-FX-02 | Integration seam bundle | Integration seam contract with fail_closed behavior. | Prevents regressions while wiring TLS outputs. | TLS-FIX-01, artifacts/tls/system_graph_integration_report.json | TLS-RT-02 |
| TLS-RT-02 | Integration red-team round | Seam red-team findings and risk labels. | Catches fallback regressions pre-runtime rollout. | TLS-FX-02 | TLS-FIX-02 |
| TLS-FIX-02 | Integration fix bundle | Patched seam contract and fallback guards. | Restores fail_closed integration behavior. | TLS-RT-02 | TLS-FX-03 |
| TLS-FX-03 | Ranking trust calibration bundle | Calibration profile and tie-break table. | Improves recommendation stability under sparse evidence. | TLS-FIX-02, artifacts/tls/tls_ranking_review_report.json | TLS-RT-03 |
| TLS-RT-03 | Ranking red-team round | Ranking red-team findings. | Finds unstable ordering paths early. | TLS-FX-03 | TLS-FIX-03 |
| TLS-FIX-03 | Ranking fix bundle | Updated calibration profile and guard thresholds. | Locks deterministic recommendation ordering. | TLS-RT-03 | TLS-FX-04 |
| TLS-FX-04 | Action layer schema bundle | Action layer schema and rationale packet template. | Keeps TLS outputs operator-usable and read-only. | TLS-FIX-03 | TLS-RT-04 |
| TLS-RT-04 | Action layer red-team round | Action layer red-team report. | Prevents recommendation packet ambiguity. | TLS-FX-04 | TLS-FIX-04 |
| TLS-FIX-04 | Action layer fix bundle | Fixed action layer schema. | Ensures recommendation-only output format remains strict. | TLS-RT-04 | TLS-FX-05 |
| TLS-FX-05 | Control bridge mapping bundle | Field mapping contract with blocked owner keys. | Allows retrieve of TLS context without ownership crossing. | TLS-FIX-04, artifacts/tls/tls_control_input_artifact.json | TLS-RT-05 |
| TLS-RT-05 | Control bridge red-team round | Control bridge red-team findings. | Detects boundary bypass attempts before use. | TLS-FX-05 | TLS-FIX-05 |
| TLS-FIX-05 | Control bridge fix bundle | Fixed owner-safe control bridge mapping. | Maintains safe cross-system retrieve path. | TLS-RT-05 | TLS-FX-06 |
| TLS-FX-06 | Learning loop ledger bundle | Learning ledger schema and bounded update profile. | Prevents uncontrolled recommendation drift. | TLS-FIX-05, artifacts/tls/tls_learning_record.json | TLS-RT-06 |
| TLS-RT-06 | Learning loop red-team round | Learning loop red-team findings. | Surfaces drift and instability risks early. | TLS-FX-06 | TLS-FIX-06 |
| TLS-FIX-06 | Learning loop fix bundle | Fixed learning loop ledger and update caps. | Stabilizes recommendation updates across runs. | TLS-RT-06 | TLS-FX-07 |
| TLS-FX-07 | Drift detection bundle | Drift signal artifact and baseline rules. | Detects regressions before operator-facing surfaces refresh. | TLS-FIX-06 | TLS-RT-07 |
| TLS-RT-07 | Drift detection red-team round | Drift red-team report. | Ensures drift checks fail closed on invalid baselines. | TLS-FX-07 | TLS-FIX-07 |
| TLS-FIX-07 | Drift detection fix bundle | Fixed drift detection profile. | Prevents repeated stale-baseline drift misses. | TLS-RT-07 | TLS-FX-08 |
| TLS-FX-08 | Dataset map bundle | Dataset map with coverage metadata and version pins. | Anchors eval governance to traceable inputs. | TLS-FIX-07, artifacts/tls/system_evidence_attachment.json | TLS-FX-09 |
| TLS-FX-09 | Eval governance gate bundle | Eval governance gate artifact and schema checks. | Blocks unverified updates from entering later phases. | TLS-FX-08 | TLS-RT-08 |
| TLS-RT-08 | Dataset+eval red-team round | Dataset/eval red-team findings. | Validates governance gate under adversarial inputs. | TLS-FX-09 | TLS-FIX-08 |
| TLS-FIX-08 | Dataset+eval fix bundle | Fixed dataset map and eval gate artifacts. | Maintains trusted update eligibility path. | TLS-RT-08 | TLS-FX-10 |
| TLS-FX-10 | Operator intelligence bundle | Operator intelligence summary artifact and retrieve index. | Improves clarity without dashboard coupling. | TLS-FIX-08 | TLS-RT-09 |
| TLS-RT-09 | Operator intelligence red-team round | Operator intelligence red-team report. | Protects operator retrieve quality and trust. | TLS-FX-10 | TLS-FIX-09 |
| TLS-FIX-09 | Operator intelligence fix bundle | Fixed operator intelligence summary artifact. | Keeps operator-facing outputs clear and bounded. | TLS-RT-09 | TLS-FX-11 |
| TLS-FX-11 | Policy hook schema bundle | Policy hook schema and override input contract. | Allows owner context retrieve without ownership transfer. | TLS-FIX-09 | TLS-RT-10 |
| TLS-RT-10 | Policy hook red-team round | Policy hook red-team findings. | Ensures hooks remain recommendation-only and read-only. | TLS-FX-11 | TLS-FIX-10 |
| TLS-FIX-10 | Policy hook fix bundle | Fixed policy hook schema artifact. | Closes bypass paths before simulation phase. | TLS-RT-10 | TLS-FX-12 |
| TLS-FX-12 | Simulation harness bundle | Simulation outcomes artifact with scenario matrix. | Validates behavior under edge and adversarial inputs. | TLS-FIX-10 | TLS-RT-11 |
| TLS-RT-11 | Simulation red-team round | Simulation red-team report. | Prevents latent fallback paths from reaching final integration. | TLS-FX-12 | TLS-FIX-11 |
| TLS-FIX-11 | Simulation fix bundle | Fixed simulation outcomes artifact and guard notes. | Ensures stable basis for final integration. | TLS-RT-11 | TLS-FX-13 |
| TLS-FX-13 | Final OS integration map bundle | Final OS integration map and compatibility checklist. | Completes operator-ready integration without ownership crossing. | TLS-FIX-11 | TLS-RT-12 |
| TLS-RT-12 | Final OS integration red-team round | Final integration red-team findings. | Catches last-mile integration failures before closeout artifact creation. | TLS-FX-13 | TLS-FIX-12 |
| TLS-FIX-12 | Final OS integration fix bundle | Fixed final OS integration map and readiness check artifact. | Produces operator-ready integration artifact with fail_closed behavior. | TLS-RT-12 | Complete |

## Recommended execution order
- TLS-FX-01
- TLS-RT-01
- TLS-FIX-01
- TLS-FX-02
- TLS-RT-02
- TLS-FIX-02
- TLS-FX-03
- TLS-RT-03
- TLS-FIX-03
- TLS-FX-04
- TLS-RT-04
- TLS-FIX-04
- TLS-FX-05
- TLS-RT-05
- TLS-FIX-05
- TLS-FX-06
- TLS-RT-06
- TLS-FIX-06
- TLS-FX-07
- TLS-RT-07
- TLS-FIX-07
- TLS-FX-08
- TLS-FX-09
- TLS-RT-08
- TLS-FIX-08
- TLS-FX-10
- TLS-RT-09
- TLS-FIX-09
- TLS-FX-11
- TLS-RT-10
- TLS-FIX-10
- TLS-FX-12
- TLS-RT-11
- TLS-FIX-11
- TLS-FX-13
- TLS-RT-12
- TLS-FIX-12

## Safe bundles (max 2–3 steps per prompt)
- **TLS-BND-01**: TLS-FX-01, TLS-RT-01, TLS-FIX-01 — Boundary hardening before integration.
- **TLS-BND-02**: TLS-FX-02, TLS-RT-02, TLS-FIX-02 — Integration seam safety and fallback guard closure.
- **TLS-BND-03**: TLS-FX-03, TLS-RT-03, TLS-FIX-03 — Ranking trust calibration and hardening.
- **TLS-BND-04**: TLS-FX-04, TLS-RT-04, TLS-FIX-04 — Action-layer schema hardening.
- **TLS-BND-05**: TLS-FX-05, TLS-RT-05, TLS-FIX-05 — Owner-safe control bridge hardening.
- **TLS-BND-06**: TLS-FX-06, TLS-RT-06, TLS-FIX-06 — Learning loop bounded updates.
- **TLS-BND-07**: TLS-FX-07, TLS-RT-07, TLS-FIX-07 — Drift detection guard hardening.
- **TLS-BND-08**: TLS-FX-08, TLS-FX-09, TLS-RT-08 — Dataset map + eval gate + red-team pass.
- **TLS-BND-09**: TLS-FIX-08, TLS-FX-10, TLS-RT-09 — Close eval findings then operator intelligence pass.
- **TLS-BND-10**: TLS-FIX-09, TLS-FX-11, TLS-RT-10 — Operator intelligence closure and policy hook hardening.
- **TLS-BND-11**: TLS-FIX-10, TLS-FX-12, TLS-RT-11 — Policy hook closure and simulation red-team.
- **TLS-BND-12**: TLS-FIX-11, TLS-FX-13, TLS-RT-12 — Simulation closure and final integration red-team.
- **TLS-BND-13**: TLS-FIX-12 — Final readiness gate and closeout artifact.

## Next 3 prompts to run
- Run bundle TLS-BND-01: build boundary map, run boundary red-team, apply fixes.
- Run bundle TLS-BND-02: build integration seam contract, red-team fallback risk, apply seam fixes.
- Run bundle TLS-BND-03: calibrate ranking trust, red-team sparse/adversarial ordering, apply ranking fixes.
