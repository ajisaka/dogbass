# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## About

**dogbass** is a Python CLI that synchronizes local Markdown files with [DocBase](https://docbase.io/), a team documentation platform. It uses YAML Front Matter in Markdown files to track metadata (title, tags, draft status, scope, groups, DocBase post ID).

## Commands

This project uses `uv` for Python package management (Python 3.12+).

- **Lint:** `uv run ruff check .`
- **Type-check:** `uv run mypy .`
- **Run tests:** `uv run python -m unittest discover -s tests`
- **Run single test:** `uv run python -m unittest tests.test_cli.DogbassTests.test_pull_markdown_file_updates_local_markdown`
- **Run CLI locally:** `uv run dogbass --help`
- **Install locally:** `uv tool install --python 3.12 --force --reinstall .`

## Architecture

Data flows: CLI handler → Markdown parser (load local file) → DocBase HTTP client → Markdown serializer (write updated file).

**`dogbass/cli.py`** — Primary command surface. Defines `click`-based subcommands (`new`, `push`, `pull`, `groups`, `install-hook`, `sync-commit`). Contains git integration utilities (`get_committed_markdown_files`, `get_git_hook_path`) and the `app_error_handler` decorator that catches `AppError` and exits cleanly.

**`dogbass/markdown.py`** — YAML Front Matter parsing and file management. `MarkdownDocument` dataclass holds all metadata. Handles newline preservation (LF/CRLF detection), template generation for `new`, and normalization/validation of Front Matter fields.

**`dogbass/docbase.py`** — DocBase HTTP client. `DocBaseClient` reads `DOCBASE_DOMAIN` and `DOCBASE_TOKEN` from environment variables and provides `create_post()`, `get_post()`, `update_post()`, `list_groups()`.

**`dogbass/errors.py`** — Error hierarchy: `AppError` (base, exit_code=1), `ConfigurationError`, `ValidationError`, `FileConflictError`, `DocBaseRequestError`, `DocBaseResponseError`.

**`main.py`** — Thin wrapper forwarding to `dogbass.cli:main`.

**`build_backend.py`** — Custom PEP 517 build backend (no external build dependencies required).

## Conventions

- `dogbass new <file>` is interactive: prompts for a title, creates a file with `draft: true` by default.
- `dogbass pull <file>` updates an existing local file by reading its Front Matter `id`. `dogbass pull --id <docbase-id> <file>` imports a DocBase post into a new file — it must not overwrite an existing file.
- Absence of `id` in Front Matter → `push` creates a new post; presence → updates the existing post.
- Preserve Markdown file newline style (LF/CRLF) when rewriting through `push` or `pull`; this is intentional and covered by tests.
- The supported commands are `new`, `push`, and `pull`; do not reintroduce the removed `update` alias.
- When adding dependencies, update `pyproject.toml` and refresh `uv.lock` together.
- `tests/test_cli.py` uses `click.testing.CliRunner` and a `FakeDocBaseClient` mock; keep new tests in this pattern.
