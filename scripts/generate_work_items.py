#!/usr/bin/env python3
"""
Generate canonical work items from governance review artifacts.

Ingests:
  - design-reviews/*.actions.json         (claude-review schema v1.0.0)
  - docs/review-actions/*.json            (review action tracker JSON)

Produces:
  - governance/work-items/work-items.json (machine-readable work item list)
  - governance/work-items/work-items-summary.md (human-readable summary)

Usage:
  python scripts/generate_work_items.py
  python scripts/generate_work_items.py --dry-run    # print only, no file writes
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
DESIGN_REVIEWS_DIR = REPO_ROOT / "design-reviews"
REVIEW_ACTIONS_DIR = REPO_ROOT / "docs" / "review-actions"
OUTPUT_DIR = REPO_ROOT / "governance" / "work-items"
OUTPUT_JSON = OUTPUT_DIR / "work-items.json"
OUTPUT_SUMMARY = OUTPUT_DIR / "work-items-summary.md"
WORK_ITEM_SCHEMA_PATH = REPO_ROOT / "schemas" / "work-item.schema.json"

# Severity → priority score mapping (base values; blocking items get +10)
SEVERITY_SCORE: dict[str, int] = {
    "critical": 90,
    "required": 80,
    "high": 70,
    "medium": 50,
    "low": 30,
    "informational": 15,
}

# Map source severity labels to canonical schema enum
SEVERITY_NORMALISE: dict[str, str] = {
    "critical": "critical",
    "required": "high",
    "high": "high",
    "medium": "medium",
    "low": "low",
    "informational": "low",
    "info": "low",
}

# Category alias normalisation
CATEGORY_NORMALISE: dict[str, str] = {
    "governance-enforcement": "governance-enforcement",
    "ci-enforcement": "ci-enforcement",
    "architecture-boundary": "architecture-boundary",
    "boundary-enforcement": "boundary-enforcement",
    "ecosystem-registry": "ecosystem-registry",
    "governance-coverage": "governance-coverage",
    "contract-stability": "contract-stability",
    "governance": "governance",
    "contract": "contract",
    "schema": "schema",
    "pipeline": "pipeline",
    "documentation": "documentation",
    "evaluation": "evaluation",
    "observability": "observability",
}

VALID_CATEGORIES = {
    "governance",
    "contract",
    "schema",
    "pipeline",
    "documentation",
    "ci-enforcement",
    "boundary-enforcement",
    "architecture-boundary",
    "ecosystem-registry",
    "governance-enforcement",
    "governance-coverage",
    "contract-stability",
    "evaluation",
    "observability",
    "other",
}

VALID_STATUSES = {"open", "in-progress", "resolved", "deferred"}


def _today() -> str:
    return date.today().isoformat()


def _normalise_severity(raw: str) -> str:
    return SEVERITY_NORMALISE.get(str(raw).lower(), "low")


def _normalise_category(raw: str) -> str:
    normalised = CATEGORY_NORMALISE.get(str(raw).lower())
    if normalised and normalised in VALID_CATEGORIES:
        return normalised
    # Fallback: if raw is already a valid category keep it
    if str(raw).lower() in VALID_CATEGORIES:
        return str(raw).lower()
    return "other"


def _normalise_status(raw: str) -> str:
    """Map source status values to canonical work item status."""
    mapping = {
        "open": "open",
        "in_progress": "in-progress",
        "in-progress": "in-progress",
        "blocked": "in-progress",
        "resolved": "resolved",
        "done": "resolved",
        "closed": "resolved",
        "deferred": "deferred",
        "wont_fix": "deferred",
    }
    return mapping.get(str(raw).lower(), "open")


def _priority_score(severity: str, blocking: bool = False) -> int:
    base = SEVERITY_SCORE.get(severity, 30)
    return min(100, base + (10 if blocking else 0))


def _load_json(path: Path) -> Any | None:
    try:
        with path.open("r", encoding="utf-8") as fh:
            return json.load(fh)
    except (json.JSONDecodeError, OSError):
        return None


def _description_text(raw: Any) -> str:
    """Flatten string or list descriptions to a single string."""
    if isinstance(raw, list):
        return " ".join(str(item).strip() for item in raw if item)
    return str(raw).strip()


def _ingest_claude_review(path: Path, counter: list[int]) -> list[dict]:
    """Parse a design-reviews/*.actions.json (claude-review schema v1.0.0) file."""
    data = _load_json(path)
    if not data or not isinstance(data, dict):
        return []

    meta = data.get("review_metadata", {})
    review_id: str = meta.get("review_id", path.stem)
    review_date: str = meta.get("review_date", _today())
    repo: str = meta.get("repository", "spectrum-systems")

    items: list[dict] = []

    for finding in data.get("findings", []):
        if not isinstance(finding, dict):
            continue

        finding_id = finding.get("id", "")
        raw_severity = finding.get("severity", "low")
        raw_category = finding.get("category", "other")
        title = finding.get("title", "").strip()
        description = _description_text(
            finding.get("description", finding.get("recommended_action", ""))
        )
        if not title or not description:
            continue

        severity = _normalise_severity(raw_severity)
        category = _normalise_category(raw_category)
        blocking = raw_severity in ("critical",)
        priority = _priority_score(raw_severity, blocking)

        related: list[str] = []
        files = finding.get("files_affected", [])
        if isinstance(files, list):
            related = [str(f) for f in files if f]
        elif isinstance(files, str) and files.strip():
            related = [files.strip()]
        related.append(str(path.relative_to(REPO_ROOT)))

        counter[0] += 1
        work_item: dict = {
            "work_item_id": f"WI-{counter[0]:04d}",
            "source_type": "review",
            "source_id": review_id,
            "repo": repo,
            "finding_id": finding_id,
            "title": title,
            "description": description,
            "severity": severity,
            "category": category,
            "status": "open",
            "priority_score": priority,
            "blocking": blocking,
            "created_at": review_date,
            "updated_at": _today(),
            "related_artifacts": list(dict.fromkeys(related)),  # dedup, preserve order
        }

        if finding.get("due_date"):
            work_item["due_date"] = finding["due_date"]
        if finding.get("suggested_issue_title"):
            work_item["suggested_issue_title"] = finding["suggested_issue_title"]
        if finding.get("suggested_labels"):
            work_item["suggested_labels"] = finding["suggested_labels"]

        items.append(work_item)

    return items


def _ingest_action_tracker(path: Path, counter: list[int]) -> list[dict]:
    """Parse a docs/review-actions/*.json (action tracker format) file."""
    data = _load_json(path)
    if not data or not isinstance(data, dict):
        return []

    review_id: str = data.get("review_id", "") or path.stem
    review_date: str = data.get("review_date", _today())
    repo: str = "spectrum-systems"

    # Support both "actions" key (claude-review schema) and top-level list fallback
    actions_list = data.get("actions", [])
    if not isinstance(actions_list, list):
        return []

    items: list[dict] = []

    for action in actions_list:
        if not isinstance(action, dict):
            continue

        finding_id = action.get("id", "")
        raw_severity = action.get("severity", action.get("priority", "low"))
        raw_category = action.get("category", "other")
        title = action.get("title", "").strip()
        description = _description_text(
            action.get("description", action.get("recommended_action", ""))
        )
        if not title or not description:
            continue

        severity = _normalise_severity(raw_severity)
        category = _normalise_category(raw_category)
        raw_status = action.get("status", "open")
        status = _normalise_status(raw_status)
        blocking = raw_severity in ("critical", "required")
        priority = _priority_score(raw_severity, blocking)

        related: list[str] = []
        files = action.get("files_affected", action.get("affected_repos", []))
        if isinstance(files, list):
            related = [str(f) for f in files if f]
        elif isinstance(files, str) and files.strip():
            related = [files.strip()]
        related.append(str(path.relative_to(REPO_ROOT)))

        counter[0] += 1
        work_item: dict = {
            "work_item_id": f"WI-{counter[0]:04d}",
            "source_type": "review",
            "source_id": review_id,
            "repo": repo,
            "finding_id": finding_id,
            "title": title,
            "description": description,
            "severity": severity,
            "category": category,
            "status": status,
            "priority_score": priority,
            "blocking": blocking,
            "created_at": review_date,
            "updated_at": _today(),
            "related_artifacts": list(dict.fromkeys(related)),
        }

        if action.get("due_date"):
            work_item["due_date"] = action["due_date"]
        if action.get("suggested_issue_title"):
            work_item["suggested_issue_title"] = action["suggested_issue_title"]
        if action.get("suggested_labels"):
            work_item["suggested_labels"] = action["suggested_labels"]

        # Track carried-forward findings from the action tracker schema
        if action.get("carried_forward_from"):
            work_item["carried_forward_from"] = action["carried_forward_from"]

        items.append(work_item)

    return items


def _deduplicate(items: list[dict]) -> list[dict]:
    """Remove exact duplicate (source_id, finding_id) pairs; keep first occurrence."""
    seen: set[tuple[str, str]] = set()
    unique: list[dict] = []
    for item in items:
        key = (item.get("source_id", ""), item.get("finding_id", ""))
        if key not in seen:
            seen.add(key)
            unique.append(item)
    return unique


def _renumber(items: list[dict]) -> list[dict]:
    """Re-assign sequential WI-NNNN IDs after deduplication."""
    for idx, item in enumerate(items, start=1):
        item["work_item_id"] = f"WI-{idx:04d}"
    return items


def _sort_items(items: list[dict]) -> list[dict]:
    """Sort by priority_score desc, then created_at asc, then finding_id asc."""
    return sorted(
        items,
        key=lambda x: (
            -x.get("priority_score", 0),
            x.get("created_at", ""),
            x.get("finding_id", ""),
        ),
    )


def _generate_summary(items: list[dict], generated_at: str) -> str:
    total = len(items)
    by_severity: dict[str, int] = {}
    by_status: dict[str, int] = {}
    by_category: dict[str, int] = {}
    blocking_count = 0

    for item in items:
        by_severity[item["severity"]] = by_severity.get(item["severity"], 0) + 1
        by_status[item["status"]] = by_status.get(item["status"], 0) + 1
        by_category[item["category"]] = by_category.get(item["category"], 0) + 1
        if item.get("blocking"):
            blocking_count += 1

    lines: list[str] = [
        "# Work Items Summary",
        "",
        f"Generated: {generated_at}  ",
        f"Total work items: **{total}**  ",
        f"Blocking items: **{blocking_count}**",
        "",
        "## Severity Breakdown",
        "",
    ]
    for sev in ("critical", "high", "medium", "low"):
        count = by_severity.get(sev, 0)
        if count:
            lines.append(f"- **{sev.capitalize()}**: {count}")
    lines += [
        "",
        "## Status Breakdown",
        "",
    ]
    for status in ("open", "in-progress", "resolved", "deferred"):
        count = by_status.get(status, 0)
        if count:
            lines.append(f"- **{status}**: {count}")
    lines += [
        "",
        "## Category Breakdown",
        "",
    ]
    for cat, count in sorted(by_category.items(), key=lambda kv: -kv[1]):
        lines.append(f"- **{cat}**: {count}")
    lines += [
        "",
        "## Top Priority Work Items",
        "",
        "| ID | Severity | Status | Title |",
        "|----|----------|--------|-------|",
    ]
    for item in items[:20]:
        wi_id = item["work_item_id"]
        sev = item["severity"]
        st = item["status"]
        title = item["title"][:80]
        lines.append(f"| {wi_id} | {sev} | {st} | {title} |")

    lines += ["", "---", f"*Generated by `scripts/generate_work_items.py`*", ""]
    return "\n".join(lines)


def generate(dry_run: bool = False) -> list[dict]:
    counter: list[int] = [0]  # mutable counter passed by reference
    all_items: list[dict] = []

    # 1. Ingest design-reviews/*.actions.json (claude-review schema)
    for path in sorted(DESIGN_REVIEWS_DIR.glob("*.actions.json")):
        if path.name in ("README.md",):
            continue
        items = _ingest_claude_review(path, counter)
        all_items.extend(items)

    # 2. Ingest docs/review-actions/*.json (action tracker format)
    for path in sorted(REVIEW_ACTIONS_DIR.glob("*.json")):
        items = _ingest_action_tracker(path, counter)
        all_items.extend(items)

    # Deduplicate, sort, and re-number
    all_items = _deduplicate(all_items)
    all_items = _sort_items(all_items)
    all_items = _renumber(all_items)

    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    output = {
        "schema_version": "1.0.0",
        "generated_at": generated_at,
        "source_types": ["review"],
        "total_items": len(all_items),
        "work_items": all_items,
    }

    if dry_run:
        print(json.dumps(output, indent=2))
        return all_items

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with OUTPUT_JSON.open("w", encoding="utf-8") as fh:
        json.dump(output, fh, indent=2)
        fh.write("\n")

    summary_text = _generate_summary(all_items, generated_at)
    with OUTPUT_SUMMARY.open("w", encoding="utf-8") as fh:
        fh.write(summary_text)

    print(
        f"Generated {len(all_items)} work items → {OUTPUT_JSON.relative_to(REPO_ROOT)}",
        file=sys.stderr,
    )
    return all_items


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true", help="Print output without writing files.")
    args = parser.parse_args()
    generate(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
