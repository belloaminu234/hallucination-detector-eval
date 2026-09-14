"""Cross-references extracted claims against the ground-truth ApiSpec
and produces a Finding per claim: valid, or hallucinated with a reason
and (where possible) a "did you mean" suggestion using difflib, since
"you typed /user/{id} but it's /users/{id}" is a lot more actionable
than just "not found".
"""

from __future__ import annotations

import difflib
from dataclasses import dataclass
from typing import Literal

from halluceval.extract import EndpointClaim, ExtractedClaims, IdClaim, ParameterClaim
from halluceval.spec import ApiSpec, find_matching_endpoint

Status = Literal["valid", "hallucinated"]


@dataclass(frozen=True)
class Finding:
    claim_type: Literal["endpoint", "parameter", "id"]
    line_no: int
    value: str
    status: Status
    detail: str


def _suggest(value: str, candidates: list[str]) -> str | None:
    matches = difflib.get_close_matches(value, candidates, n=1, cutoff=0.6)
    return matches[0] if matches else None


def evaluate_endpoint(claim: EndpointClaim, spec: ApiSpec) -> Finding:
    match = find_matching_endpoint(claim.method, claim.path, spec)
    value = f"{claim.method} {claim.path}"
    if match is not None:
        return Finding("endpoint", claim.line_no, value, "valid", "matches a known endpoint")

    same_method_paths = [ep.path_template for ep in spec.endpoints if ep.method == claim.method]
    suggestion = _suggest(claim.path, same_method_paths)
    detail = (
        f"no {claim.method} endpoint matches this path"
        + (f"; did you mean {claim.method} {suggestion}?" if suggestion else "")
    )
    return Finding("endpoint", claim.line_no, value, "hallucinated", detail)


def evaluate_parameter(claim: ParameterClaim, spec: ApiSpec) -> Finding:
    known = spec.all_parameters()
    if claim.name in known:
        return Finding(
            "parameter", claim.line_no, claim.name, "valid",
            "matches a parameter defined somewhere in the spec",
        )

    suggestion = _suggest(claim.name, sorted(known))
    detail = "not a parameter defined anywhere in the spec" + (
        f"; did you mean {suggestion!r}?" if suggestion else ""
    )
    return Finding("parameter", claim.line_no, claim.name, "hallucinated", detail)


def evaluate_id(claim: IdClaim, spec: ApiSpec) -> Finding:
    if not spec.valid_ids:
        # No ID registry supplied -- we have nothing to check IDs
        # against, so we don't claim to have verified anything. This is
        # deliberately NOT reported as a Finding at all (see evaluate())
        # rather than silently marked "valid", which would overstate
        # what was actually checked.
        raise ValueError("evaluate_id called with no valid_ids in spec; caller should skip")

    if claim.value in spec.valid_ids:
        return Finding("id", claim.line_no, claim.value, "valid", "matches a known ID")

    suggestion = _suggest(claim.value, sorted(spec.valid_ids))
    detail = "not a known ID" + (f"; did you mean {suggestion!r}?" if suggestion else "")
    return Finding("id", claim.line_no, claim.value, "hallucinated", detail)


def evaluate(claims: ExtractedClaims, spec: ApiSpec) -> list[Finding]:
    findings: list[Finding] = [evaluate_endpoint(c, spec) for c in claims.endpoints]
    findings.extend(evaluate_parameter(c, spec) for c in claims.parameters)

    if spec.valid_ids:
        findings.extend(evaluate_id(c, spec) for c in claims.ids)
    # If no valid_ids registry was supplied, ID claims are extracted (and
    # can still be inspected by a caller who wants the raw list) but are
    # not scored -- there's nothing to check them against.

    return findings
