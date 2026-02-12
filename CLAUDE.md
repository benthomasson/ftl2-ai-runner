# CLAUDE.md - Project Instructions for Claude

## Project Overview

ftl2-ai-runner runs markdown desired-state files as AWX job templates via ftl2-ai-loop's reconcile() function. It extends ftl2-runner's AWX integration to support AI-driven automation.

## Key Concepts

- **Markdown as Playbook**: `.yml` files with `hosts: all` header + `---` separator + markdown desired state
- **Reconcile Loop**: ftl2-ai-loop's observe/decide/execute loop drives convergence
- **Event Translation**: FTL2 module events are translated to AWX events via EventTranslator (from ftl2-runner)
- **ANSI Encoding**: Events encoded as ANSI escape sequences for AWX's OutputEventFilter
- **Python Script Fallback**: Files containing `async def run(` are handled as FTL2 Python scripts (ftl2-runner behavior)

## Project Structure

```
ftl2-ai-runner/
├── src/ftl2_ai_runner/
│   ├── __init__.py      # Public exports
│   ├── __main__.py      # CLI entry point
│   ├── playbook.py      # ANSI encoding, reconcile wrapper, script fallback
│   └── markdown.py      # Parse .yml markdown files
├── tests/
│   ├── test_markdown.py
│   └── test_playbook_ansi.py
├── ee/
│   └── Containerfile.dev
└── examples/
    └── nginx.yml
```

## Development Commands

```bash
# Install dependencies
uv pip install -e ".[dev]"

# Run all tests
uv run pytest tests/ -v

# Test CLI
uv run ftl2-ai-runner playbook examples/nginx.yml
```

## Related Projects

- **ftl2-runner**: `/Users/ben/git/ftl2-runner` - Base AWX integration (EventTranslator, ANSI encoding, RunnerContext)
- **ftl2-ai-loop**: `/Users/ben/git/ftl2-ai-loop` - AI reconciliation loop (reconcile API)
- **FTL2**: `/Users/ben/git/faster-than-light2` - The execution engine
- **AWX**: `/Users/ben/git/awx` - Controller that uses Receptor
