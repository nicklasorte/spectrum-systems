#!/usr/bin/env python3
"""Fail-closed strategy compliance enforcement for roadmap prompts and outputs."""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import re
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROMPTS = [Path("docs/architecture/strategy_guided_roadmap_prompt.md")]
DEFAULT_ROADMAPS = [
    Path("docs/roadmaps/system_roadmap.md"),
    Path("docs/roadmap/system_roadmap.md"),
]
DEFAULT_REPORT = Path("docs/reports/strategy_drift_report.md")

AGENT_FIRST_PATTERNS = [
    re.compile(r"\bagent-first\b", re.IGNORECASE),
    re.compile(r"\bprompt-first\b", re.IGNORECASE),
    re.compile(r"\bagent-centric\b", re.IGNORECASE),
    re.compile(r"\bcapability-first\b", re.IGNORECASE),
]


@dataclass(frozen=True)
class Violation:
    severity: str
    code: str
    message: str
    file: Path


class StrategyComplianceChecker:
    def __init__(self, prompt_files: list[Path], roadmap_files: list[Path], report_path: Path) -> None:
        self.prompt_files = prompt_files
        self.roadmap_files = roadmap_files
        self.report_path = report_path
        self.violations: list[Violation] = []

    def add_violation(self, severity: str, code: str, message: str, file: Path) -> None:
        self.violations.append(Violation(severity=severity, code=code, message=message, file=file))

    def read_file(self, path: Path) -> str:
        full_path = REPO_ROOT / path
        if not full_path.is_file():
            self.add_violation("block", "missing_file", "Required file is missing.", path)
            return ""
        return full_path.read_text(encoding="utf-8")

    def check_prompt_controls(self) -> None:
        strategy_lock_pattern = re.compile(r'strategy_version\s*:\s*"strategy-control\.md::[^"\n]+"', re.IGNORECASE)

        for file_path in self.prompt_files:
            text = self.read_file(file_path)
            if not text:
                continue

            order_lines = [line.strip() for line in text.splitlines() if re.match(r"^\d+\.\s+", line.strip())]
            if not order_lines:
                self.add_violation("block", "missing_input_order", "Roadmap prompt must declare ordered inputs with strategy first.", file_path)
            else:
                first_item = order_lines[0]
                if "docs/architecture/strategy-control.md" not in first_item:
                    self.add_violation("block", "strategy_not_first_input", "Roadmap prompt must include strategy as the first input.", file_path)
                if len(order_lines) < 2 or "docs/architecture/foundation_pqx_eval_control.md" not in order_lines[1]:
                    self.add_violation(
                        "block",
                        "foundation_not_second_input",
                        "Roadmap prompt must include foundation_pqx_eval_control.md as the second input.",
                        file_path,
                    )

            if "Every step MUST reference at least one strategy invariant" not in text:
                self.add_violation("block", "missing_invariant_requirement", "Prompt must require invariant validation per step.", file_path)
            if "Foundation document is mandatory architecture authority" not in text:
                self.add_violation(
                    "block",
                    "missing_foundation_authority_requirement",
                    "Prompt must require the foundation architecture document as mandatory authority.",
                    file_path,
                )
            if "present_and_governed" not in text or "present_but_bypassable" not in text or "missing" not in text:
                self.add_violation(
                    "block",
                    "missing_foundation_gap_classification",
                    "Prompt must include foundation gap classification statuses.",
                    file_path,
                )
            if "whether golden path is buildable" not in text:
                self.add_violation(
                    "block",
                    "missing_golden_path_buildability_check",
                    "Prompt must require explicit golden path buildability status.",
                    file_path,
                )
            if "proposes expansion while foundation is incomplete" not in text:
                self.add_violation(
                    "block",
                    "missing_foundation_expansion_block",
                    "Prompt must fail closed when expansion is proposed while foundation is incomplete.",
                    file_path,
                )

            if "drift" not in text.lower():
                self.add_violation("block", "missing_drift_rules", "Prompt must include drift detection rules.", file_path)

            if not strategy_lock_pattern.search(text):
                self.add_violation("block", "missing_strategy_version_lock", "Prompt must require strategy_version lock: strategy-control.md::<hash/version>.", file_path)

    def _markdown_tables(self, text: str) -> list[tuple[list[str], list[list[str]]]]:
        lines = text.splitlines()
        tables: list[tuple[list[str], list[list[str]]]] = []
        i = 0
        while i < len(lines) - 1:
            if lines[i].strip().startswith("|") and lines[i + 1].strip().startswith("|"):
                header = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                sep_cells = [c.strip() for c in lines[i + 1].strip().strip("|").split("|")]
                if all(set(cell) <= {"-", ":", " "} and cell for cell in sep_cells):
                    rows: list[list[str]] = []
                    j = i + 2
                    while j < len(lines) and lines[j].strip().startswith("|"):
                        rows.append([c.strip() for c in lines[j].strip().strip("|").split("|")])
                        j += 1
                    tables.append((header, rows))
                    i = j
                    continue
            i += 1
        return tables

    def check_roadmap_output_contract(self) -> None:
        required_columns = ["Strategy Alignment", "Primary Trust Gain"]
        for file_path in self.roadmap_files:
            text = self.read_file(file_path)
            if not text:
                continue
            tables = self._markdown_tables(text)
            if not tables:
                self.add_violation("block", "missing_roadmap_table", "Roadmap output must contain markdown table output.", file_path)
                continue

            table_with_required_columns = False
            for headers, rows in tables:
                if all(col in headers for col in required_columns):
                    table_with_required_columns = True
                    indices = {col: headers.index(col) for col in required_columns}
                    for row_idx, row in enumerate(rows, start=1):
                        for col, idx in indices.items():
                            value = row[idx].strip() if idx < len(row) else ""
                            if not value:
                                self.add_violation(
                                    "block",
                                    "missing_required_row_field",
                                    f"Roadmap row {row_idx} missing required column '{col}'.",
                                    file_path,
                                )
            if not table_with_required_columns:
                self.add_violation(
                    "block",
                    "missing_strategy_trust_columns",
                    "Roadmap table must include both 'Strategy Alignment' and 'Primary Trust Gain' columns.",
                    file_path,
                )

    def check_violation_signals(self) -> None:
        target_files = [*self.prompt_files, *self.roadmap_files]
        for file_path in target_files:
            text = self.read_file(file_path)
            if not text:
                continue
            lowered = text.lower()

            for line in text.splitlines():
                lowered_line = line.lower()
                if any(pattern.search(line) for pattern in AGENT_FIRST_PATTERNS):
                    if "agent-first or prompt-first steps" in lowered_line:
                        continue
                    if "roadmap includes agent-first" in lowered_line:
                        continue
                    if any(token in lowered_line for token in ("invalid", "forbidden", "must not", "reject")):
                        continue
                    self.add_violation(
                        "freeze",
                        "agent_first_language",
                        "Forbidden agent-first language found outside invalid-condition guardrails.",
                        file_path,
                    )
                    break

            if "eval" not in lowered:
                self.add_violation("block", "missing_eval_reference", "Missing eval references; include explicit eval linkage.", file_path)

            if "control loop" not in lowered and "control-loop" not in lowered and "cl-" not in lowered:
                self.add_violation("block", "missing_control_loop_integration", "Missing control-loop integration references.", file_path)

            if "replay" not in lowered or "trace" not in lowered:
                self.add_violation("freeze", "missing_replay_trace", "Missing replay and/or trace considerations.", file_path)

            if "governance" not in lowered:
                self.add_violation("freeze", "capability_without_governance", "Capability references must include governance linkage.", file_path)

    def write_drift_report(self) -> None:
        report_full_path = REPO_ROOT / self.report_path
        report_full_path.parent.mkdir(parents=True, exist_ok=True)

        lines = [
            "# Strategy Drift Report",
            "",
            "## Compliance Result",
            "FAIL" if self.violations else "PASS",
            "",
            "## Violations Found",
        ]
        if not self.violations:
            lines.append("- None")
        else:
            for violation in self.violations:
                lines.append(
                    f"- [{violation.severity.upper()}] `{violation.code}` in `{violation.file}`: {violation.message}"
                )

        lines.extend(["", "## Recommended Fixes"])
        if not self.violations:
            lines.append("- No fixes required.")
        else:
            for violation in self.violations:
                lines.append(
                    f"- `{violation.code}` ({violation.severity}): Update `{violation.file}` to satisfy the missing strategy-control requirement."
                )

        report_full_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def run(self) -> int:
        self.check_prompt_controls()
        self.check_roadmap_output_contract()
        self.check_violation_signals()
        self.write_drift_report()

        if self.violations:
            print("FAIL")
            for violation in self.violations:
                print(
                    f"- [{violation.severity.upper()}] {violation.code} | {violation.file} | {violation.message}"
                )
            return 1

        print("PASS")
        print("- No strategy compliance violations detected.")
        return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate strategy compliance for roadmap prompts and outputs.")
    parser.add_argument(
        "--prompt",
        action="append",
        dest="prompts",
        default=None,
        help="Path to a roadmap prompt markdown file (repeatable).",
    )
    parser.add_argument(
        "--roadmap",
        action="append",
        dest="roadmaps",
        default=None,
        help="Path to a roadmap output markdown file (repeatable).",
    )
    parser.add_argument(
        "--report",
        default=str(DEFAULT_REPORT),
        help="Path to write strategy drift report markdown.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    prompt_files = [Path(p) for p in args.prompts] if args.prompts else DEFAULT_PROMPTS
    roadmap_files = [Path(p) for p in args.roadmaps] if args.roadmaps else DEFAULT_ROADMAPS
    report_path = Path(args.report)

    checker = StrategyComplianceChecker(
        prompt_files=prompt_files,
        roadmap_files=roadmap_files,
        report_path=report_path,
    )
    return checker.run()


if __name__ == "__main__":
    sys.exit(main())
