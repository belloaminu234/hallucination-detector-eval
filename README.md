# hallucination-detector-eval

A specialized evaluator that scans agent output (code, API calls, prose) for references to API endpoints, parameters, and ID strings, and flags any that don't actually exist in a supplied ground-truth API spec — a common and hard-to-catch failure mode where an LLM confidently invents a plausible-looking `/v2/users/{id}/deactivate` endpoint, a `discount_code` parameter, or an object ID that was never returned by anything. Built entirely on the Python standard library.

## What it does

Given:
- an **API spec** (JSON: real endpoints with their methods, path templates, and valid parameter names; optionally, a registry of known-valid object IDs), and
- **agent output** (code, API calls, or prose that references the API),

it extracts every claim the output makes about the API surface and checks each one:

- **Endpoint claims** — `requests.get("https://api.example.com/users/42")` or a prose mention like `GET /users/{id}` — matched against the spec's path templates (`/users/{id}` correctly matches a concrete path like `/users/42`).
- **Parameter claims** — keyword arguments in API calls, including digging *inside* `params={...}`/`json={...}` dict literals rather than treating `params` itself as a parameter.
- **ID claims** — token-shaped object identifiers (`usr_abc123`, `ord_9f8e7d`) checked against a known-ID registry, when one is supplied.

Anything that doesn't match gets a `difflib`-powered "did you mean...?" suggestion where a close match exists, so the output is actionable, not just a bare "not found."

## Usage

```bash
python -m halluceval.cli --spec api_spec.json --output agent_output.py
```

Exits non-zero if any hallucination is found — set a looser bar with `--max-hallucination-rate`:

```bash
python -m halluceval.cli --spec api_spec.json --output agent_output.py --max-hallucination-rate 0.1
```

This makes it usable as a CI gate on agent-generated code before it ships.

`api_spec.json`:
```json
{
  "endpoints": [
    {"method": "GET", "path": "/users/{id}", "parameters": ["include_deleted"]},
    {"method": "POST", "path": "/orders", "parameters": ["customer_id", "amount", "currency"]}
  ],
  "valid_ids": ["usr_abc123", "cus_9f8e7d"]
}
```

Example output:

```
=== Hallucination Detector Report ===
Overall: 2/10 claims hallucinated (20.0%)
  endpoint   1/3 hallucinated (33.3%)
  parameter  1/5 hallucinated (20.0%)
  id         0/2 hallucinated (0.0%)

=== Hallucinated Claims ===
  line 5: [parameter] 'discount_code' -- not a parameter defined anywhere in the spec
  line 8: [endpoint] 'DELETE /users/usr_totallymadeup' -- no DELETE endpoint matches this path
```

## Design notes

**Parameters are checked against the full spec vocabulary, not one specific endpoint.** Reliably associating an arbitrary function call in free-form text with exactly one REST endpoint is a much harder (and much more fragile) problem than the rest of this tool. Checking each parameter name against the union of every valid parameter across the whole API is a deliberate scope decision: it still reliably catches a genuinely made-up parameter name, at the cost of not catching "real parameter, wrong endpoint" mistakes.

**The ID pattern requires a digit in the suffix.** An early version matched any `prefix_suffix`-shaped token, which produced false positives on completely ordinary snake_case words like `include_deleted` (a real parameter name, not an ID). Requiring a digit somewhere in the suffix is what separates "generated-looking identifier" from "English compound word" — see `test_extract.py` for the regression tests this bug produced.

**`requests`'s own keyword arguments (`params`, `json`, `headers`, `timeout`, etc.) are never treated as domain parameters.** An earlier version extracted `params` itself as a "parameter claim" from `requests.get(..., params={...})`, which is wrong — `params` is the HTTP library's own kwarg name, not a field of the API being called. The fix looks *inside* `params=`/`json=` dict literals for the actual domain field names instead.

## Architecture

```
src/halluceval/
  spec.py         ApiSpec, EndpointSpec, path-template matching, JSON loading
  extract.py       regex-based claim extraction (endpoints, parameters, IDs)
  evaluate.py        cross-references claims against the spec, produces Findings
  score.py             rolls Findings up into overall + per-type hallucination rates
  report.py              plain-text report rendering
  cli.py                   argument parsing, CI-gate exit code, the command-line entry point
```

## Testing

```bash
python -m unittest discover tests -v
```

47 tests, covering:

- **`test_spec.py`** — path-template matching, including the "variable doesn't cross a `/` boundary" edge case.
- **`test_extract.py`** — claim extraction, including regression tests for two real false-positive bugs caught during manual testing (see "Design notes" above): the `include_deleted`-as-ID false positive, and the `params`-as-domain-parameter false positive.
- **`test_evaluate.py`** — valid/hallucinated classification, typo-suggestion generation, and the "no ID registry supplied → ID claims aren't scored at all" behavior (deliberately not silently marked "valid").
- **`test_score.py`** — hallucination-rate math, including zero-claims and zero-of-a-given-type edge cases that could otherwise divide by zero.
- **`test_cli.py`** — the real CLI entry point end-to-end against actual spec/output files on disk, including the `--max-hallucination-rate` CI-gate behavior and exit codes.

Also manually smoke-tested against realistic agent-output snippets (see the example above) — correctly caught a made-up parameter and a made-up endpoint while leaving every real reference unflagged, and separately confirmed ID-hallucination detection fires correctly on a digit-containing fake ID.

## Limitations

- Regex-based static extraction, not a real parser — favors precision over recall by design. Unusual formatting, multi-line calls, or nested parentheses may cause a claim to be missed entirely rather than mis-extracted.
- Parameter validity is checked against the whole API's vocabulary, not per-endpoint (see "Design notes").
- The ID pattern is tuned for the common `prefix_alphanumericwithdigits` shape (Stripe/Linear-style). Purely numeric IDs, UUIDs, or a different house style would need a different pattern.
- No understanding of variables/data flow — `path = "/users/" + user_id; requests.get(path)` won't be recognized as an endpoint claim, since the literal path isn't in the call itself.

## License

MIT — see [LICENSE](LICENSE).
