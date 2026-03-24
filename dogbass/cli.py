from __future__ import annotations

from functools import wraps
from pathlib import Path
import shlex
import subprocess
import sys
from typing import Callable, ParamSpec, TypeVar

import click

from dogbass.errors import (
    AppError,
    DocBaseResponseError,
    FileConflictError,
    ValidationError,
)
from dogbass.docbase import DocBaseClient
from dogbass.markdown import (
    create_markdown_document,
    is_dogbass_markdown,
    load_document_id,
    load_markdown_document,
    markdown_document_from_docbase,
    write_document_id,
    write_markdown_document,
)

P = ParamSpec("P")
R = TypeVar("R")
HOOK_MARKER = "# Installed by dogbass install-hook"


def app_error_handler(
    function: Callable[P, R],
) -> Callable[P, R]:
    @wraps(function)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        try:
            return function(*args, **kwargs)
        except AppError as exc:
            click.echo(f"Error: {exc}", err=True)
            raise click.exceptions.Exit(exc.exit_code) from exc

    return wrapper


def prompt_title() -> str:
    while True:
        title = click.prompt("Title", prompt_suffix=": ").strip()
        if title:
            return title
        click.echo("Title must not be empty.")


def new_markdown_file(markdown_path: Path) -> int:
    title = prompt_title()
    create_markdown_document(markdown_path, title)
    click.echo(f"Created Markdown file at {markdown_path}")
    return 0


def push_markdown_file(
    markdown_path: Path,
    client: DocBaseClient,
    notify_override: bool | None = None,
) -> int:
    document = load_markdown_document(markdown_path)

    if document.document_id is None:
        payload = document.to_docbase_payload(
            default_scope="private", notice_override=notify_override
        )
        response = client.create_post(payload)
        created_id = response.get("id")
        if not isinstance(created_id, int):
            raise DocBaseResponseError("DocBase response is missing document id")
        write_document_id(markdown_path, created_id)
        click.echo(f"Created DocBase post {created_id} from {markdown_path}")
        return 0

    payload = document.to_docbase_payload(notice_override=notify_override)
    client.update_post(document.document_id, payload)
    click.echo(f"Updated DocBase post {document.document_id} from {markdown_path}")
    return 0


def pull_markdown_file(
    markdown_path: Path, client: DocBaseClient, document_id: int | None = None
) -> int:
    notice: bool | None = None
    if markdown_path.exists():
        try:
            notice = load_markdown_document(markdown_path).notice
        except AppError:
            notice = None
    if document_id is None:
        document_id = load_document_id(markdown_path)
    payload = client.get_post(document_id)
    document = markdown_document_from_docbase(
        markdown_path, payload, document_id, notice=notice
    )
    write_markdown_document(document)
    click.echo(f"Pulled DocBase post {document_id} into {markdown_path}")
    return 0


def list_groups(client: DocBaseClient) -> int:
    groups = client.list_groups()
    for group in groups:
        group_id = group.get("id")
        group_name = group.get("name")
        if not isinstance(group_id, int) or not isinstance(group_name, str):
            raise DocBaseResponseError("DocBase API returned an invalid group")
        click.echo(f"{group_id}\t{group_name}")
    return 0


def install_post_commit_hook(executable: str) -> int:
    repo_root = get_git_repo_root()
    hook_path = get_git_hook_path(repo_root, "post-commit")
    hook_path.parent.mkdir(parents=True, exist_ok=True)

    if hook_path.exists():
        existing = hook_path.read_text(encoding="utf-8")
        if HOOK_MARKER not in existing:
            raise FileConflictError(
                f"refusing to overwrite existing git hook: {hook_path}"
            )

    hook_path.write_text(render_post_commit_hook(executable), encoding="utf-8")
    hook_path.chmod(hook_path.stat().st_mode | 0o111)
    click.echo(f"Installed post-commit hook at {hook_path}")
    return 0


