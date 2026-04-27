from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class WorkItem:
    id: str
    work_item: str
    depends_on: list[str]
    why_it_matters: str
    risk_if_done_out_of_order: str


LOCKED_SEQUENCE = [
    WorkItem("BLF-01", "BLF-01 — Baseline failure fix", [], "Stabilizes baseline failure posture before downstream readiness claims.", "Readiness claims become untrustworthy."),
    WorkItem("RFX-04", "RFX-04 — Loop-07/08", ["BLF-01"], "Establishes replay/observability foundations used by H01 and RMP evidence.", "Downstream checkpoints lack verifiable replay and freeze behavior."),
    WorkItem("RMP-SUPER-01", "RMP-SUPER-01", ["BLF-01", "RFX-04"], "Provides roadmap mediation and drift-checked readiness evidence.", "Roadmap claims can drift from executable truth."),
    WorkItem("H01", "H01 — Pre-MVP trust spine review/fix closure", ["BLF-01", "RFX-04", "RMP-SUPER-01"], "Confirms trust spine is ready before proof hardening and expansion.", "Proof and hardening run on unstable trust-spine assumptions."),
    WorkItem("RFX-PROOF-01", "RFX LOOP-09/10 — Fix Integrity Proof + closure gate", ["BLF-01", "RFX-04", "RMP-SUPER-01", "H01"], "Creates proof-bound trust baseline required by EVL/TPA/CDE/SEL hardening.", "Trust-chain hardening occurs without proof-bound closure."),
    WorkItem("EVL", "EVL hardening", ["RFX-PROOF-01"], "Evaluation integrity depends on proof-complete trust spine.", "Evaluation signals can be spoofed or incomplete."),
    WorkItem("TPA", "TPA hardening", ["EVL"], "Policy adjudication must consume trusted evaluation outcomes.", "Policy outcomes can be based on non-certified evaluation state."),
    WorkItem("CDE", "CDE hardening", ["TPA"], "Control recommendations depend on trusted policy adjudication.", "Control recommendations can bypass policy trust chain."),
    WorkItem("SEL", "SEL hardening", ["CDE"], "Enforcement must follow controlled recommendation provenance.", "Execution may enforce untrusted recommendation paths."),
    WorkItem("MET", "MET", ["RFX-PROOF-01", "SEL"], "Metrics trust must be grounded in completed core trust spine.", "Metrics can falsely signal maturity before trust closure."),
    WorkItem("HOP", "HOP", ["MET"], "Higher-order optimization depends on trustworthy metrics.", "Optimization can reinforce incorrect or unsafe behavior."),
]


def status_from_done(item_id: str, done: set[str]) -> str:
    return "complete" if item_id in done else "not_started"


def first_unmet(done: set[str]) -> WorkItem | None:
    for item in LOCKED_SEQUENCE:
        if item.id in done:
            continue
        if all(dep in done for dep in item.depends_on):
            return item
    return None
