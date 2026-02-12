# ftl2-ai-runner

Drop-in `ansible-playbook` replacement that runs markdown desired-state files as AWX job templates. It feeds the markdown to [ftl2-ai-loop](https://github.com/benthomasson/ftl2-ai-loop)'s `reconcile()` function, which observes infrastructure, reasons with AI, and executes [FTL2](https://github.com/benthomasson/faster-than-light2) modules to converge on the desired state.

## How it works

1. AWX discovers `.yml` files in the project directory as playbooks
2. ftl2-ai-runner detects whether the file is a Python script or a markdown desired-state description
3. For markdown files, it extracts the content after `---` and passes it to `reconcile()`
4. FTL2 module events are translated to AWX-compatible events with ANSI encoding
5. AWX displays structured task output just like a normal Ansible job

## Desired state file format

Files use `hosts: all` on the first line to satisfy AWX's playbook discovery, followed by a `---` separator and the desired state in markdown:

```yaml
hosts: all
---
# Web Server Setup

Ensure nginx is installed and running.
The default site should serve files from /var/www/html.
Create an index.html with the content "Hello from FTL2 AI Runner".
```

The markdown after `---` is passed directly to `reconcile()` as the desired state. The AI observes the current infrastructure, decides what actions to take, and executes FTL2 modules until the system matches the description.

## Example desired state files

### Simple service setup

```yaml
hosts: all
---
# Redis Cache

Install redis-server and ensure it is running.
Configure it to listen on 127.0.0.1 only.
Set maxmemory to 256mb with allkeys-lru eviction policy.
```

### Multi-service application

```yaml
hosts: all
---
# Blog Application

## Database
PostgreSQL 16 should be installed and running.
Create a database called "blog" owned by user "blogapp".

## Application
Clone https://github.com/example/blog-app to /opt/blog-app.
Install Python dependencies from requirements.txt.
Create a systemd service called "blog" that runs the app on port 8000.

## Web Server
Nginx should proxy requests from port 80 to localhost:8000.
Enable the site and reload nginx.
```

## Installation

```bash
pip install ftl2-ai-runner
```

Or from source:

```bash
pip install git+https://github.com/benthomasson/ftl2-ai-runner
```

## Usage

### CLI

```bash
# Run a markdown desired-state file
ftl2-ai-runner playbook -i inventory nginx.yml

# Also works via ansible-playbook symlink (inside EE container)
ansible-playbook -i inventory nginx.yml
```

### AWX / AAP

1. Build the execution environment from `ee/Containerfile.dev`
2. Set `ANTHROPIC_API_KEY` via a custom credential type
3. Create a project with `.yml` desired-state files
4. Create a job template pointing at a desired-state file
5. Launch the job — AWX shows structured task events as the AI converges

## Python script fallback

Files containing `async def run(` are treated as FTL2 Python scripts and handled by [ftl2-runner](https://github.com/benthomasson/ftl2-runner)'s playbook mode:

```yaml
hosts: all  # noqa
async def run(inventory_path, extravars, runner):
    async with runner.automation() as ftl:
        await ftl.ping()
        await ftl.command(cmd="uname -a")
    return 0
```

## Dependencies

- [ftl2-runner](https://github.com/benthomasson/ftl2-runner) — EventTranslator, ANSI encoding, RunnerContext
- [ftl2-ai-loop](https://github.com/benthomasson/ftl2-ai-loop) — AI reconciliation loop (observe/decide/execute)
- [FTL2](https://github.com/benthomasson/faster-than-light2) — Execution engine
