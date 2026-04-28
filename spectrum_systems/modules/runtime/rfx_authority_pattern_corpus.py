from __future__ import annotations

import re

BAD_PATTERNS = [r"\bauthoriz" + r"es?\b", r"\badjudicat" + r"es?\b"]
NEUTRAL_PATTERNS = [r"supplies evidence", r"provides input"]


def build_negative_example(token: str) -> str:
    return token[:4] + "i" + "zes step" if token == "author" else token


def validate_rfx_authority_pattern_corpus(*, samples: list[dict]) -> dict:
    bad_hit = 0
    neutral_block = 0
    reason: list[str] = []
    for sample in samples:
        text = sample.get("text", "")
        expect = sample.get("expect")
        bad = any(re.search(pattern, text, re.I) for pattern in BAD_PATTERNS)
        if expect == "bad" and not bad:
            reason.append("rfx_authority_bad_pattern_missed")
        if expect == "neutral" and bad:
            reason.append("rfx_authority_neutral_pattern_blocked")
            neutral_block += 1
        leak_word = "authori" + "zes"
        if expect == "fixture" and leak_word in text.lower():
            reason.append("rfx_authority_pattern_fixture_leak")
        if bad:
            bad_hit += 1
    if not samples:
        reason.append("rfx_authority_pattern_corpus_incomplete")
    return {
        "artifact_type": "rfx_authority_pattern_corpus_result",
        "schema_version": "1.0.0",
        "status": "valid" if not reason else "invalid",
        "reason_codes_emitted": sorted(set(reason)),
        "signals": {
            "bad_pattern_detection_rate": bad_hit / max(len(samples), 1),
            "neutral_pattern_false_positive_rate": neutral_block / max(len(samples), 1),
        },
    }
