from __future__ import annotations

import argparse
from pathlib import Path

from dogbass.docbase import DocBaseClient
from dogbass.markdown import (
    load_document_id,
    load_markdown_document,
    markdown_document_from_docbase,
    write_document_id,
    write_markdown_document,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="dogbass")
    subparsers = parser.add_subparsers(dest="command", required=True)

    push_parser = subparsers.add_parser(
        "push",
        aliases=["update"],
        help="Create or update a DocBase document from a Markdown file.",
    )
    push_parser.add_argument("markdown_file", help="Path to the Markdown file to sync.")

    pull_parser = subparsers.add_parser(
        "pull", help="Fetch a DocBase document into a Markdown file."
    )
    pull_parser.add_argument(
        "markdown_file", help="Path to the Markdown file to refresh from DocBase."
    )

    return parser


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


def pull_markdown_file(markdown_path: Path, client: DocBaseClient) -> int:
    document_id = load_document_id(markdown_path)
    payload = client.get_post(document_id)
    document = markdown_document_from_docbase(markdown_path, payload, document_id)
    write_markdown_document(document)
    print(f"Pulled DocBase post {document_id} into {markdown_path}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    client = DocBaseClient.from_env()

    if args.command in {"push", "update"}:
        return push_markdown_file(Path(args.markdown_file), client)
    if args.command == "pull":
        return pull_markdown_file(Path(args.markdown_file), client)

    parser.error(f"Unsupported command: {args.command}")
    return 2
