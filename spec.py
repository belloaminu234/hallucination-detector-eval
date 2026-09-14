"""The ground truth this whole tool checks agent output against: a set
of real API endpoints (method + path template + valid parameter names)
and, optionally, a registry of known-valid ID strings.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field


@dataclass(frozen=True)
class EndpointSpec:
    method: str          # "GET", "POST", etc.
    path_template: str   # e.g. "/users/{id}/orders/{order_id}"
    parameters: frozenset[str] = field(default_factory=frozenset)

    def __post_init__(self) -> None:
        object.__setattr__(self, "method", self.method.upper())


@dataclass(frozen=True)
class ApiSpec:
    endpoints: tuple[EndpointSpec, ...]
    valid_ids: frozenset[str] = field(default_factory=frozenset)

    def all_parameters(self) -> frozenset[str]:
        """The full parameter vocabulary across every endpoint -- used
        to flag a parameter name that isn't valid ANYWHERE in the API,
        which is a stronger and more reliable signal of a made-up
        parameter than trying to associate every call with exactly one
        endpoint (see README for why that association is left global)."""
        result: set[str] = set()
        for ep in self.endpoints:
            result.update(ep.parameters)
        return frozenset(result)


_TEMPLATE_VAR_RE = re.compile(r"\{[^{}]+\}")


def _template_to_regex(template: str) -> re.Pattern[str]:
    """Converts "/users/{id}/orders/{order_id}" into a regex that
    matches any concrete path with the same shape, e.g. "/users/42/orders/7"."""
    # Escape the literal parts, then substitute a wildcard for each {var}.
    parts = _TEMPLATE_VAR_RE.split(template)
    escaped_parts = [re.escape(p) for p in parts]
    pattern = "[^/]+".join(escaped_parts)
    return re.compile(f"^{pattern}$")


def path_matches_template(path: str, template: str) -> bool:
    path = path.rstrip("/") or "/"
    template = template.rstrip("/") or "/"
    return bool(_template_to_regex(template).match(path))


def find_matching_endpoint(
    method: str, path: str, spec: ApiSpec
) -> EndpointSpec | None:
    method = method.upper()
    for ep in spec.endpoints:
        if ep.method == method and path_matches_template(path, ep.path_template):
            return ep
    return None


def load_spec(json_text: str) -> ApiSpec:
    data = json.loads(json_text)
    endpoints = tuple(
        EndpointSpec(
            method=e["method"],
            path_template=e["path"],
            parameters=frozenset(e.get("parameters", [])),
        )
        for e in data.get("endpoints", [])
    )
    valid_ids = frozenset(data.get("valid_ids", []))
    return ApiSpec(endpoints=endpoints, valid_ids=valid_ids)
