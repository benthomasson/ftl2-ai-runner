"""CLI entry point for ftl2-ai-runner.

Provides an ansible-playbook compatible interface that detects
markdown desired-state files and runs them through ftl2-ai-loop's
reconcile(), or falls back to ftl2-runner for Python scripts.
"""

import argparse
import sys

from ftl2_ai_runner.playbook import create_playbook_parser, handle_playbook


def main(args: list[str] | None = None) -> int:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="ftl2-ai-runner",
        description="Run markdown desired-state files as AWX job templates",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Playbook command (mimics ansible-playbook CLI)
    create_playbook_parser(subparsers)

    parsed = parser.parse_args(args)

    if parsed.command == "playbook":
        return handle_playbook(parsed)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
