#!/usr/bin/env python3
"""Deterministic PDF to Markdown converter for repo-native source ingestion.

Extraction is exact-text oriented and intentionally conservative:
- No summarization or inferred content.
- Best-effort text extraction from PDF page content streams.
- Deterministic normalization for stable repeated runs.
"""

from __future__ import annotations

import argparse
import re
import sys
import zlib
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

_PAGE_NUMBER_RE = re.compile(r"^(?:page\s+)?\d+(?:\s*/\s*\d+)?$", re.IGNORECASE)
_OBJECT_RE = re.compile(rb"(\d+)\s+(\d+)\s+obj\b(.*?)\bendobj\b", re.DOTALL)
_STREAM_RE = re.compile(rb"stream\r?\n(.*?)\r?\nendstream", re.DOTALL)
_TEXT_BLOCK_RE = re.compile(rb"BT\b(.*?)\bET", re.DOTALL)
_TEXT_TJ_RE = re.compile(rb"\((?:\\.|[^\\)])*\)\s*Tj")
_TEXT_TJ_ARRAY_RE = re.compile(rb"\[(.*?)\]\s*TJ", re.DOTALL)
_STRING_RE = re.compile(rb"\((?:\\.|[^\\)])*\)")


@dataclass(frozen=True)
class ExtractionResult:
    page_lines: list[list[str]]
    markdown: str


def _decode_pdf_string(raw: bytes) -> str:
    body = raw[1:-1]
    out: list[int] = []
    i = 0
    while i < len(body):
        ch = body[i]
        if ch != 0x5C:  # backslash
            out.append(ch)
            i += 1
            continue

        i += 1
        if i >= len(body):
            break
        esc = body[i]
        i += 1
        mapping = {
            ord("n"): ord("\n"),
            ord("r"): ord("\r"),
            ord("t"): ord("\t"),
            ord("b"): 0x08,
            ord("f"): 0x0C,
            ord("("): ord("("),
            ord(")"): ord(")"),
            ord("\\"): ord("\\"),
        }
        if esc in mapping:
            out.append(mapping[esc])
            continue
        if 48 <= esc <= 55:  # octal escape
            oct_digits = bytes([esc])
            for _ in range(2):
                if i < len(body) and 48 <= body[i] <= 55:
                    oct_digits += bytes([body[i]])
                    i += 1
                else:
                    break
            out.append(int(oct_digits, 8))
            continue
        out.append(esc)

    return bytes(out).decode("utf-8", errors="replace")


def _decode_stream(stream_payload: bytes) -> bytes:
    payload = stream_payload.strip(b"\r\n")
    try:
        return zlib.decompress(payload)
    except zlib.error:
        return payload


def _extract_text_from_stream(stream_payload: bytes) -> list[str]:
    lines: list[str] = []
    decoded = _decode_stream(stream_payload)
    for block in _TEXT_BLOCK_RE.findall(decoded):
        for match in _TEXT_TJ_RE.findall(block):
            text_obj = _STRING_RE.search(match)
            if text_obj:
                lines.append(_decode_pdf_string(text_obj.group(0)))
        for arr_match in _TEXT_TJ_ARRAY_RE.findall(block):
            parts = [_decode_pdf_string(part) for part in _STRING_RE.findall(arr_match)]
            if parts:
                lines.append("".join(parts))
    return lines


def extract_page_lines(pdf_bytes: bytes) -> list[list[str]]:
    objects: dict[int, bytes] = {}
    ordered_ids: list[int] = []
    for obj_match in _OBJECT_RE.finditer(pdf_bytes):
        obj_id = int(obj_match.group(1))
        body = obj_match.group(3)
        objects[obj_id] = body
        ordered_ids.append(obj_id)

    page_ids: list[int] = []
    for obj_id in ordered_ids:
        body = objects[obj_id]
        if b"/Type /Page" in body and b"/Type /Pages" not in body:
            page_ids.append(obj_id)

    pages: list[list[str]] = []
    for page_id in page_ids:
        body = objects[page_id]
        refs = [int(value) for value in re.findall(rb"/Contents\s+(\d+)\s+0\s+R", body)]
        if not refs:
            refs = [int(value) for value in re.findall(rb"(\d+)\s+0\s+R", body)]

        page_lines: list[str] = []
        seen_refs: set[int] = set()
        for ref in refs:
            if ref in seen_refs or ref not in objects:
                continue
            seen_refs.add(ref)
            for stream in _STREAM_RE.findall(objects[ref]):
                page_lines.extend(_extract_text_from_stream(stream))

        pages.append([line.strip() for line in page_lines if line.strip()])

    return pages


def _normalize_table_like_line(line: str) -> str:
    if "  " not in line:
        return line
    cells = [cell.strip() for cell in re.split(r"\s{2,}", line) if cell.strip()]
    if len(cells) < 3:
        return line
    return "| " + " | ".join(cells) + " |"


