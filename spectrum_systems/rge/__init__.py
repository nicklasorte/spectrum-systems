"""Roadmap Generation Engine (RGE).

RGE is a self-driving, self-healing roadmap system that enforces three
principles on every phase it proposes:

    1. Kill Complexity Early      — every phase must justify itself
    2. Build Fewer, Stronger Loops — every phase must strengthen a loop leg
    3. Optimize for Debuggability — every phase must be explainable

Only phases passing all three gates enter the roadmap. Every gate emits a
schema-validated artifact. RGE never mutates the repo directly — it emits
candidate roadmaps that ship via governed promotion (PR gate).
"""
from __future__ import annotations

CANONICAL_LOOP_LEGS = frozenset({
    "AEX", "PQX", "EVL", "TPA", "CDE", "SEL",
    "REP", "LIN", "OBS", "SLO",
})
