"""Tests for markdown.py — desired-state file parsing."""

import tempfile
from pathlib import Path

from ftl2_ai_runner.markdown import parse_desired_state


def test_parse_markdown_with_separator():
    """Files with hosts: all + --- should return content after ---."""
    content = "hosts: all\n---\n# Web Server\n\nEnsure nginx is installed.\n"
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
        f.write(content)
        f.flush()
        result = parse_desired_state(f.name)
    assert result == "# Web Server\n\nEnsure nginx is installed."


def test_parse_markdown_without_separator():
    """Files without --- should return content minus hosts: line."""
    content = "hosts: all\n# Web Server\n\nEnsure nginx is installed.\n"
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
        f.write(content)
        f.flush()
        result = parse_desired_state(f.name)
    assert result == "# Web Server\n\nEnsure nginx is installed."


def test_parse_python_script():
    """Files containing async def run( should return None."""
    content = 'hosts: all  # noqa\nasync def run(inventory_path, extravars, runner):\n    pass\n'
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
        f.write(content)
        f.flush()
        result = parse_desired_state(f.name)
    assert result is None


def test_parse_empty_after_separator():
    """Files with --- but no content after should return None."""
    content = "hosts: all\n---\n"
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
        f.write(content)
        f.flush()
        result = parse_desired_state(f.name)
    assert result is None


def test_parse_multiline_desired_state():
    """Multi-paragraph desired state is preserved."""
    content = """hosts: all
---
# Database Setup

Ensure PostgreSQL 16 is installed and running.
Create a database called "myapp" with user "appuser".

## Security

- SSL should be enabled
- Only allow connections from 10.0.0.0/8
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
        f.write(content)
        f.flush()
        result = parse_desired_state(f.name)
    assert "# Database Setup" in result
    assert "PostgreSQL 16" in result
    assert "## Security" in result
    assert "10.0.0.0/8" in result
