# Copilot Instructions

## Commands

- Install and run within the `uv` workflow used by this repository.
- Run the current application entrypoint with `uv run python main.py`.
- There are no project-defined build, lint, or test commands in `pyproject.toml` at the moment. Do not assume `pytest`, `ruff`, or other tooling is available unless you add and wire it explicitly.

## Architecture

- This repository is currently a minimal flat Python project, not a package-based application.
- `main.py` is the only code entrypoint and contains the full runtime behavior.
- `pyproject.toml` defines the project metadata, Python requirement (`>=3.11`), and runtime dependencies.
- `uv.lock` is the lockfile for the `uv`-managed environment and should stay in sync with dependency changes in `pyproject.toml`.
- `README.md` is currently empty, so rely on the source tree and project metadata rather than README-driven workflows.

## Conventions

- Keep changes aligned with the existing flat layout unless there is a clear reason to introduce a package or additional modules.
- Use `uv`-managed commands when running Python in this repository instead of assuming a globally managed environment.
- When adding dependencies, update `pyproject.toml` and refresh `uv.lock` together.
- Treat `main.py` as the authoritative executable path until the project introduces a package, console script, or alternate entrypoint.
