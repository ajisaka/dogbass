# Copilot Instructions

## Commands

- This repository is a package-based Python CLI managed with `uv`.
- End users are expected to install and update it with `uv tool install --python 3.12 --force git+https://github.com/ajisaka/dogbass.git` and invoke the `dogbass` command directly.
- For local development inside the repository, use `uv run dogbass --help` to exercise the CLI entrypoint.
- Lint with `uv run ruff check .`
- Type-check with `uv run mypy .`
- Run the full test suite with `uv run python -m unittest discover -s tests`
- Run a single test with `uv run python -m unittest tests.test_cli.DogbassTests.test_pull_markdown_file_updates_local_markdown`

## Architecture

- `dogbass/cli.py` is the primary command surface and defines the `click`-based `new`, `push`, and `pull` subcommands.
- `dogbass/docbase.py` contains the DocBase HTTP client and reads `DOCBASE_DOMAIN` / `DOCBASE_TOKEN` from the environment.
- `dogbass/markdown.py` is responsible for YAML Front Matter parsing, Markdown template creation, Markdown serialization, and preserving the source file's newline convention when rewriting files.
- `main.py` is only a thin wrapper that forwards to `dogbass.cli:main`.
- `pyproject.toml` defines the package metadata, console script, and in-repo PEP 517 build backend; `uv.lock` should stay in sync with dependency changes.
- `tests/test_cli.py` covers the main CLI flows with mocked DocBase API interactions and uses `click.testing.CliRunner` for command-level tests.
- `dogbass` now targets Python 3.12+ because the declared `click` / `httpx` dependency set must run unchanged in the supported runtime.

## Conventions

- Keep user-facing documentation aligned with the installed-command workflow (`dogbass ...`), while using `uv run ...` for local repository validation.
- `dogbass new <file>` is interactive: it prompts for a title and creates a file with `draft: true` by default.
- `dogbass pull <file>` updates an existing local file by reading its front matter `id`, while `dogbass pull --id <docbase-id> <file>` imports a DocBase post into a new local file.
- `dogbass pull --id ...` must not overwrite an existing file; preserve this safety check.
- Preserve Markdown file newline style when changing files through `push` or `pull`; this behavior is intentional and covered by tests.
- The supported commands are `new`, `push`, and `pull`; do not reintroduce the removed `update` alias unless explicitly requested.
- Use `uv`-managed commands when running Python in this repository instead of assuming a globally managed environment.
- When adding dependencies, update `pyproject.toml` and refresh `uv.lock` together.
