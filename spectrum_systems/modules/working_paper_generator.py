"""
Working Paper Generator — spectrum_systems/modules/working_paper_generator.py

Converts meeting transcripts + slide intelligence + gap analysis into a
structured, report-ready working paper that reflects the clearest argument,
not the loudest voice.

Design principles:
  - Deterministic (no LLM calls, no network I/O)
  - Rule-based composition from structured inputs
  - Full traceability: every claim references its source
  - Backward compatible: all inputs except structured_transcript are optional
  - FCC/NTIA-defensible output structure

Output schema:
    {
      "title": "...",
      "executive_summary": "...",
      "purpose_and_scope": "...",
      "system_description": "...",
      "technical_analysis": "...",
      "key_findings": [...],
      "risks_and_uncertainties": [...],
      "decisions_and_recommendations": [...],
      "open_questions_for_agencies": [...],
      "appendix": {
          "source_traceability": [...],
          "slide_alignment_summary": [...],
          "discussion_gaps": [...]
      }
    }
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

# ─── Constants ────────────────────────────────────────────────────────────────

_SCHEMA_VERSION = "1.0.0"

# Keywords that indicate a technical claim about interference / sharing
_INTERFERENCE_KEYWORDS = {
    "interference",
    "jamming",
    "desensitization",
    "co-channel",
    "adjacent-channel",
    "noise floor",
    "i/n",
    "carrier-to-noise",
    "c/n",
    "overload",
    "blocking",
    "spurious",
    "harmonic",
    "pfd",
    "eirp",
    "epfd",
}

_PROTECTION_KEYWORDS = {
    "protection criteria",
    "protection zone",
    "exclusion zone",
    "separation distance",
    "guard band",
    "coordination zone",
    "threshold",
    "margin",
    "link budget",
}

_UNCERTAINTY_KEYWORDS = {
    "assumed",
    "assumption",
    "uncertain",
    "unclear",
    "unknown",
    "pending",
    "tbd",
    "not validated",
    "unvalidated",
    "needs verification",
    "needs data",
    "missing",
    "gap",
    "open question",
    "open issue",
}

_DECISION_KEYWORDS = {
    "agreed",
    "decided",
    "confirmed",
    "resolved",
    "approved",
    "accepted",
    "will proceed",
    "shall",
    "must",
    "required",
}

_QUESTION_KEYWORDS = {
    "?",
    "how would",
    "what assumptions",
    "what would it take",
    "how does",
    "what is",
    "whether",
    "if so",
}

_BAND_PATTERN = re.compile(
    r"(\d[\d.]*)\s*[-–]\s*(\d[\d.]*)\s*(MHz|GHz|kHz)",
    re.IGNORECASE,
)

_LINK_BUDGET_PATTERN = re.compile(
    r"link\s*budget|path\s*loss|propagation|free.space|itm|longley.rice|eirp|received\s*power",
    re.IGNORECASE,
)

_ASSUMPTION_PATTERN = re.compile(
    r"\b(assum\w+|estimat\w+|model\w+|predict\w+|calculat\w+|simulat\w+)\b",
    re.IGNORECASE,
)

# Keys whose values must be lists in the output schema (shared by generator and validator)
_LIST_SECTION_KEYS = (
    "key_findings",
    "risks_and_uncertainties",
    "decisions_and_recommendations",
    "open_questions_for_agencies",
)


# ─── Internal helpers ─────────────────────────────────────────────────────────


def _text_from_list(items: List[Any], key: str = "text") -> List[str]:
    """Extract text strings from a list that may contain dicts or plain strings."""
    out: List[str] = []
    for item in items:
        if isinstance(item, str):
            out.append(item)
        elif isinstance(item, dict):
            val = item.get(key) or item.get("description") or item.get("content") or ""
            if val:
                out.append(str(val))
    return out


def _contains_any(text: str, keywords: set) -> bool:
    lower = text.lower()
    return any(kw in lower for kw in keywords)


def _detect_bands(text: str) -> List[str]:
    """Return band-range strings found in text (e.g. '3550–3700 MHz')."""
    bands = []
    for m in _BAND_PATTERN.finditer(text):
        bands.append(f"{m.group(1)}–{m.group(2)} {m.group(3)}")
    return bands


def _build_traceability_entry(claim: str, source: str, confidence: float) -> Dict[str, Any]:
    return {
        "claim": claim,
        "source": source,
        "confidence": round(min(max(confidence, 0.0), 1.0), 2),
    }


def _transcript_text(structured_transcript: Dict[str, Any]) -> str:
    """
    Extract a single string from a structured_transcript dict.

    Supports several common shapes:
        {"text": "..."}
        {"transcript": "..."}
        {"segments": [{"text": "..."}, ...]}
        {"utterances": [{"text": "..."}, ...]}
    """
    if not structured_transcript:
        return ""
    if "text" in structured_transcript:
        return str(structured_transcript["text"])
    if "transcript" in structured_transcript:
        return str(structured_transcript["transcript"])
    segs = structured_transcript.get("segments") or structured_transcript.get("utterances") or []
    return " ".join(_text_from_list(segs))


# ─── Section Generators ───────────────────────────────────────────────────────


def _generate_executive_summary(
    structured_transcript: Dict[str, Any],
    slide_signals: Optional[Dict[str, Any]],
    gap_analysis: Optional[Dict[str, Any]],
    traceability: List[Dict[str, Any]],
) -> str:
    """
    Build a concise executive summary (5–8 sentences).

    Includes:
        - what was studied
        - key tension (sharing vs protection)
        - 1–2 main findings
        - 1 unresolved issue
    """
    lines: List[str] = []
    raw = _transcript_text(structured_transcript)
    meeting_context = structured_transcript.get("meeting_context", "") or structured_transcript.get(
        "context", ""
    )
    title = (
        structured_transcript.get("title")
        or structured_transcript.get("meeting_title")
        or "the subject band"
    )

    # Sentence 1: what was studied
    bands = _detect_bands(raw + " " + meeting_context)
    band_str = " and ".join(bands[:2]) if bands else "the subject band"
    lines.append(
        f"This working paper summarizes technical findings and meeting discussions regarding "
        f"spectrum sharing and protection in {band_str}."
    )

    # Sentence 2: key tension
    sharing_count = raw.lower().count("sharing")
    protection_count = raw.lower().count("protection")
    if sharing_count > 0 or protection_count > 0:
        dominant = "spectrum sharing" if sharing_count >= protection_count else "incumbent protection"
        lines.append(
            f"The central tension in the discussions involves balancing {dominant} with "
            f"the competing operational requirements of federal and non-federal systems."
        )

    # Sentences 3–4: main findings from decisions or strong claims
    decisions = _text_from_list(
        structured_transcript.get("decisions_made") or structured_transcript.get("decisions") or []
    )
    if decisions:
        traceability.append(
            _build_traceability_entry(decisions[0][:120], "transcript", 0.85)
        )
        lines.append(f"A key finding from the meeting is that {decisions[0].rstrip('.')}.")
    if len(decisions) > 1:
        traceability.append(
            _build_traceability_entry(decisions[1][:120], "transcript", 0.80)
        )
        lines.append(
            f"Additionally, the group noted that {decisions[1].rstrip('.')}."
        )

    # Slide-derived finding
    if slide_signals:
        claims = slide_signals.get("claims") or []
        strong_claims = [
            c for c in claims if isinstance(c, dict) and c.get("confidence", 0) >= 0.7
        ]
        if strong_claims:
            claim_text = strong_claims[0].get("text", "")[:120]
            if claim_text:
                traceability.append(_build_traceability_entry(claim_text, "slide", 0.75))
                lines.append(
                    f"Slide materials support the technical conclusion that {claim_text.rstrip('.')}."
                )

    # Unresolved issue
    open_qs = _text_from_list(
        structured_transcript.get("risks_or_open_questions")
        or structured_transcript.get("open_questions")
        or []
    )
    if not open_qs and gap_analysis:
        open_qs = _text_from_list(gap_analysis.get("gaps") or gap_analysis.get("missing_topics") or [])
    if open_qs:
        traceability.append(
            _build_traceability_entry(open_qs[0][:120], "transcript", 0.70)
        )
        lines.append(
            f"One significant unresolved issue remains: {open_qs[0].rstrip('.')}."
        )
    else:
        lines.append(
            "Several technical questions remain open and require agency follow-up before "
            "final conclusions can be drawn."
        )

    # Cap at 8 sentences
    return " ".join(lines[:8])


def _generate_purpose_and_scope(
    structured_transcript: Dict[str, Any],
    slide_signals: Optional[Dict[str, Any]],
) -> str:
    """Build purpose and scope narrative."""
    raw = _transcript_text(structured_transcript)
    meeting_context = structured_transcript.get("meeting_context", "") or ""
    combined = raw + " " + meeting_context

    bands = _detect_bands(combined)
    band_str = ", ".join(bands[:4]) if bands else "the subject spectrum band"

    in_band = _contains_any(combined, {"in-band", "co-channel", "primary band", "primary channel"})
    adjacent = _contains_any(combined, {"adjacent", "adjacent-band", "adjacent channel"})
    focus_str = ""
    if in_band and adjacent:
        focus_str = "The scope encompasses both in-band and adjacent-band interference scenarios."
    elif adjacent:
        focus_str = "The scope is focused primarily on adjacent-band interference scenarios."
    else:
        focus_str = "The scope is focused primarily on in-band interference scenarios."

    slide_scope = ""
    if slide_signals:
        scope_notes = slide_signals.get("scope_notes") or slide_signals.get("purpose") or ""
        if scope_notes:
            slide_scope = f" Slide materials further clarify that {scope_notes}."

    return (
        f"The purpose of this working paper is to document and synthesize the technical analysis, "
        f"key findings, and open questions arising from coordinated engineering discussions on "
        f"spectrum allocation and sharing in {band_str}. "
        f"{focus_str}"
        f"{slide_scope}"
    ).strip()


def _generate_system_description(
    structured_transcript: Dict[str, Any],
    slide_signals: Optional[Dict[str, Any]],
    traceability: List[Dict[str, Any]],
) -> str:
    """Summarize federal and non-federal systems mentioned."""
    raw = _transcript_text(structured_transcript)
    entities = structured_transcript.get("entities") or []

    federal_systems: List[str] = []
    nonfederal_systems: List[str] = []

    federal_keywords = {"p2p", "radar", "federal", "military", "dod", "ntia", "government", "satellite"}
    nonfederal_keywords = {
        "base station",
        "5g",
        "lte",
        "commercial",
        "nr",
        "cbrs",
        "cellular",
        "fcc",
        "unlicensed",
        "licensee",
    }

    for ent in entities:
        name = (
            ent.get("name") or ent.get("text") or ent.get("entity") or ""
        ).lower()
        if _contains_any(name, federal_keywords):
            federal_systems.append(ent.get("name") or name)
        elif _contains_any(name, nonfederal_keywords):
            nonfederal_systems.append(ent.get("name") or name)

    # Fallback: scan raw text for well-known system terms
    if not federal_systems:
        for kw in ["P2P link", "radar system", "federal system", "government system"]:
            if kw.lower() in raw.lower():
                federal_systems.append(kw)
    if not nonfederal_systems:
        for kw in ["base station", "5G NR", "LTE", "CBRS", "commercial system"]:
            if kw.lower() in raw.lower():
                nonfederal_systems.append(kw)

    # Slide entities
    if slide_signals:
        for ent in slide_signals.get("entities") or []:
            name = (ent.get("name") or ent.get("text") or "").lower()
            if _contains_any(name, federal_keywords):
                federal_systems.append(ent.get("name") or name)
            elif _contains_any(name, nonfederal_keywords):
                nonfederal_systems.append(ent.get("name") or name)

    federal_systems = list(dict.fromkeys(federal_systems))[:5]
    nonfederal_systems = list(dict.fromkeys(nonfederal_systems))[:5]

    parts: List[str] = []
    if federal_systems:
        fed_str = ", ".join(federal_systems)
        traceability.append(_build_traceability_entry(f"Federal systems: {fed_str}", "transcript", 0.80))
        parts.append(f"Federal systems discussed include: {fed_str}.")
    else:
        parts.append(
            "Federal systems referenced in the discussions include point-to-point (P2P) "
            "communication links and other licensed incumbents operating in the subject band."
        )

    if nonfederal_systems:
        nf_str = ", ".join(nonfederal_systems)
        traceability.append(
            _build_traceability_entry(f"Non-federal systems: {nf_str}", "transcript", 0.80)
        )
        parts.append(f"Non-federal systems discussed include: {nf_str}.")
    else:
        parts.append(
            "Non-federal systems referenced include base stations and commercial broadband "
            "systems seeking access to the band."
        )

    return " ".join(parts)


def _generate_technical_analysis(
    structured_transcript: Dict[str, Any],
    slide_signals: Optional[Dict[str, Any]],
    traceability: List[Dict[str, Any]],
) -> str:
    """
    Build technical analysis narrative organized into assumptions, methods,
    and limitations.
    """
    raw = _transcript_text(structured_transcript)

    # -- Assumptions
    assumptions = _text_from_list(
        structured_transcript.get("assumptions") or []
    )
    if not assumptions and _ASSUMPTION_PATTERN.search(raw):
        # Extract sentences containing assumption keywords
        for sent in re.split(r"[.!?]", raw):
            sent = sent.strip()
            if sent and _ASSUMPTION_PATTERN.search(sent) and len(sent) > 20:
                assumptions.append(sent)
                if len(assumptions) >= 3:
                    break
    for a in assumptions[:3]:
        traceability.append(_build_traceability_entry(a[:120], "transcript", 0.70))

    # -- Methods
    link_budget_segs: List[str] = []
    for sent in re.split(r"[.!?]", raw):
        sent = sent.strip()
        if sent and _LINK_BUDGET_PATTERN.search(sent) and len(sent) > 15:
            link_budget_segs.append(sent)
    for lb in link_budget_segs[:3]:
        traceability.append(_build_traceability_entry(lb[:120], "transcript", 0.75))

    slide_methods = ""
    if slide_signals:
        methods = slide_signals.get("methods") or slide_signals.get("propagation_models") or []
        if methods:
            slide_methods = (
                " Slide materials reference the following analytical methods: "
                + "; ".join(_text_from_list(methods)[:3])
                + "."
            )
            for m in _text_from_list(methods)[:2]:
                traceability.append(_build_traceability_entry(m[:120], "slide", 0.80))

    # -- Limitations
    limitations: List[str] = []
    for sent in re.split(r"[.!?]", raw):
        sent = sent.strip()
        if sent and _contains_any(sent, _UNCERTAINTY_KEYWORDS) and len(sent) > 15:
            limitations.append(sent)
            if len(limitations) >= 3:
                break

    # Compose narrative
    sections = []
    assump_text = (
        "Assumptions: " + "; ".join(assumptions[:3]) + "."
        if assumptions
        else "Assumptions: Specific deployment parameters and propagation conditions are assumed "
        "to follow standard engineering practice unless otherwise noted."
    )
    sections.append(assump_text)

    methods_text = (
        "Methods: " + "; ".join(link_budget_segs[:2]) + "." + slide_methods
        if link_budget_segs
        else "Methods: The technical analysis draws on link budget calculations, propagation "
        "modeling, and interference scenario evaluation." + slide_methods
    )
    sections.append(methods_text)

    limits_text = (
        "Limitations: " + "; ".join(limitations[:2]) + "."
        if limitations
        else "Limitations: Several modeling assumptions have not yet been validated against "
        "field measurements, and deployment-specific parameters may vary."
    )
    sections.append(limits_text)

    return " ".join(sections)


def _generate_key_findings(
    structured_transcript: Dict[str, Any],
    slide_signals: Optional[Dict[str, Any]],
    traceability: List[Dict[str, Any]],
) -> List[str]:
    """
    Derive atomic bullet findings from decisions and strong claims.
    """
    findings: List[str] = []

    decisions = _text_from_list(
        structured_transcript.get("decisions_made") or structured_transcript.get("decisions") or []
    )
    for d in decisions:
        d = d.strip().rstrip(".")
        if d:
            findings.append(d)
            traceability.append(_build_traceability_entry(d[:120], "transcript", 0.85))

    # Strong claims from transcript
    raw = _transcript_text(structured_transcript)
    for sent in re.split(r"[.!?]", raw):
        sent = sent.strip()
        if (
            len(sent) > 20
            and _contains_any(sent, _INTERFERENCE_KEYWORDS | _PROTECTION_KEYWORDS)
            and not _contains_any(sent, _UNCERTAINTY_KEYWORDS)
        ):
            findings.append(sent)
            traceability.append(_build_traceability_entry(sent[:120], "transcript", 0.70))
            if len(findings) >= 10:
                break

    # Slide-derived claims
    if slide_signals:
        for claim in slide_signals.get("claims") or []:
            text = (
                claim.get("text") or claim.get("content") or ""
                if isinstance(claim, dict)
                else str(claim)
            ).strip().rstrip(".")
            if text:
                findings.append(text)
                traceability.append(_build_traceability_entry(text[:120], "slide", 0.80))
            if len(findings) >= 15:
                break

    # Deduplicate while preserving order
    seen_keys: set = set()
    unique: List[str] = []
    for f in findings:
        key = f.lower()[:80]
        if key not in seen_keys:
            seen_keys.add(key)
            unique.append(f)

    return unique[:10] if unique else [
        "No explicit decisions were recorded; findings will be updated as analysis matures."
    ]


def _generate_risks_and_uncertainties(
    structured_transcript: Dict[str, Any],
    gap_analysis: Optional[Dict[str, Any]],
    traceability: List[Dict[str, Any]],
) -> List[str]:
    """Compile risks from transcript and gap analysis."""
    risks: List[str] = []

    raw_risks = _text_from_list(
        structured_transcript.get("risks_or_open_questions")
        or structured_transcript.get("risks")
        or structured_transcript.get("open_questions")
        or []
    )
    for r in raw_risks:
        r = r.strip()
        if r:
            risks.append(r)
            traceability.append(_build_traceability_entry(r[:120], "transcript", 0.75))

    if gap_analysis:
        for item in (
            gap_analysis.get("gaps") or gap_analysis.get("missing_topics") or []
        ):
            text = (
                item.get("description") or item.get("text") or str(item)
                if isinstance(item, dict)
                else str(item)
            ).strip()
            if text:
                risks.append(f"[Gap] {text}")
                traceability.append(_build_traceability_entry(text[:120], "gap_analysis", 0.65))

    # Add structured risk categories if nothing found
    if not risks:
        risks = [
            "Model uncertainty: propagation and interference models may not capture all deployment scenarios.",
            "Deployment assumptions: actual antenna heights, densities, and patterns may differ from modeled values.",
            "Coordination challenges: multi-agency coordination timelines and requirements are not yet established.",
        ]

    return list(dict.fromkeys(risks))[:15]


def _generate_decisions_and_recommendations(
    structured_transcript: Dict[str, Any],
    traceability: List[Dict[str, Any]],
) -> List[str]:
    """Normalize decisions_made into recommendations and add implied ones."""
    recs: List[str] = []

    decisions = _text_from_list(
        structured_transcript.get("decisions_made") or structured_transcript.get("decisions") or []
    )
    for d in decisions:
        d = d.strip().rstrip(".")
        if d:
            recs.append(d)
            traceability.append(_build_traceability_entry(d[:120], "transcript", 0.85))

    action_items = _text_from_list(
        structured_transcript.get("action_items") or []
    )
    for ai in action_items:
        ai = ai.strip().rstrip(".")
        if ai and ai not in recs:
            recs.append(ai)
            traceability.append(_build_traceability_entry(ai[:120], "transcript", 0.80))

    # Add implied recommendations if none found
    if not recs:
        recs = [
            "Conduct validated interference simulations using site-specific propagation data.",
            "Establish inter-agency coordination procedures for the subject band.",
            "Document and review all modeling assumptions with agency stakeholders.",
        ]

    return recs[:12]


def _generate_gap_augmented_sections(
    gap_analysis: Optional[Dict[str, Any]],
) -> Dict[str, List[str]]:
    """
    Return additional subsection content driven by gap analysis.

    Returns a dict with keys:
        "unaddressed_deployment_assumptions"
        "unvalidated_interference_scenarios"
        "slide_vs_discussion_conflicts"
    """
    out: Dict[str, List[str]] = {
        "unaddressed_deployment_assumptions": [],
        "unvalidated_interference_scenarios": [],
        "slide_vs_discussion_conflicts": [],
    }
    if not gap_analysis:
        return out

    for item in gap_analysis.get("deployment_gaps") or gap_analysis.get("gaps") or []:
        text = (
            item.get("description") or item.get("text") or str(item)
            if isinstance(item, dict)
            else str(item)
        ).strip()
        if text:
            out["unaddressed_deployment_assumptions"].append(text)

    for item in gap_analysis.get("interference_gaps") or []:
        text = (
            item.get("description") or item.get("text") or str(item)
            if isinstance(item, dict)
            else str(item)
        ).strip()
        if text:
            out["unvalidated_interference_scenarios"].append(text)

    for item in gap_analysis.get("conflicts") or gap_analysis.get("slide_conflicts") or []:
        text = (
            item.get("description") or item.get("text") or str(item)
            if isinstance(item, dict)
            else str(item)
        ).strip()
        if text:
            out["slide_vs_discussion_conflicts"].append(text)

    return out


def _build_slide_alignment_summary(
    slide_signals: Optional[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Build slide alignment entries for the appendix."""
    if not slide_signals:
        return []
    alignment: List[Dict[str, Any]] = []
    for claim in (slide_signals.get("claims") or [])[:10]:
        if isinstance(claim, dict):
            alignment.append(
                {
                    "slide_claim": claim.get("text") or claim.get("content") or "",
                    "section": claim.get("section") or "unassigned",
                    "confidence": claim.get("confidence", 0.5),
                }
            )
    return alignment


