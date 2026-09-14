"""Scans free-form agent output (code, API calls, prose/comments) for
things that look like claims about the API surface: "this endpoint
exists", "this parameter exists", "this ID exists". Heuristic and
regex-based by design -- this is static text analysis, not a code
interpreter, so it deliberately favors precision over recall: a call
with nested parentheses or unusual formatting might be missed entirely
rather than mis-parsed into a false claim. See README for the exact
patterns recognized and their known limits.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# "GET /users/{id}" or "GET /users/42" mentioned directly, e.g. in a
# comment, docstring, or log line.
_PROSE_ENDPOINT_RE = re.compile(
    r"\b(GET|POST|PUT|PATCH|DELETE)\s+(/[\w\-{}/.]*)"
)

# requests.get("https://api.example.com/users/42", params={...}, ...)
# Captures the method, the literal URL/path string, and everything else
# passed to the call (so we can dig into params=/json= separately).
_REQUESTS_CALL_RE = re.compile(
    r"requests\.(get|post|put|patch|delete)\(\s*[\"']([^\"']+)[\"']"
    r"(?P<rest>[^)]*)\)",
    re.IGNORECASE,
)

# A generic client-style call: client.users.get(id="usr_123", ...) or
# api.orders.create(customer_id="cus_1", amount=500). We don't try to
# resolve these to one specific endpoint (see spec.py's
# all_parameters() for why); we just harvest the keyword arguments as
# parameter claims.
_CLIENT_CALL_RE = re.compile(r"\b([\w.]+)\(\s*(?P<args>[^)]*)\)")

_KWARG_RE = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*=")

# Dict-literal keys, e.g. {"include_deleted": True, 'limit': 10} --
# used to look *inside* a requests params=/json= dict rather than
# treating "params" itself as a domain-level API parameter.
_DICT_KEY_RE = re.compile(r"[\"']([A-Za-z_][A-Za-z0-9_]*)[\"']\s*:")

# Keyword arguments belonging to the requests library itself, not the
# domain API being called -- never treated as API parameter claims.
_HTTP_LIBRARY_KWARGS = {
    "params", "json", "headers", "timeout", "auth", "verify", "data",
    "cookies", "allow_redirects", "stream", "proxies", "files", "cert",
}

# ID-like tokens: a short prefix, underscore, then an alphanumeric body
# -- the common "usr_abc123" / "ord_9f8e7d" shape used by Stripe-,
# Linear-, and similar APIs' object identifiers. Requiring a digit
# somewhere in the suffix is what keeps this from matching ordinary
# snake_case words like "include_deleted" or "customer_id" (see
# test_extract.py for the case that motivated this).
_ID_TOKEN_RE = re.compile(r"\b[a-z]{2,8}_(?=[A-Za-z0-9]*\d)[A-Za-z0-9]{4,}\b")


@dataclass(frozen=True)
class EndpointClaim:
    line_no: int
    method: str
    path: str
    raw: str


@dataclass(frozen=True)
class ParameterClaim:
    line_no: int
    name: str
    raw: str


@dataclass(frozen=True)
class IdClaim:
    line_no: int
    value: str
    raw: str


def _strip_url_to_path(url: str) -> str:
    """Turns "https://api.example.com/users/42" into "/users/42"; leaves
    an already-relative path like "/users/42" alone."""
    match = re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://[^/]+(/.*)?$", url)
    if match:
        return match.group(1) or "/"
    return url


def extract_endpoint_claims(text: str) -> list[EndpointClaim]:
    claims: list[EndpointClaim] = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        requests_spans: list[tuple[int, int]] = []
        for match in _REQUESTS_CALL_RE.finditer(line):
            method = match.group(1).upper()
            path = _strip_url_to_path(match.group(2))
            claims.append(EndpointClaim(line_no, method, path, match.group(0)))
            requests_spans.append(match.span())

        for match in _PROSE_ENDPOINT_RE.finditer(line):
            # Skip a prose-shaped match that's actually inside a
            # requests.* call already captured above (the method name
            # embedded in "requests.get(" can otherwise look like a
            # second, spurious prose mention).
            if any(start <= match.start() < end for start, end in requests_spans):
                continue
            method, path = match.group(1), match.group(2)
            claims.append(EndpointClaim(line_no, method.upper(), path, match.group(0)))

    return claims


def extract_parameter_claims(text: str) -> list[ParameterClaim]:
    claims: list[ParameterClaim] = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        requests_spans: list[tuple[int, int]] = []

        # requests.* calls: look inside params=/json= dict literals for
        # the actual domain parameter names, rather than treating the
        # wrapper kwarg ("params", "json") as a domain parameter itself.
        for match in _REQUESTS_CALL_RE.finditer(line):
            requests_spans.append(match.span())
            rest = match.group("rest")
            for dict_match in re.finditer(r"(params|json)\s*=\s*\{([^}]*)\}", rest):
                for key_match in _DICT_KEY_RE.finditer(dict_match.group(2)):
                    claims.append(ParameterClaim(line_no, key_match.group(1), match.group(0)))

        # Generic client-style calls: every top-level kwarg is treated
        # as a domain parameter claim, except calls already handled
        # above (requests.*) and library-level kwarg names.
        for call_match in _CLIENT_CALL_RE.finditer(line):
            if any(start <= call_match.start() < end for start, end in requests_spans):
                continue
            args = call_match.group("args")
            for kwarg_match in _KWARG_RE.finditer(args):
                name = kwarg_match.group(1)
                if name in _HTTP_LIBRARY_KWARGS:
                    continue
                claims.append(ParameterClaim(line_no, name, call_match.group(0)))

    return claims


def extract_id_claims(text: str) -> list[IdClaim]:
    claims: list[IdClaim] = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        for match in _ID_TOKEN_RE.finditer(line):
            claims.append(IdClaim(line_no, match.group(0), match.group(0)))
    return claims


@dataclass(frozen=True)
class ExtractedClaims:
    endpoints: list[EndpointClaim]
    parameters: list[ParameterClaim]
    ids: list[IdClaim]


def extract_claims(text: str) -> ExtractedClaims:
    return ExtractedClaims(
        endpoints=extract_endpoint_claims(text),
        parameters=extract_parameter_claims(text),
        ids=extract_id_claims(text),
    )
