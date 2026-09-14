"""End-to-end tests: writes real spec.json and agent-output files to a
temp directory and runs the actual CLI entry point against them."""

import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from halluceval import cli

SPEC_JSON = """
{
    "endpoints": [
        {"method": "GET", "path": "/users/{id}", "parameters": ["include_deleted"]},
        {"method": "POST", "path": "/users", "parameters": ["name", "email"]}
    ],
    "valid_ids": ["usr_abc123"]
}
"""

CLEAN_OUTPUT = (
    'requests.get("https://api.example.com/users/usr_abc123", '
    'params={"include_deleted": true})\n'
)

HALLUCINATED_OUTPUT = (
    'requests.get("https://api.example.com/users/usr_abc123", '
    'params={"include_deleted": true})\n'
    'requests.post("/users", json={"name": "Ada", "phone_number": "555-1234"})\n'
    'requests.delete("https://api.example.com/users/usr_fake999")\n'
)


class TestCliEndToEnd(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.spec_path = Path(self.tmp.name) / "spec.json"
        self.spec_path.write_text(SPEC_JSON)

    def _run(self, output_text: str, extra_args: list[str] | None = None) -> tuple[int, str]:
        output_path = Path(self.tmp.name) / "output.txt"
        output_path.write_text(output_text)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            exit_code = cli.main(
                ["--spec", str(self.spec_path), "--output", str(output_path)]
                + (extra_args or [])
            )
        return exit_code, buf.getvalue()

    def test_clean_output_passes(self):
        exit_code, output = self._run(CLEAN_OUTPUT)
        self.assertEqual(exit_code, 0)
        self.assertIn("No hallucinations detected", output)

    def test_hallucinated_output_fails_by_default(self):
        exit_code, output = self._run(HALLUCINATED_OUTPUT)
        self.assertNotEqual(exit_code, 0)
        self.assertIn("phone_number", output)
        self.assertIn("usr_fake999", output)

    def test_max_hallucination_rate_threshold_allows_some_failures(self):
        # 3 hallucinated out of a larger total -- set a generous threshold
        # so it passes despite the hallucinations.
        exit_code, _ = self._run(HALLUCINATED_OUTPUT, ["--max-hallucination-rate", "1.0"])
        self.assertEqual(exit_code, 0)

    def test_missing_spec_file_returns_nonzero(self):
        output_path = Path(self.tmp.name) / "output.txt"
        output_path.write_text(CLEAN_OUTPUT)
        exit_code = cli.main(
            ["--spec", "/nonexistent/spec.json", "--output", str(output_path)]
        )
        self.assertNotEqual(exit_code, 0)

    def test_missing_output_file_returns_nonzero(self):
        exit_code = cli.main(
            ["--spec", str(self.spec_path), "--output", "/nonexistent/output.txt"]
        )
        self.assertNotEqual(exit_code, 0)


if __name__ == "__main__":
    unittest.main()
