import unittest

from halluceval.evaluate import evaluate, evaluate_endpoint, evaluate_id, evaluate_parameter
from halluceval.extract import EndpointClaim, IdClaim, ParameterClaim, extract_claims
from halluceval.spec import ApiSpec, EndpointSpec


def make_spec():
    return ApiSpec(
        endpoints=(
            EndpointSpec("GET", "/users/{id}", frozenset({"include_deleted"})),
            EndpointSpec("POST", "/users", frozenset({"name", "email"})),
        ),
        valid_ids=frozenset({"usr_abc123"}),
    )


class TestEvaluateEndpoint(unittest.TestCase):
    def test_valid_endpoint(self):
        spec = make_spec()
        claim = EndpointClaim(1, "GET", "/users/42", "raw")
        finding = evaluate_endpoint(claim, spec)
        self.assertEqual(finding.status, "valid")

    def test_hallucinated_endpoint(self):
        spec = make_spec()
        claim = EndpointClaim(1, "DELETE", "/users/42", "raw")
        finding = evaluate_endpoint(claim, spec)
        self.assertEqual(finding.status, "hallucinated")

    def test_typo_endpoint_gets_suggestion(self):
        spec = make_spec()
        claim = EndpointClaim(1, "POST", "/user", "raw")  # missing the 's'
        finding = evaluate_endpoint(claim, spec)
        self.assertEqual(finding.status, "hallucinated")
        self.assertIn("/users", finding.detail)


class TestEvaluateParameter(unittest.TestCase):
    def test_valid_parameter(self):
        spec = make_spec()
        finding = evaluate_parameter(ParameterClaim(1, "name", "raw"), spec)
        self.assertEqual(finding.status, "valid")

    def test_hallucinated_parameter(self):
        spec = make_spec()
        finding = evaluate_parameter(ParameterClaim(1, "phone_number", "raw"), spec)
        self.assertEqual(finding.status, "hallucinated")

    def test_typo_parameter_gets_suggestion(self):
        spec = make_spec()
        finding = evaluate_parameter(ParameterClaim(1, "emial", "raw"), spec)  # typo
        self.assertEqual(finding.status, "hallucinated")
        self.assertIn("email", finding.detail)


class TestEvaluateId(unittest.TestCase):
    def test_valid_id(self):
        spec = make_spec()
        finding = evaluate_id(IdClaim(1, "usr_abc123", "raw"), spec)
        self.assertEqual(finding.status, "valid")

    def test_hallucinated_id(self):
        spec = make_spec()
        finding = evaluate_id(IdClaim(1, "usr_totallyfake", "raw"), spec)
        self.assertEqual(finding.status, "hallucinated")

    def test_raises_when_spec_has_no_id_registry(self):
        spec = ApiSpec(endpoints=())
        with self.assertRaises(ValueError):
            evaluate_id(IdClaim(1, "usr_abc123", "raw"), spec)


class TestEvaluateFullPipeline(unittest.TestCase):
    def test_ids_skipped_entirely_when_no_registry_supplied(self):
        spec = ApiSpec(
            endpoints=(EndpointSpec("GET", "/users/{id}", frozenset({"include_deleted"})),),
            valid_ids=frozenset(),  # no ID registry
        )
        claims = extract_claims('requests.get("/users/usr_abc123")\n')
        findings = evaluate(claims, spec)
        id_findings = [f for f in findings if f.claim_type == "id"]
        self.assertEqual(id_findings, [])  # not scored, not fabricated as "valid" either

    def test_realistic_mixed_snippet(self):
        spec = make_spec()
        snippet = (
            'requests.get("https://api.example.com/users/usr_abc123", '
            'params={"include_deleted": true})\n'
            'requests.post("/users", json={"name": "Ada", "phone_number": "555-1234"})\n'
            'requests.delete("https://api.example.com/users/usr_fake999")\n'
        )
        claims = extract_claims(snippet)
        findings = evaluate(claims, spec)

        hallucinated_values = {f.value for f in findings if f.status == "hallucinated"}
        self.assertIn("phone_number", hallucinated_values)     # not a real parameter
        self.assertIn("usr_fake999", hallucinated_values)       # not a real id
        self.assertIn("DELETE /users/usr_fake999", hallucinated_values)  # no DELETE endpoint at all

        valid_values = {f.value for f in findings if f.status == "valid"}
        self.assertIn("include_deleted", valid_values)
        self.assertIn("name", valid_values)
        self.assertIn("usr_abc123", valid_values)


if __name__ == "__main__":
    unittest.main()
