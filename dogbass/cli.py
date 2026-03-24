from __future__ import annotations

from functools import wraps
from pathlib import Path
from typing import Callable, ParamSpec, TypeVar

import click

from dogbass.errors import AppError, DocBaseResponseError, FileConflictError
from dogbass.docbase import DocBaseClient
from dogbass.markdown import (
    create_markdown_document,
    load_document_id,
    load_markdown_document,
    markdown_document_from_docbase,
    write_document_id,
    write_markdown_document,
)

P = ParamSpec("P")
R = TypeVar("R")


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


def push_markdown_file(markdown_path: Path, client: DocBaseClient) -> int:
    document = load_markdown_document(markdown_path)

    if document.document_id is None:
        payload = document.to_docbase_payload(default_scope="private")
        response = client.create_post(payload)
        created_id = response.get("id")
        if not isinstance(created_id, int):
            raise DocBaseResponseError("DocBase response is missing document id")
        write_document_id(markdown_path, created_id)
        click.echo(f"Created DocBase post {created_id} from {markdown_path}")
        return 0

    payload = document.to_docbase_payload()
    client.update_post(document.document_id, payload)
    click.echo(f"Updated DocBase post {document.document_id} from {markdown_path}")
    return 0


def pull_markdown_file(
    markdown_path: Path, client: DocBaseClient, document_id: int | None = None
) -> int:
    if document_id is None:
        document_id = load_document_id(markdown_path)
    payload = client.get_post(document_id)
    document = markdown_document_from_docbase(markdown_path, payload, document_id)
    write_markdown_document(document)
    click.echo(f"Pulled DocBase post {document_id} into {markdown_path}")
    return 0


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
@click.argument("markdown_file", type=click.Path(exists=True, path_type=Path))
@app_error_handler
def push_command(markdown_file: Path) -> None:
    """Create or update a DocBase document from a Markdown file."""
    client = DocBaseClient.from_env()
    push_markdown_file(markdown_file, client)


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
