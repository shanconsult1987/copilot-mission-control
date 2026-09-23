"""Tests for the Mission Control command-line interface."""

import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO

from app.main import _build_parser, _format_result, main
from app.mission import Incident, process_incident


class MainTests(unittest.TestCase):
    """Verify command-line parsing, formatting, and exit behavior."""

    def test_build_parser_reads_required_arguments(self) -> None:
        args = _build_parser().parse_args(
            ["AUR-301", "Battery voltage is falling."]
        )

        self.assertEqual("AUR-301", args.incident_id)
        self.assertEqual("Battery voltage is falling.", args.description)

    def test_format_result_includes_classification_and_actions(self) -> None:
        result = process_incident(
            Incident("AUR-302", "Battery voltage is falling.")
        )

        output = _format_result(result)

        self.assertIn("Incident: AUR-302", output)
        self.assertIn("Category: battery", output)
        self.assertIn("Matched keywords: battery, voltage", output)
        self.assertIn(
            "Response: Protect remaining electrical power.",
            output,
        )
        self.assertIn(
            "1. Reduce nonessential power consumption.",
            output,
        )

    def test_main_prints_result_and_returns_success(self) -> None:
        stdout = StringIO()

        with redirect_stdout(stdout):
            exit_code = main(
                ["AUR-303", "The antenna lost its telemetry signal."]
            )

        self.assertEqual(0, exit_code)
        self.assertIn("Incident: AUR-303", stdout.getvalue())
        self.assertIn("Category: communication", stdout.getvalue())

    def test_main_prints_validation_error_and_returns_failure(self) -> None:
        stderr = StringIO()

        with redirect_stderr(stderr):
            exit_code = main([" ", "Battery voltage is falling."])

        self.assertEqual(2, exit_code)
        self.assertEqual(
            "Error: incident_id must not be empty\n",
            stderr.getvalue(),
        )


if __name__ == "__main__":
    unittest.main()
