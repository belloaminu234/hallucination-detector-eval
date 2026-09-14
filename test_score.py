import unittest

from halluceval.evaluate import Finding
from halluceval.score import compute_score


def finding(claim_type, status):
    return Finding(claim_type, 1, "x", status, "detail")


class TestComputeScore(unittest.TestCase):
    def test_no_findings_gives_zero_rate_not_division_error(self):
        score = compute_score([])
        self.assertEqual(score.total_claims, 0)
        self.assertEqual(score.hallucination_rate, 0.0)

    def test_all_valid_gives_zero_rate(self):
        findings = [finding("endpoint", "valid"), finding("parameter", "valid")]
        score = compute_score(findings)
        self.assertEqual(score.hallucination_rate, 0.0)

    def test_all_hallucinated_gives_rate_one(self):
        findings = [finding("endpoint", "hallucinated"), finding("id", "hallucinated")]
        score = compute_score(findings)
        self.assertEqual(score.hallucination_rate, 1.0)

    def test_mixed_rate(self):
        findings = [
            finding("endpoint", "valid"),
            finding("endpoint", "hallucinated"),
            finding("endpoint", "hallucinated"),
            finding("endpoint", "hallucinated"),
        ]
        score = compute_score(findings)
        self.assertEqual(score.hallucination_rate, 0.75)

    def test_by_type_breakdown(self):
        findings = [
            finding("endpoint", "valid"),
            finding("parameter", "hallucinated"),
            finding("parameter", "hallucinated"),
            finding("id", "valid"),
        ]
        score = compute_score(findings)
        self.assertEqual(score.by_type["endpoint"].hallucination_rate, 0.0)
        self.assertEqual(score.by_type["parameter"].hallucination_rate, 1.0)
        self.assertEqual(score.by_type["id"].hallucination_rate, 0.0)

    def test_by_type_with_zero_claims_of_that_type_does_not_crash(self):
        findings = [finding("endpoint", "valid")]
        score = compute_score(findings)
        self.assertEqual(score.by_type["id"].total_claims, 0)
        self.assertEqual(score.by_type["id"].hallucination_rate, 0.0)


if __name__ == "__main__":
    unittest.main()
