"""Parse .yml markdown files for desired-state content.

AWX discovers playbooks as .yml files. We use a convention:
- Line 1: `hosts: all` (satisfies AWX playbook discovery)
- `---` separator
- Everything after `---` is the desired state (markdown)

If the file contains `async def run(`, it's a Python script
and should be handled by ftl2-runner instead.
"""

from pathlib import Path


def parse_desired_state(path: str) -> str | None:
    """Extract desired state from a markdown playbook file.

    Args:
        path: Path to the .yml file

    Returns:
        The desired state string (content after ---), or None if
        the file is a Python script (contains 'async def run(').
    """
    content = Path(path).read_text()

    # Python scripts are handled by ftl2-runner's load_baked_script
    if "async def run(" in content:
        return None

    # Split on first --- separator
    if "---" not in content:
        # No separator — treat entire content (minus hosts: line) as desired state
        lines = content.splitlines()
        body_lines = [l for l in lines if not l.strip().startswith("hosts:")]
        return "\n".join(body_lines).strip() or None

    _, _, after = content.partition("---")
    desired_state = after.strip()
    return desired_state if desired_state else None
