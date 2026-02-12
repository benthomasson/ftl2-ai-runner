"""Ansible-playbook compatible command for ftl2-ai-runner.

Detects whether a playbook file is a markdown desired-state description
or a Python script, and runs it accordingly:

- Markdown: feeds to ftl2-ai-loop's reconcile() with AWX event emission
- Python script: falls back to ftl2-runner's load_baked_script() behavior

Usage:
    ftl2-ai-runner playbook [ansible-playbook args] <playbook.yml>
    ansible-playbook [args] <playbook.yml>  # via symlink/wrapper
"""

import argparse
import asyncio
import os
import sys
from typing import Any

from ftl2_runner.events import EventTranslator, encode_event_ansi
from ftl2_runner.playbook import parse_extravars, run_playbook as run_script_playbook

from ftl2_ai_loop import reconcile, ask_user_noninteractive
from ftl2_ai_runner.markdown import parse_desired_state


def _make_ansi_emitter(translator: EventTranslator):
    """Create an on_event callback that writes ANSI-encoded events to stdout.

    Same pattern as ftl2-runner's playbook.py on_event.
    """
    def on_event(event: dict[str, Any]) -> None:
        encoded: dict[str, Any] = {
            "event": event.get("event", "verbose"),
            "uuid": event.get("uuid"),
            "created": event.get("created"),
            "event_data": event.get("event_data", {}),
            "pid": os.getpid(),
        }
        if event.get("parent_uuid"):
            encoded["parent_uuid"] = event["parent_uuid"]
        job_id = os.environ.get("JOB_ID", "")
        if job_id:
            encoded["job_id"] = int(job_id)

        sys.stdout.write(encode_event_ansi(encoded))

        stdout_text = event.get("stdout", "")
        if stdout_text:
            sys.stdout.write(stdout_text)
            if not stdout_text.endswith("\n"):
                sys.stdout.write("\n")

        sys.stdout.write(encode_event_ansi(encoded))
        sys.stdout.flush()

    return on_event


async def run_reconcile(
    playbook_path: str,
    inventory: str | None = None,
    extra_vars: dict[str, Any] | None = None,
    verbosity: int = 0,
) -> int:
    """Run a markdown desired-state file through reconcile().

    Args:
        playbook_path: Path to the .yml file
        inventory: Path to inventory file/directory
        extra_vars: Extra variables dict
        verbosity: Verbosity level

    Returns:
        Exit code (0 = converged, 1 = not converged, 2 = task failures)
    """
    desired_state = parse_desired_state(playbook_path)
    if desired_state is None:
        print(f"ERROR: Could not extract desired state from {playbook_path}", file=sys.stderr)
        return 1

    extra_vars = extra_vars or {}

    # Set up event translation
    translator = EventTranslator(ident="1", verbosity=verbosity)
    on_event = _make_ansi_emitter(translator)
    translator.on_event = on_event

    # Stats tracking (same pattern as RunnerContext._handle_ftl2_event)
    stats: dict[str, dict[str, int]] = {}

    def handle_ftl2_event(event: dict[str, Any]) -> None:
        """Handle FTL2 module events from reconcile's automation context."""
        # Emit task_start before each module_start
        if event.get("event") == "module_start":
            module_name = event.get("module", "unknown")
            task_event = translator.create_task_start_event(module_name, module_name)
            on_event(task_event)

        # Translate and forward
        translator(event)

        # Update stats
        if event.get("event") == "module_complete":
            host = event.get("host", "localhost")
            if host not in stats:
                stats[host] = {
                    "ok": 0, "changed": 0, "failed": 0,
                    "skipped": 0, "rescued": 0, "ignored": 0,
                }
            if event.get("success"):
                stats[host]["ok"] += 1
                if event.get("changed"):
                    stats[host]["changed"] += 1
            else:
                stats[host]["failed"] += 1
                stats[host]["ignored"] += 1

    # Emit playbook hierarchy events
    start_event = translator.create_playbook_start_event()
    on_event(start_event)

    play_event = translator.create_play_start_event("Reconcile")
    on_event(play_event)

    try:
        result = await reconcile(
            desired_state=desired_state,
            inventory=inventory,
            ask_user=ask_user_noninteractive,
            quiet=True,
            on_event=handle_ftl2_event,
        )

        # Emit stats
        if stats:
            stats_event = translator.create_stats_event(stats)
            on_event(stats_event)

        converged = result.get("converged", False)

        # Check for task failures
        has_failures = any(
            counts.get("failed", 0) > 0 for counts in stats.values()
        )

        if has_failures:
            return 2
        return 0 if converged else 1

    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1


