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
    WorkItem(
        id="BLF-01",
        work_item="BLF-01 — Baseline failure fix",
        depends_on=[],
        why_it_matters="Stabilizes baseline failure posture before downstream readiness claims.",
        risk_if_done_out_of_order="Readiness claims become untrustworthy.",
    ),
    WorkItem(
        id="RFX-04",
        work_item="RFX-04 — Loop-07/08",
        depends_on=["BLF-01"],
        why_it_matters="Establishes replay/observability foundations used by H01 and RMP evidence.",
        risk_if_done_out_of_order="Downstream checkpoints lack verifiable replay and freeze behavior.",
    ),
    WorkItem(
        id="RMP-SUPER-01",
        work_item="RMP-SUPER-01",
        depends_on=["BLF-01", "RFX-04"],
        why_it_matters="Provides roadmap mediation and drift-checked readiness evidence.",
        risk_if_done_out_of_order="Roadmap claims can drift from executable truth.",
    ),
    WorkItem(
        id="H01",
        work_item="H01 — Pre-MVP trust spine review/fix closure",
        depends_on=["BLF-01", "RFX-04", "RMP-SUPER-01"],
        why_it_matters="Confirms trust spine is ready before proof hardening and expansion.",
        risk_if_done_out_of_order="Proof and hardening run on unstable trust-spine assumptions.",
    ),
    WorkItem(
        id="RFX-PROOF-01",
        work_item="RFX LOOP-09/10 — Fix Integrity Proof + closure gate",
        depends_on=["BLF-01", "RFX-04", "RMP-SUPER-01", "H01"],
        why_it_matters="Creates proof-bound trust baseline required by EVL/TPA/CDE/SEL hardening.",
        risk_if_done_out_of_order="Trust-chain hardening occurs without proof-bound closure.",
    ),
    WorkItem(
        id="EVL",
        work_item="EVL hardening",
        depends_on=["RFX-PROOF-01"],
        why_it_matters="Evaluation integrity depends on proof-complete trust spine.",
        risk_if_done_out_of_order="Evaluation signals can be spoofed or incomplete.",
    ),
    WorkItem(
        id="TPA",
        work_item="TPA hardening",
        depends_on=["EVL"],
        why_it_matters="Policy adjudication must consume trusted evaluation outcomes.",
        risk_if_done_out_of_order="Policy outcomes can be based on non-certified evaluation state.",
    ),
    WorkItem(
        id="CDE",
        work_item="CDE hardening",
        depends_on=["TPA"],
        why_it_matters="Decision governance depends on trusted policy adjudication.",
        risk_if_done_out_of_order="Decision logic can bypass policy trust chain.",
    ),
    WorkItem(
        id="SEL",
        work_item="SEL hardening",
        depends_on=["CDE"],
        why_it_matters="Enforcement must follow controlled decision provenance.",
        risk_if_done_out_of_order="Execution may enforce untrusted decision paths.",
    ),
    WorkItem(
        id="MET",
        work_item="MET",
        depends_on=["RFX-PROOF-01", "SEL"],
        why_it_matters="Metrics trust must be grounded in completed core trust spine.",
        risk_if_done_out_of_order="Metrics can falsely signal maturity before trust closure.",
    ),
    WorkItem(
        id="HOP",
        work_item="HOP",
        depends_on=["MET"],
        why_it_matters="Higher-order optimization depends on trustworthy metrics.",
        risk_if_done_out_of_order="Optimization can reinforce incorrect or unsafe behavior.",
    ),
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
