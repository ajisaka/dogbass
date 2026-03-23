from __future__ import annotations

import argparse
from pathlib import Path

from dogbass.docbase import DocBaseClient
from dogbass.markdown import load_markdown_document, write_document_id


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="dogbass")
    subparsers = parser.add_subparsers(dest="command", required=True)

    update_parser = subparsers.add_parser(
        "update", help="Create or update a DocBase document from a Markdown file."
    )
    update_parser.add_argument(
        "markdown_file", help="Path to the Markdown file to sync."
    )

    return parser


def sync_markdown_file(markdown_path: Path, client: DocBaseClient) -> int:
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


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "update":
        client = DocBaseClient.from_env()
        return sync_markdown_file(Path(args.markdown_file), client)

    parser.error(f"Unsupported command: {args.command}")
    return 2
