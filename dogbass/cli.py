from __future__ import annotations

import argparse
from pathlib import Path

from dogbass.docbase import DocBaseClient
from dogbass.markdown import (
    create_markdown_document,
    load_document_id,
    load_markdown_document,
    markdown_document_from_docbase,
    write_document_id,
    write_markdown_document,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="dogbass")
    subparsers = parser.add_subparsers(dest="command", required=True)

    new_parser = subparsers.add_parser(
        "new", help="Create a new Markdown file for DocBase."
    )
    new_parser.add_argument(
        "markdown_file", help="Path to the Markdown file to create."
    )

    push_parser = subparsers.add_parser(
        "push", help="Create or update a DocBase document from a Markdown file."
    )
    push_parser.add_argument("markdown_file", help="Path to the Markdown file to sync.")

    pull_parser = subparsers.add_parser(
        "pull", help="Fetch a DocBase document into a Markdown file."
    )
    pull_parser.add_argument(
        "--id",
        dest="document_id",
        type=int,
        help="DocBase document id to import. Required when creating a new local file.",
    )
    pull_parser.add_argument(
        "markdown_file", help="Path to the Markdown file to refresh from DocBase."
    )

    return parser


def prompt_title() -> str:
    while True:
        title = input("Title: ").strip()
        if title:
            return title
        print("Title must not be empty.")


def new_markdown_file(markdown_path: Path) -> int:
    title = prompt_title()
    create_markdown_document(markdown_path, title)
    print(f"Created Markdown file at {markdown_path}")
    return 0


def push_markdown_file(markdown_path: Path, client: DocBaseClient) -> int:
    document = load_markdown_document(markdown_path)
    payload = document.to_docbase_payload()

    if document.document_id is None:
        response = client.create_post(payload)
        created_id = response.get("id")
        if not isinstance(created_id, int):
            raise RuntimeError(
                "DocBase create response did not include an integer 'id'"
            )
        write_document_id(markdown_path, created_id)
        print(f"Created DocBase post {created_id} from {markdown_path}")
        return 0

    client.update_post(document.document_id, payload)
    print(f"Updated DocBase post {document.document_id} from {markdown_path}")
    return 0


def pull_markdown_file(
    markdown_path: Path, client: DocBaseClient, document_id: int | None = None
) -> int:
    if document_id is None:
        document_id = load_document_id(markdown_path)
    payload = client.get_post(document_id)
    document = markdown_document_from_docbase(markdown_path, payload, document_id)
    write_markdown_document(document)
    print(f"Pulled DocBase post {document_id} into {markdown_path}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "new":
        return new_markdown_file(Path(args.markdown_file))

    client = DocBaseClient.from_env()
    if args.command == "push":
        return push_markdown_file(Path(args.markdown_file), client)
    if args.command == "pull":
        return pull_markdown_file(
            Path(args.markdown_file), client, document_id=args.document_id
        )

    parser.error(f"Unsupported command: {args.command}")
    return 2