def sync_committed_markdown_files(client: DocBaseClient, rev: str = "HEAD") -> int:
    repo_root = get_git_repo_root()
    pushed = 0
    for markdown_path in get_committed_markdown_files(repo_root, rev):
        if not is_dogbass_markdown(markdown_path):
            continue
        push_markdown_file(markdown_path, client)
        pushed += 1
    return pushed


def get_git_repo_root() -> Path:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError) as exc:
        raise ValidationError("not inside a git repository") from exc

    return Path(result.stdout.strip())


def get_git_hook_path(repo_root: Path, hook_name: str) -> Path:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--git-path", f"hooks/{hook_name}"],
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        raise ValidationError("failed to locate git hooks directory") from exc

    hook_path = Path(result.stdout.strip())
    if not hook_path.is_absolute():
        hook_path = repo_root / hook_path
    return hook_path


def get_committed_markdown_files(repo_root: Path, rev: str) -> list[Path]:
    try:
        result = subprocess.run(
            [
                "git",
                "diff-tree",
                "--no-commit-id",
                "--root",
                "--name-status",
                "-z",
                "-r",
                rev,
                "--",
                "*.md",
            ],
            cwd=repo_root,
            check=True,
            capture_output=True,
        )
    except subprocess.CalledProcessError as exc:
        raise ValidationError(f"failed to inspect commit diff for {rev}") from exc

    entries = [entry.decode("utf-8") for entry in result.stdout.split(b"\0") if entry]
    files: list[Path] = []
    index = 0
    while index < len(entries):
        status = entries[index]
        index += 1
        kind = status[0]

        if kind in {"R", "C"}:
            if index + 1 >= len(entries):
                raise ValidationError("failed to parse git diff output")
            index += 1
            path_text = entries[index]
            index += 1
        else:
            if index >= len(entries):
                raise ValidationError("failed to parse git diff output")
            path_text = entries[index]
            index += 1

        if kind not in {"A", "M", "R", "C"}:
            continue

        file_path = repo_root / path_text
        if file_path.exists():
            files.append(file_path)

    return files


def render_post_commit_hook(executable: str) -> str:
    return f"#!/bin/sh\n{HOOK_MARKER}\n{shlex.quote(executable)} sync-commit\n"


@click.group()
def main() -> None:
    """Synchronize Markdown files with DocBase."""


@main.command("new")
@click.argument("markdown_file", type=click.Path(path_type=Path))
@app_error_handler
def new_command(markdown_file: Path) -> None:
    """Create a new Markdown file for DocBase."""
    new_markdown_file(markdown_file)


@main.command("push")
@click.option("--notify/--no-notify", "notify_override", default=None)
@click.argument("markdown_file", type=click.Path(exists=True, path_type=Path))
@app_error_handler
def push_command(markdown_file: Path, notify_override: bool | None) -> None:
    """Create or update a DocBase document from a Markdown file."""
    client = DocBaseClient.from_env()
    push_markdown_file(markdown_file, client, notify_override=notify_override)


@main.command("pull")
@click.option(
    "--id",
    "document_id",
    type=int,
    help="DocBase document id to import. Required when creating a new local file.",
)
@click.argument("markdown_file", type=click.Path(path_type=Path))
@app_error_handler
def pull_command(markdown_file: Path, document_id: int | None) -> None:
    """Fetch a DocBase document into a Markdown file."""
    if document_id is not None and markdown_file.exists():
        raise FileConflictError(f"refusing to overwrite existing file: {markdown_file}")
    client = DocBaseClient.from_env()
    pull_markdown_file(markdown_file, client, document_id=document_id)


@main.command("groups")
@app_error_handler
def groups_command() -> None:
    """List available DocBase groups."""
    client = DocBaseClient.from_env()
    list_groups(client)


@main.command("install-hook")
@app_error_handler
def install_hook_command() -> None:
    """Install a git post-commit hook that pushes changed dogbass Markdown files."""
    install_post_commit_hook(sys.argv[0])


@main.command("sync-commit", hidden=True)
@app_error_handler
def sync_commit_command() -> None:
    """Push changed dogbass Markdown files from the latest commit."""
    client = DocBaseClient.from_env()
    sync_committed_markdown_files(client)
