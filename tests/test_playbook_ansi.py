"""Tests for playbook.py — ANSI event encoding and reconcile wrapper."""

import base64
import json
import re
import tempfile
from unittest.mock import AsyncMock, patch

import pytest

from ftl2_ai_runner.markdown import parse_desired_state


# Regex to extract ANSI-encoded event data (same as ftl2-runner's tests)
EVENT_DATA_RE = re.compile(rb"\x1b\[K((?:[A-Za-z0-9+/=]+\x1b\[\d+D)+)\x1b\[K")


def decode_ansi_event(match):
    """Decode an ANSI-encoded event from a regex match."""
    raw = match.group(1)
    b64data = re.sub(rb"\x1b\[\d+D", b"", raw)
    return json.loads(base64.b64decode(b64data))


@pytest.mark.asyncio
async def test_run_reconcile_converged():
    """Reconcile that converges should return exit code 0."""
    from ftl2_ai_runner.playbook import run_reconcile

    # Create a markdown playbook
    content = "hosts: all\n---\n# Test\n\nEnsure everything is ok.\n"
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
        f.write(content)
        f.flush()
        playbook_path = f.name

    mock_result = {"converged": True, "history": [], "next_observations": []}

    with patch("ftl2_ai_runner.playbook.reconcile", new_callable=AsyncMock, return_value=mock_result):
        with patch("ftl2_ai_runner.playbook.ask_user_noninteractive"):
            rc = await run_reconcile(playbook_path)

    assert rc == 0


@pytest.mark.asyncio
async def test_run_reconcile_not_converged():
    """Reconcile that doesn't converge should return exit code 1."""
    from ftl2_ai_runner.playbook import run_reconcile

    content = "hosts: all\n---\n# Test\n\nEnsure everything is ok.\n"
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
        f.write(content)
        f.flush()
        playbook_path = f.name

    mock_result = {"converged": False, "history": [], "next_observations": []}

    with patch("ftl2_ai_runner.playbook.reconcile", new_callable=AsyncMock, return_value=mock_result):
        with patch("ftl2_ai_runner.playbook.ask_user_noninteractive"):
            rc = await run_reconcile(playbook_path)

    assert rc == 1


@pytest.mark.asyncio
async def test_run_playbook_detects_markdown():
    """run_playbook should detect markdown files and call run_reconcile."""
    from ftl2_ai_runner.playbook import run_playbook

    content = "hosts: all\n---\n# Test desired state\n"
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
        f.write(content)
        f.flush()
        playbook_path = f.name

    mock_result = {"converged": True, "history": [], "next_observations": []}

    with patch("ftl2_ai_runner.playbook.reconcile", new_callable=AsyncMock, return_value=mock_result) as mock_reconcile:
        with patch("ftl2_ai_runner.playbook.ask_user_noninteractive"):
            rc = await run_playbook(playbook_path)

    assert rc == 0
    mock_reconcile.assert_called_once()
    # Verify desired_state was extracted correctly
    call_kwargs = mock_reconcile.call_args[1]
    assert call_kwargs["desired_state"] == "# Test desired state"


@pytest.mark.asyncio
async def test_run_playbook_detects_python_script():
    """run_playbook should detect Python scripts and fall back to ftl2-runner."""
    from ftl2_ai_runner.playbook import run_playbook

    content = 'hosts: all  # noqa\nasync def run(inventory_path, extravars, runner):\n    return 0\n'
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
        f.write(content)
        f.flush()
        playbook_path = f.name

    with patch("ftl2_ai_runner.playbook.run_script_playbook", new_callable=AsyncMock, return_value=0) as mock_script:
        rc = await run_playbook(playbook_path)

    assert rc == 0
    mock_script.assert_called_once()
