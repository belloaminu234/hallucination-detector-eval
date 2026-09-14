import unittest

from halluceval.extract import extract_claims, extract_endpoint_claims, extract_id_claims, extract_parameter_claims


class TestExtractEndpointClaims(unittest.TestCase):
    def test_prose_style_mention(self):
        claims = extract_endpoint_claims("# Calling GET /users/{id} to fetch a user\n")
        self.assertEqual(len(claims), 1)
        self.assertEqual(claims[0].method, "GET")
        self.assertEqual(claims[0].path, "/users/{id}")

    def test_requests_call_with_full_url(self):
        claims = extract_endpoint_claims('requests.get("https://api.example.com/users/42")\n')
        self.assertEqual(len(claims), 1)
        self.assertEqual(claims[0].method, "GET")
        self.assertEqual(claims[0].path, "/users/42")

    def test_requests_call_with_relative_path(self):
        claims = extract_endpoint_claims('requests.post("/users", json={"name": "Ada"})\n')
        self.assertEqual(len(claims), 1)
        self.assertEqual(claims[0].method, "POST")
        self.assertEqual(claims[0].path, "/users")

    def test_requests_call_is_not_double_counted_as_prose(self):
        # This was a real bug found during manual testing: the method
        # name inside "requests.get(..." could spuriously also match
        # the prose pattern.
        claims = extract_endpoint_claims('requests.get("https://api.example.com/users/42")\n')
        self.assertEqual(len(claims), 1)

    def test_line_numbers_are_1_indexed_and_correct(self):
        text = "line one\nrequests.get(\"/users/42\")\nline three\n"
        claims = extract_endpoint_claims(text)
        self.assertEqual(claims[0].line_no, 2)


class TestExtractParameterClaims(unittest.TestCase):
    def test_generic_client_call_kwargs(self):
        claims = extract_parameter_claims('client.orders.create(customer_id="cus_1", amount=500)\n')
        names = {c.name for c in claims}
        self.assertEqual(names, {"customer_id", "amount"})

    def test_requests_wrapper_kwargs_not_treated_as_domain_parameters(self):
        # Regression test: "params" and "json" are requests' OWN keyword
        # arguments, not domain-level API parameters, and must not be
        # extracted as parameter claims themselves.
        claims = extract_parameter_claims(
            'requests.get("https://api.example.com/users/42", params={"include_deleted": true})\n'
        )
        names = {c.name for c in claims}
        self.assertNotIn("params", names)
        self.assertIn("include_deleted", names)

    def test_json_dict_keys_extracted_as_parameters(self):
        claims = extract_parameter_claims(
            'requests.post("/users", json={"name": "Ada", "email": "ada@example.com"})\n'
        )
        names = {c.name for c in claims}
        self.assertEqual(names, {"name", "email"})

    def test_no_duplicate_extraction_between_requests_and_generic_call_patterns(self):
        # The generic client-call regex could otherwise ALSO match a
        # requests.get(...) line and re-extract "params" as a kwarg.
        claims = extract_parameter_claims(
            'requests.get("https://api.example.com/users/42", params={"limit": 10})\n'
        )
        names = [c.name for c in claims]
        self.assertEqual(names.count("limit"), 1)


class TestExtractIdClaims(unittest.TestCase):
    def test_matches_prefix_underscore_alphanumeric_with_digit(self):
        claims = extract_id_claims("id: usr_abc123\n")
        self.assertEqual([c.value for c in claims], ["usr_abc123"])

    def test_does_not_match_ordinary_snake_case_words(self):
        # Regression test: this was a real false positive found during
        # manual testing -- "include_deleted" matched the old ID regex
        # because it happened to be "letters_letters" shaped.
        claims = extract_id_claims("include_deleted and customer_id are parameter names\n")
        self.assertEqual(claims, [])

    def test_matches_multiple_ids_on_one_line(self):
        claims = extract_id_claims("usr_abc123 and ord_9f8e7d were both returned\n")
        self.assertEqual({c.value for c in claims}, {"usr_abc123", "ord_9f8e7d"})

    def test_short_numeric_suffix_below_length_threshold_not_matched(self):
        # "ord_42" has a digit but the suffix is short -- below what
        # real generated IDs typically look like; documented as an
        # intentional precision/recall tradeoff.
        claims = extract_id_claims("ord_42\n")
        self.assertEqual(claims, [])


class TestExtractClaims(unittest.TestCase):
    def test_combined_extraction_on_realistic_snippet(self):
        snippet = (
            '# Fetching a user via GET /users/{id}\n'
            'response = requests.get("https://api.example.com/users/usr_abc123", '
            'params={"include_deleted": true})\n'
            'client.orders.create(customer_id="cus_9f8e7d", amount=500, currency="usd")\n'
        )
        claims = extract_claims(snippet)
        self.assertEqual(len(claims.endpoints), 2)  # prose mention + requests call
        param_names = {c.name for c in claims.parameters}
        self.assertEqual(param_names, {"include_deleted", "customer_id", "amount", "currency"})
        id_values = {c.value for c in claims.ids}
        self.assertEqual(id_values, {"usr_abc123", "cus_9f8e7d"})


if __name__ == "__main__":
    unittest.main()
