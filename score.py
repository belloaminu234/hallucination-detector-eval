"""Rolls up a list of Findings into summary scores -- overall and
per-claim-type hallucination rates."""

from __future__ import annotations

from dataclasses import dataclass

from halluceval.evaluate import Finding


@dataclass(frozen=True)
class Score:
    total_claims: int
    hallucinated_claims: int
    hallucination_rate: float  # 0.0 (no hallucinations) to 1.0 (all hallucinated)
    by_type: dict[str, "Score"]


def _score_for(findings: list[Finding]) -> tuple[int, int, float]:
    total = len(findings)
    hallucinated = sum(1 for f in findings if f.status == "hallucinated")
    rate = (hallucinated / total) if total > 0 else 0.0
    return total, hallucinated, rate


def compute_score(findings: list[Finding]) -> Score:
    total, hallucinated, rate = _score_for(findings)

    by_type: dict[str, Score] = {}
    for claim_type in ("endpoint", "parameter", "id"):
        subset = [f for f in findings if f.claim_type == claim_type]
        sub_total, sub_hallucinated, sub_rate = _score_for(subset)
        by_type[claim_type] = Score(sub_total, sub_hallucinated, sub_rate, by_type={})

    return Score(total, hallucinated, rate, by_type)
