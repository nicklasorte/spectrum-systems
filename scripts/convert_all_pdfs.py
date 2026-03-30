#!/usr/bin/env python3
"""Batch convert docs/raw/*.pdf into docs/source/*.md.

Policy:
- Default is skip existing markdown outputs.
- Use --overwrite to replace existing outputs.
- Exits non-zero if any conversion fails.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.convert_pdf_to_md import convert_pdf_to_markdown


DEFAULT_RAW_DIR = REPO_ROOT / "docs" / "raw"
DEFAULT_SOURCE_DIR = REPO_ROOT / "docs" / "source"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Batch convert PDF sources into normalized markdown files.")
    parser.add_argument("--raw-dir", default=str(DEFAULT_RAW_DIR), help="Directory containing input PDFs.")
    parser.add_argument("--source-dir", default=str(DEFAULT_SOURCE_DIR), help="Directory for output markdown files.")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing markdown outputs.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    raw_dir = Path(args.raw_dir)
    source_dir = Path(args.source_dir)

    if not raw_dir.is_dir():
        print(f"ERROR: raw directory not found: {raw_dir}", file=sys.stderr)
        return 2

    pdf_files = sorted(raw_dir.glob("*.pdf"))
    if not pdf_files:
        print(f"No PDF files found in {raw_dir}.")
        return 0

    converted = 0
    skipped = 0
    failed = 0

    source_dir.mkdir(parents=True, exist_ok=True)

    for pdf_path in pdf_files:
        output_path = source_dir / f"{pdf_path.stem}.md"
        if output_path.exists() and not args.overwrite:
            print(f"SKIP   {pdf_path.name} -> {output_path.name} (exists; use --overwrite to replace)")
            skipped += 1
            continue

        try:
            result = convert_pdf_to_markdown(pdf_path, output_path)
        except Exception as exc:  # noqa: BLE001
            print(f"FAIL   {pdf_path.name}: {exc}", file=sys.stderr)
            failed += 1
            continue

        print(f"OK     {pdf_path.name} -> {output_path.name} ({len(result.markdown)} chars)")
        converted += 1

    print(
        "Summary: "
        f"total={len(pdf_files)} converted={converted} skipped={skipped} failed={failed}"
    )

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