def _is_list_line(line: str) -> bool:
    return bool(re.match(r"^(-|\*|\+)\s+", line) or re.match(r"^\d+[\.)]\s+", line))


def _is_heading_candidate(line: str) -> bool:
    stripped = line.strip()
    if not stripped or len(stripped) > 90:
        return False
    if re.match(r"^\d+(?:\.\d+)*[\.)]?\s+[A-Z]", stripped):
        return True
    if stripped == stripped.upper() and re.search(r"[A-Z]", stripped):
        return True
    return bool(re.match(r"^[A-Z][A-Za-z0-9][A-Za-z0-9\s\-:/,&()]+$", stripped) and len(stripped.split()) <= 10)


def _suppress_repeated_artifacts(page_lines: list[list[str]]) -> list[list[str]]:
    counts: Counter[str] = Counter()
    for lines in page_lines:
        for line in set(lines):
            if len(line) <= 100:
                counts[line] += 1

    threshold = max(2, int(len(page_lines) * 0.6))
    repeated = {line for line, n in counts.items() if n >= threshold}

    cleaned: list[list[str]] = []
    for lines in page_lines:
        output: list[str] = []
        for line in lines:
            normalized = line.strip()
            if not normalized:
                continue
            if _PAGE_NUMBER_RE.match(normalized):
                continue
            if normalized in repeated and len(normalized.split()) <= 10:
                continue
            if re.fullmatch(r"\[\d+\]", normalized):
                continue
            output.append(normalized)
        cleaned.append(output)
    return cleaned


def _normalize_lines(lines: list[str]) -> list[str]:
    normalized: list[str] = []
    i = 0
    while i < len(lines):
        line = re.sub(r"\s+", " ", lines[i]).strip()
        if not line:
            i += 1
            continue

        line = re.sub(r"^[•‣◦▪–—]\s*", "- ", line)
        line = re.sub(r"^o\s+", "- ", line)
        line = re.sub(r"^(\d+)\)\s+", r"\1. ", line)

        if i + 1 < len(lines):
            nxt = re.sub(r"\s+", " ", lines[i + 1]).strip()
            if line and nxt:
                if _is_heading_candidate(line) and _is_heading_candidate(nxt) and not line.endswith(":"):
                    line = f"{line} {nxt}"
                    i += 1

        line = _normalize_table_like_line(line)
        normalized.append(line)
        i += 1

    merged: list[str] = []
    for line in normalized:
        if not merged:
            merged.append(line)
            continue

        prev = merged[-1]
        if (
            prev
            and not prev.endswith((".", ":", "?", "!", "|"))
            and not _is_list_line(prev)
            and not _is_heading_candidate(prev)
            and not _is_list_line(line)
            and not _is_heading_candidate(line)
        ):
            merged[-1] = f"{prev} {line}".strip()
        else:
            merged.append(line)

    return merged


def normalize_to_markdown(page_lines: list[list[str]]) -> str:
    cleaned_pages = _suppress_repeated_artifacts(page_lines)
    sections: list[str] = []
    for lines in cleaned_pages:
        normalized = _normalize_lines(lines)
        if normalized:
            sections.append("\n".join(normalized))

    output = "\n\n".join(section for section in sections if section.strip()).strip()
    output = re.sub(r"\n{3,}", "\n\n", output)
    return output


def convert_pdf_to_markdown(input_path: Path, output_path: Path) -> ExtractionResult:
    pdf_bytes = input_path.read_bytes()
    page_lines = extract_page_lines(pdf_bytes)
    markdown = normalize_to_markdown(page_lines)
    if not markdown or len(markdown.strip()) < 40:
        raise ValueError("Extraction produced empty or suspiciously tiny output; check source PDF integrity.")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(markdown + "\n", encoding="utf-8")
    return ExtractionResult(page_lines=page_lines, markdown=markdown)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Convert one PDF to Markdown deterministically. "
            "Default policy is fail if output exists; pass --overwrite to replace."
        )
    )
    parser.add_argument("--input", required=True, help="Path to input PDF file.")
    parser.add_argument("--output", required=True, help="Path to output Markdown file.")
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite output file if it already exists. Default behavior is fail-fast.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    input_path = Path(args.input)
    output_path = Path(args.output)

    if not input_path.is_file():
        print(f"ERROR: input PDF not found: {input_path}", file=sys.stderr)
        return 2
    if input_path.suffix.lower() != ".pdf":
        print(f"ERROR: input file must be a .pdf: {input_path}", file=sys.stderr)
        return 2

    if output_path.exists() and not args.overwrite:
        print(
            f"ERROR: output file already exists: {output_path}. "
            "Use --overwrite to replace it.",
            file=sys.stderr,
        )
        return 2

    try:
        result = convert_pdf_to_markdown(input_path, output_path)
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: conversion failed: {exc}", file=sys.stderr)
        return 1

    print(
        f"Converted {input_path} -> {output_path} "
        f"({len(result.page_lines)} pages, {len(result.markdown)} chars)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
