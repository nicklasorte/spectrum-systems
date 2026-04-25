from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BaselineHarness:
    """Deterministic transcript -> FAQ projection harness."""

    candidate_id: str = "hop-baseline-v1"

    def run(self, transcript: str) -> dict:
        text = (transcript or "").strip()
        if not text:
            raise ValueError("transcript must be non-empty")

        fragments = [frag.strip() for frag in text.replace("\n", " ").split("?") if frag.strip()]
        faq_items = []
        for index, fragment in enumerate(fragments, start=1):
            question = fragment
            answer = ""
            if "A:" in fragment:
                left, right = fragment.split("A:", 1)
                question = left.replace("Q:", "").strip()
                answer = right.strip().rstrip(".")
            question = question.rstrip(":").strip()
            faq_items.append(
                {
                    "id": f"faq-{index:03d}",
                    "question": question if question.endswith("?") else f"{question}?",
                    "answer": answer or "No explicit answer provided.",
                }
            )

        return {
            "artifact_type": "faq_cluster_artifact",
            "faq_items": faq_items,
            "faq_count": len(faq_items),
        }
