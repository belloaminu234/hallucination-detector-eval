"""CLI: python -m halluceval.cli --spec api_spec.json --output agent_output.txt
[--max-hallucination-rate 0.0]

Exits non-zero if the hallucination rate exceeds --max-hallucination-rate
(default 0.0, i.e. any hallucination at all fails) -- intended for use as
a CI gate on agent-generated code/output.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from halluceval.evaluate import evaluate
from halluceval.extract import extract_claims
from halluceval.report import render_report
from halluceval.score import compute_score
from halluceval.spec import load_spec


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Detect hallucinated API endpoints/parameters/IDs in agent output."
    )
    parser.add_argument("--spec", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--max-hallucination-rate", type=float, default=0.0)
    args = parser.parse_args(argv)

    if not args.spec.exists():
        print(f"error: {args.spec} does not exist", file=sys.stderr)
        return 1
    if not args.output.exists():
        print(f"error: {args.output} does not exist", file=sys.stderr)
        return 1

    spec = load_spec(args.spec.read_text())
    claims = extract_claims(args.output.read_text())
    findings = evaluate(claims, spec)
    score = compute_score(findings)

    print(render_report(findings, score), end="")

    if score.hallucination_rate > args.max_hallucination_rate:
        print(
            f"\nFAILED: hallucination rate {score.hallucination_rate:.1%} exceeds "
            f"threshold {args.max_hallucination_rate:.1%}",
            file=sys.stderr,
        )
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
