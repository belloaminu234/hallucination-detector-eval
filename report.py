"""Renders a plain-text report from a list of Findings and their Score."""

from __future__ import annotations

from halluceval.evaluate import Finding
from halluceval.score import Score


def render_report(findings: list[Finding], score: Score) -> str:
    lines = []
    lines.append("=== Hallucination Detector Report ===")
    lines.append(
        f"Overall: {score.hallucinated_claims}/{score.total_claims} claims hallucinated "
        f"({score.hallucination_rate:.1%})"
    )
    for claim_type, sub in score.by_type.items():
        if sub.total_claims == 0:
            continue
        lines.append(
            f"  {claim_type:<10} {sub.hallucinated_claims}/{sub.total_claims} "
            f"hallucinated ({sub.hallucination_rate:.1%})"
        )

    hallucinated = [f for f in findings if f.status == "hallucinated"]
    if hallucinated:
        lines.append("")
        lines.append("=== Hallucinated Claims ===")
        for f in sorted(hallucinated, key=lambda f: (f.line_no, f.claim_type)):
            lines.append(f"  line {f.line_no}: [{f.claim_type}] {f.value!r} -- {f.detail}")
    else:
        lines.append("")
        lines.append("No hallucinations detected.")

    return "\n".join(lines) + "\n"
