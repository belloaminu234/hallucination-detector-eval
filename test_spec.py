import unittest

from halluceval.spec import ApiSpec, EndpointSpec, find_matching_endpoint, load_spec, path_matches_template


class TestPathMatchesTemplate(unittest.TestCase):
    def test_exact_match_no_variables(self):
        self.assertTrue(path_matches_template("/users", "/users"))

    def test_single_variable(self):
        self.assertTrue(path_matches_template("/users/42", "/users/{id}"))
        self.assertTrue(path_matches_template("/users/usr_abc123", "/users/{id}"))

    def test_multiple_variables(self):
        self.assertTrue(
            path_matches_template("/users/42/orders/7", "/users/{id}/orders/{order_id}")
        )

    def test_wrong_segment_count_does_not_match(self):
        self.assertFalse(
            path_matches_template("/users/42/orders", "/users/{id}/orders/{order_id}")
        )
        self.assertFalse(path_matches_template("/users", "/users/{id}"))

    def test_trailing_slash_normalized(self):
        self.assertTrue(path_matches_template("/users/", "/users"))
        self.assertTrue(path_matches_template("/users", "/users/"))

    def test_variable_does_not_cross_segment_boundary(self):
        # "{id}" should match one path segment, not "/42/orders"
        self.assertFalse(path_matches_template("/users/42/orders", "/users/{id}"))


class TestFindMatchingEndpoint(unittest.TestCase):
    def setUp(self) -> None:
        self.spec = ApiSpec(
            endpoints=(
                EndpointSpec("GET", "/users/{id}", frozenset({"include_deleted"})),
                EndpointSpec("POST", "/users", frozenset({"name", "email"})),
            )
        )

    def test_finds_matching_endpoint(self):
        match = find_matching_endpoint("GET", "/users/42", self.spec)
        self.assertIsNotNone(match)
        self.assertEqual(match.path_template, "/users/{id}")

    def test_method_mismatch_returns_none(self):
        self.assertIsNone(find_matching_endpoint("DELETE", "/users/42", self.spec))

    def test_method_is_case_insensitive(self):
        match = find_matching_endpoint("get", "/users/42", self.spec)
        self.assertIsNotNone(match)


class TestLoadSpec(unittest.TestCase):
    def test_loads_from_json(self):
        json_text = """
        {
            "endpoints": [
                {"method": "GET", "path": "/users/{id}", "parameters": ["include_deleted"]},
                {"method": "POST", "path": "/users", "parameters": ["name", "email"]}
            ],
            "valid_ids": ["usr_abc123", "usr_def456"]
        }
        """
        spec = load_spec(json_text)
        self.assertEqual(len(spec.endpoints), 2)
        self.assertIn("usr_abc123", spec.valid_ids)
        self.assertEqual(spec.all_parameters(), {"include_deleted", "name", "email"})

    def test_missing_valid_ids_defaults_to_empty(self):
        json_text = '{"endpoints": [{"method": "GET", "path": "/ping", "parameters": []}]}'
        spec = load_spec(json_text)
        self.assertEqual(spec.valid_ids, frozenset())


if __name__ == "__main__":
    unittest.main()