# ─── Agency Question Generation ───────────────────────────────────────────────


def generate_agency_questions(
    working_paper: Dict[str, Any],
    gap_analysis: Optional[Dict[str, Any]] = None,
) -> List[str]:
    """
    Generate calibrated, open-ended questions for agency follow-up.

    Applies Chris Voss-style calibrated question framing but remains
    fully deterministic:
        "How would [agency] validate X?"
        "What assumptions support Y?"
        "What would it take to ensure Z does not cause interference?"

    Categories:
        - validation
        - missing data
        - conflicting claims
        - implementation feasibility

    Returns at least 5 questions and up to 15.
    """
    questions: List[str] = []

    # -- Validation questions from key findings
    for finding in (working_paper.get("key_findings") or [])[:3]:
        q = f"How would the relevant agencies validate the following finding: '{finding[:100]}'?"
        questions.append(q)

    # -- Questions from risks and uncertainties
    for risk in (working_paper.get("risks_and_uncertainties") or [])[:3]:
        risk_clean = risk.strip().lstrip("[Gap] ")
        q = f"What assumptions support the risk assessment that: '{risk_clean[:100]}'?"
        questions.append(q)

    # -- Questions from open decisions/recommendations
    for rec in (working_paper.get("decisions_and_recommendations") or [])[:2]:
        q = (
            f"What would it take to implement the following recommendation without causing "
            f"interference to incumbent systems: '{rec[:100]}'?"
        )
        questions.append(q)

    # -- Gap-driven questions
    if gap_analysis:
        gaps = _text_from_list(
            gap_analysis.get("gaps") or gap_analysis.get("missing_topics") or []
        )
        for gap in gaps[:4]:
            q = f"What additional data or analysis is needed to address the gap: '{gap[:100]}'?"
            questions.append(q)

        conflicts = _text_from_list(gap_analysis.get("conflicts") or [])
        for conflict in conflicts[:2]:
            q = (
                f"How should agencies reconcile the conflicting claims regarding: "
                f"'{conflict[:100]}'?"
            )
            questions.append(q)

    # -- Ensure minimum 5 questions with fallbacks
    fallback_questions = [
        "How would NTIA validate that the proposed interference threshold is appropriate for all incumbent federal systems?",
        "What field measurement campaign would best characterize the propagation environment in this band?",
        "What deployment assumptions for commercial base stations have been independently validated?",
        "How should coordination zones be updated if actual antenna densities exceed modeled values?",
        "What would it take to ensure that aggregate interference from multiple commercial deployments does not degrade federal system performance?",
        "How does the proposed protection criterion account for cumulative interference from multiple non-federal sources?",
        "What implementation timeline is feasible for inter-agency coordination requirements?",
    ]
    for fb in fallback_questions:
        if len(questions) >= 10:
            break
        if not any(fb[:40].lower() in q.lower() for q in questions):
            questions.append(fb)

    # Deduplicate and cap
    seen_keys: set = set()
    unique: List[str] = []
    for q in questions:
        key = q.lower()[:60]
        if key not in seen_keys:
            seen_keys.add(key)
            unique.append(q)

    return unique[:15]


