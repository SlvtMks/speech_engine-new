---
name: project-health-check
description: Assess a repository's overall health (git hygiene, dependencies, tests, linting, security, docs, CI/CD, and containerization) and produce a concise, evidence-based health report with prioritized fixes. Use when the user asks for a project health check, repo audit, readiness review, cleanup checklist, or to understand why a project feels brittle/outdated.
---

# Project Health Check

## Scope + principles

- Prefer a **read-only** assessment first. Do not change code unless the user asks for fixes.
- Be **evidence-based**: include the exact commands run and their outputs (summarized), and cite files/paths for findings.
- Optimize for **next actions**: produce a prioritized list of fixes with clear owners/effort.

## Workflow (fast → deep)

### 0) Establish baseline context

1. Confirm repo root and current branch state:
   - `git status`
   - `git log -10 --oneline --decorate`
   - `git remote -v`
2. Identify stacks/tools present by scanning the root and common config paths:
   - Python: `pyproject.toml`, `requirements.txt`, `requirements-dev.txt`, `poetry.lock`, `pip-tools` files
   - Node: `package.json`, `package-lock.json`, `pnpm-lock.yaml`, `yarn.lock`
   - Containers: `Dockerfile*`, `docker-compose.yml`
   - CI: `.github/workflows/`, `.gitlab-ci.yml`, `azure-pipelines.yml`
   - Lint/format: `.ruff.toml`, `ruff.toml`, `.flake8`, `pyproject.toml`, `.prettierrc*`, `eslint.config.*`, `.eslintrc*`
3. Note any obvious risk signals:
   - Large uncommitted changes, untracked secrets, missing lockfiles, stale docs, failing tests.

### 1) Repo hygiene and maintainability

- **Git ignore + artifacts**:
  - Ensure `.gitignore` covers venvs, build outputs, local env files, logs, IDE files.
- **Project structure sanity**:
  - Look for clear boundaries (app code vs tests vs scripts) and consistent naming.
- **Release/build metadata** (if applicable):
  - Versioning strategy, changelog/release notes, reproducible builds.

### 2) Dependency health (offline-first)

#### Python

- Identify the dependency authority:
  - If `pyproject.toml` exists: prefer it; otherwise `requirements*.txt`.
- Check for consistency and obvious issues:
  - Duplicates/conflicts across requirement files.
  - Unpinned dependencies where reproducibility matters.
  - Missing dev/test dependencies when tests exist.
- If a virtualenv is present and safe to use, run:
  - `python -V`
  - `python -m pip --version`
  - `python -m pip check`

#### Node / web

- Identify package manager and lockfile:
  - Prefer the lockfile as the source of truth.
- Validate scripts and build intent:
  - Read `package.json` (do not edit)
  - Look for `lint`, `test`, `build`, `typecheck` scripts.
- If dependencies are installed (node_modules present), it’s reasonable to run:
  - `npm -v` / `node -v`
  - `npm ls --depth=0` (can be noisy; summarize)

#### Security scanning (only if tools/network are available)

- If the user wants security posture and the environment allows it, prefer:
  - `pip-audit` for Python (if installed / installable)
  - `npm audit` for Node
- If network is blocked or installs are undesired, still report:
  - Presence/absence of lockfiles
  - Dependency pinning strategy
  - Known risky patterns (e.g., downloading models/binaries at runtime without checksums)

### 3) Quality gates: tests, lint, type checks

- Run the **smallest, fastest** verification first.

#### Python

- If tests exist:
  - `python -m pytest -q`
- If lint config exists:
  - Prefer `ruff` when present: `python -m ruff check .`
- If typing is used:
  - `python -m mypy .` (only when configured; otherwise report absence)

#### Node / web

- If a `web/` app exists:
  - `npm test` (or the repo’s test script)
  - `npm run lint`
  - `npm run build`
- For TypeScript projects:
  - `npm run typecheck` if present

Record what you ran and whether it passed. If you can’t run something, explain why (missing deps, environment, time) and suggest the exact command to run later.

### 4) Build, packaging, and runtime checks

#### Docker / Compose (optional)

- Validate configuration:
  - `docker compose config`
- If Docker is available and the user wants it, try:
  - `docker build` for each Dockerfile
  - `docker compose up` smoke test (short, timeboxed)

#### Local run (optional)

- Verify the README’s “run” path actually matches scripts/config.
- If there’s a CLI/API, do a minimal smoke test:
  - `--help`, a short request, or a small sample input.

### 5) Documentation and onboarding

Check whether a new contributor can succeed in <15 minutes:

- README includes:
  - prerequisites (Python/Node/Docker versions)
  - install steps
  - how to run (dev/prod)
  - how to test/lint
  - configuration (env vars) with safe defaults
- Presence of:
  - `LICENSE`
  - Contribution guidelines (optional but helpful)
  - Architecture notes for non-trivial systems

### 6) Output: deliver a health report

Produce a concise report using this template.

```markdown
## Project health check

### Executive summary
- **Overall**: [healthy | mixed | needs attention]
- **Top 3 risks**:
  1. ...
  2. ...
  3. ...

### What I checked (evidence)
- **Git**:
  - Command(s): `git status`, `git log -10 --oneline --decorate`
  - Result: ...
- **Stacks detected**:
  - Python: [yes/no] (files: ...)
  - Node/Web: [yes/no] (files: ...)
  - Docker/Compose: [yes/no] (files: ...)
  - CI: [yes/no] (files: ...)
- **Quality gates**:
  - Tests: [pass/fail/not run] (command: ...)
  - Lint: [pass/fail/not run] (command: ...)
  - Build: [pass/fail/not run] (command: ...)

### Findings (prioritized)
#### P0 (must fix soon)
- **Finding**: ...
  - Evidence: file/path, command output, or failing check
  - Impact: ...
  - Fix (suggested): ...

#### P1 (should fix)
- ...

#### P2 (nice to have)
- ...

### Quick wins (≤30 minutes)
- ...

### Recommended next commands
```bash
# paste the exact commands the user should run next
```
```

## Examples

### Example prompts that should trigger this skill

- "Can you do a project health check on this repo?"
- "Why does this project feel brittle? Audit it."
- "Before we deploy, can you review readiness and risks?"
- "Give me a cleanup checklist for this repository."

### Example outcomes

- A short, evidence-backed report with prioritized fixes.
- Clear next commands to run, with notes about prerequisites and expected outputs.
