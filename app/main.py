"""Command-line entry point for the Mission Control application."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from app.mission import Incident, IncidentResult, process_incident


def _build_parser() -> argparse.ArgumentParser:
    """Create the command-line argument parser."""

    parser = argparse.ArgumentParser(
        description="Classify a spacecraft incident and recommend a response."
    )
    parser.add_argument("incident_id", help="incident tracking identifier")
    parser.add_argument("description", help="incident description")
    return parser


def _format_result(result: IncidentResult) -> str:
    """Format a structured incident result for terminal output."""

    keywords = ", ".join(result.matched_keywords) or "none"
    actions = "\n".join(
        f"{number}. {action}"
        for number, action in enumerate(result.response.actions, start=1)
    )
    return (
        f"Incident: {result.incident.incident_id}\n"
        f"Category: {result.category.value}\n"
        f"Matched keywords: {keywords}\n"
        f"Response: {result.response.summary}\n"
        f"Actions:\n{actions}"
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Run Mission Control and return a process exit code."""

    args = _build_parser().parse_args(argv)
    try:
        result = process_incident(
            Incident(
                incident_id=args.incident_id,
                description=args.description,
            )
        )
    except (TypeError, ValueError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 2

    print(_format_result(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())