# ─── Core Generation Function ─────────────────────────────────────────────────


def generate_working_paper(
    structured_transcript: Dict[str, Any],
    slide_signals: Optional[Dict[str, Any]] = None,
    gap_analysis: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Generate a structured, report-ready working paper from meeting inputs.

    Parameters
    ----------
    structured_transcript:
        Structured extraction from a meeting transcript.  Recognised keys:
            text / transcript / segments / utterances — raw text
            meeting_title / title — meeting or paper title
            meeting_context / context — background context
            decisions_made / decisions — resolved decisions
            action_items — assigned tasks
            risks_or_open_questions / risks / open_questions — risks
            assumptions — explicit assumptions
            entities — named entities (systems, organizations)
    slide_signals:
        Optional slide intelligence packet produced by
        ``slide_intelligence.build_slide_intelligence_packet``.
        Adds slide-derived claims, methods, and entities.
    gap_analysis:
        Optional gap analysis document.  Recognised keys:
            gaps / missing_topics — general gaps
            deployment_gaps — unaddressed deployment assumptions
            interference_gaps — unvalidated interference scenarios
            conflicts / slide_conflicts — slide vs. discussion conflicts

    Returns
    -------
    dict
        A working paper dict conforming to the working_paper output schema.
        All top-level keys and appendix keys are always present.
    """
    traceability: List[Dict[str, Any]] = []

    title = (
        structured_transcript.get("title")
        or structured_transcript.get("meeting_title")
        or "Working Paper: Spectrum Sharing and Interference Analysis"
    )

    executive_summary = _generate_executive_summary(
        structured_transcript, slide_signals, gap_analysis, traceability
    )
    purpose_and_scope = _generate_purpose_and_scope(structured_transcript, slide_signals)
    system_description = _generate_system_description(
        structured_transcript, slide_signals, traceability
    )
    technical_analysis = _generate_technical_analysis(
        structured_transcript, slide_signals, traceability
    )
    key_findings = _generate_key_findings(
        structured_transcript, slide_signals, traceability
    )
    risks_and_uncertainties = _generate_risks_and_uncertainties(
        structured_transcript, gap_analysis, traceability
    )
    decisions_and_recommendations = _generate_decisions_and_recommendations(
        structured_transcript, traceability
    )

    gap_sections = _generate_gap_augmented_sections(gap_analysis)

    # Inject gap subsections into technical_analysis narrative when present
    aug_parts: List[str] = []
    if gap_sections["unaddressed_deployment_assumptions"]:
        aug_parts.append(
            "Unaddressed Deployment Assumptions: "
            + "; ".join(gap_sections["unaddressed_deployment_assumptions"][:3])
            + "."
        )
    if gap_sections["unvalidated_interference_scenarios"]:
        aug_parts.append(
            "Unvalidated Interference Scenarios: "
            + "; ".join(gap_sections["unvalidated_interference_scenarios"][:3])
            + "."
        )
    if aug_parts:
        technical_analysis = technical_analysis + " " + " ".join(aug_parts)

    # Build preliminary working paper for question generation
    working_paper: Dict[str, Any] = {
        "title": title,
        "executive_summary": executive_summary,
        "purpose_and_scope": purpose_and_scope,
        "system_description": system_description,
        "technical_analysis": technical_analysis,
        "key_findings": key_findings,
        "risks_and_uncertainties": risks_and_uncertainties,
        "decisions_and_recommendations": decisions_and_recommendations,
        "open_questions_for_agencies": [],
        "appendix": {
            "source_traceability": traceability,
            "slide_alignment_summary": _build_slide_alignment_summary(slide_signals),
            "discussion_gaps": gap_sections["slide_vs_discussion_conflicts"],
        },
    }

    # Attach agency questions
    working_paper["open_questions_for_agencies"] = generate_agency_questions(
        working_paper, gap_analysis
    )

    return working_paper


# ─── Schema Validation ────────────────────────────────────────────────────────

_REQUIRED_KEYS = {
    "title",
    "executive_summary",
    "purpose_and_scope",
    "system_description",
    "technical_analysis",
    "key_findings",
    "risks_and_uncertainties",
    "decisions_and_recommendations",
    "open_questions_for_agencies",
    "appendix",
}

_REQUIRED_APPENDIX_KEYS = {
    "source_traceability",
    "slide_alignment_summary",
    "discussion_gaps",
}


def validate_working_paper(working_paper: Dict[str, Any]) -> List[str]:
    """
    Validate a working paper dict against the output schema.

    Returns a list of error messages (empty list means valid).
    """
    errors: List[str] = []

    missing_top = _REQUIRED_KEYS - set(working_paper.keys())
    if missing_top:
        errors.append(f"Missing required top-level keys: {sorted(missing_top)}")

    for key in ("title", "executive_summary", "purpose_and_scope", "system_description", "technical_analysis"):
        if key in working_paper and not working_paper[key]:
            errors.append(f"Required section '{key}' is empty")

    for key in _LIST_SECTION_KEYS:
        if key in working_paper and not isinstance(working_paper.get(key), list):
            errors.append(f"'{key}' must be a list")

    appendix = working_paper.get("appendix")
    if appendix is not None:
        if not isinstance(appendix, dict):
            errors.append("'appendix' must be a dict")
        else:
            missing_app = _REQUIRED_APPENDIX_KEYS - set(appendix.keys())
            if missing_app:
                errors.append(f"Missing appendix keys: {sorted(missing_app)}")
    else:
        errors.append("Missing 'appendix' section")

    return errors