async def run_playbook(
    playbook_path: str,
    inventory: str | None = None,
    extra_vars: dict[str, Any] | None = None,
    check_mode: bool = False,
    verbosity: int = 0,
) -> int:
    """Run a playbook file — detects markdown vs Python script.

    Args:
        playbook_path: Path to the .yml file
        inventory: Path to inventory file/directory
        extra_vars: Extra variables dict
        check_mode: Run in check mode
        verbosity: Verbosity level

    Returns:
        Exit code (0 = success/converged)
    """
    desired_state = parse_desired_state(playbook_path)

    if desired_state is not None:
        # Markdown desired-state file → reconcile
        return await run_reconcile(
            playbook_path=playbook_path,
            inventory=inventory,
            extra_vars=extra_vars,
            verbosity=verbosity,
        )
    else:
        # Python script → ftl2-runner's playbook handler
        return await run_script_playbook(
            playbook_path=playbook_path,
            inventory=inventory,
            extra_vars=extra_vars,
            check_mode=check_mode,
            verbosity=verbosity,
        )


def create_playbook_parser(subparsers: argparse._SubParsersAction) -> argparse.ArgumentParser:
    """Create the playbook subcommand parser.

    Accepts all common ansible-playbook arguments for compatibility.
    """
    pb_parser = subparsers.add_parser(
        "playbook",
        help="Run a playbook as markdown reconcile or FTL2 script",
        description="Execute a playbook file as markdown desired-state or FTL2 Python script.",
    )

    pb_parser.add_argument(
        "playbook",
        help="Playbook file to execute",
    )

    pb_parser.add_argument(
        "-i", "--inventory",
        dest="inventory",
        help="Inventory file or directory",
    )

    pb_parser.add_argument(
        "-e", "--extra-vars",
        dest="extra_vars",
        action="append",
        default=[],
        help="Extra variables (key=value, JSON, or @file)",
    )

    pb_parser.add_argument(
        "-C", "--check",
        dest="check_mode",
        action="store_true",
        help="Run in check mode (dry run)",
    )

    pb_parser.add_argument(
        "-v", "--verbose",
        action="count",
        default=0,
        help="Increase verbosity",
    )

    # Accepted but ignored arguments for ansible-playbook compatibility
    for flag, dest in [
        ("-u", "remote_user"),
        ("--become-user", "become_user"),
        ("--become-method", "become_method"),
        ("--vault-password-file", "vault_password_file"),
        ("--vault-id", "vault_id"),
        ("--syntax-check", "syntax_check"),
        ("--list-tasks", "list_tasks"),
        ("--list-tags", "list_tags"),
        ("--list-hosts", "list_hosts"),
        ("--start-at-task", "start_at_task"),
        ("--skip-tags", "skip_tags"),
        ("-t", "tags"),
        ("-l", "limit"),
    ]:
        pb_parser.add_argument(flag, dest=dest, default=None, help=argparse.SUPPRESS)

    for flag, dest in [
        ("-b", "become"),
        ("--become", "become"),
        ("--diff", "diff_mode"),
        ("--ask-pass", "ask_pass"),
        ("--ask-become-pass", "ask_become_pass"),
        ("--ask-vault-pass", "ask_vault_pass"),
    ]:
        pb_parser.add_argument(flag, dest=dest, action="store_true", default=False, help=argparse.SUPPRESS)

    pb_parser.add_argument(
        "-f", "--forks",
        dest="forks",
        type=int,
        default=5,
        help=argparse.SUPPRESS,
    )

    return pb_parser


def handle_playbook(args: argparse.Namespace) -> int:
    """Handle the playbook command."""
    extra_vars = parse_extravars(args.extra_vars)

    return asyncio.run(
        run_playbook(
            playbook_path=args.playbook,
            inventory=args.inventory,
            extra_vars=extra_vars,
            check_mode=args.check_mode,
            verbosity=args.verbose,
        )
    )
