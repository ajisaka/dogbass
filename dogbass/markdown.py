from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import frontmatter  # type: ignore[import-untyped]


@dataclass(slots=True)
class MarkdownDocument:
    path: Path
    title: str
    body: str
    tags: list[str]
    draft: bool
    document_id: int | None

    def to_docbase_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "title": self.title,
            "body": self.body,
            "draft": self.draft,
        }
        if self.tags:
            payload["tags"] = self.tags
        return payload


def create_markdown_document(path: Path, title: str) -> None:
    if path.exists():
        raise FileExistsError(path)
    if not title.strip():
        raise ValueError("Title must not be empty")

    document = MarkdownDocument(
        path=path,
        title=title.strip(),
        body="",
        tags=[],
        draft=True,
        document_id=None,
    )
    write_markdown_document(document)


def load_document_id(path: Path) -> int:
    if path.suffix != ".md":
        raise ValueError(f"Expected a Markdown file (*.md): {path}")
    if not path.exists():
        raise FileNotFoundError(path)

    post = frontmatter.load(path)
    document_id = _normalize_document_id(post.metadata.get("id"))
    if document_id is None:
        raise ValueError("Markdown front matter must include an 'id' for pull")
    return document_id


def load_markdown_document(path: Path) -> MarkdownDocument:
    if path.suffix != ".md":
        raise ValueError(f"Expected a Markdown file (*.md): {path}")
    if not path.exists():
        raise FileNotFoundError(path)

    post = frontmatter.load(path)
    title = post.metadata.get("title")
    if not isinstance(title, str) or not title.strip():
        raise ValueError("Markdown front matter must include a non-empty 'title'")

    tags = _normalize_tags(post.metadata.get("tags"))
    draft = _normalize_draft(post.metadata.get("draft"))
    document_id = _normalize_document_id(post.metadata.get("id"))

    return MarkdownDocument(
        path=path,
        title=title.strip(),
        body=post.content,
        tags=tags,
        draft=draft,
        document_id=document_id,
    )


def write_document_id(path: Path, document_id: int) -> None:
    post = frontmatter.load(path)
    post.metadata["id"] = document_id
    path.write_text(_render_post(path, post), encoding="utf-8", newline="")


def write_markdown_document(document: MarkdownDocument) -> None:
    metadata = {
        "title": document.title,
        "tags": document.tags,
        "draft": document.draft,
    }
    if document.document_id is not None:
        metadata["id"] = document.document_id

    post = frontmatter.Post(document.body, **metadata)
    if document.path.exists():
        rendered = _render_post(document.path, post)
    else:
        rendered = _normalize_newlines(frontmatter.dumps(post))
        if not rendered.endswith("\n"):
            rendered = f"{rendered}\n"
    document.path.write_text(rendered, encoding="utf-8", newline="")


def markdown_document_from_docbase(
    path: Path, payload: dict[str, Any], document_id: int
) -> MarkdownDocument:
    title = payload.get("title")
    body = payload.get("body")
    draft = payload.get("draft")
    tags_payload = payload.get("tags")

    if not isinstance(title, str) or not title.strip():
        raise ValueError("DocBase response did not include a valid 'title'")
    if not isinstance(body, str):
        raise ValueError("DocBase response did not include a valid 'body'")
    if not isinstance(draft, bool):
        raise ValueError("DocBase response did not include a valid 'draft'")
    if not isinstance(tags_payload, list):
        raise ValueError("DocBase response did not include a valid 'tags'")

    tags: list[str] = []
    for tag in tags_payload:
        if not isinstance(tag, dict):
            raise ValueError("DocBase response included an invalid tag entry")
        name = tag.get("name")
        if not isinstance(name, str) or not name.strip():
            raise ValueError("DocBase response included an invalid tag name")
        tags.append(name.strip())

    return MarkdownDocument(
        path=path,
        title=title.strip(),
        body=body,
        tags=tags,
        draft=draft,
        document_id=document_id,
    )


def _normalize_tags(raw_tags: Any) -> list[str]:
    if raw_tags is None:
        return []
    if not isinstance(raw_tags, list):
        raise ValueError("Markdown front matter 'tags' must be a list")

    normalized_tags: list[str] = []
    for tag in raw_tags:
        if not isinstance(tag, str) or not tag.strip():
            raise ValueError("Each tag must be a non-empty string")
        normalized_tags.append(tag.strip())
    return normalized_tags


def _normalize_draft(raw_draft: Any) -> bool:
    if raw_draft is None:
        return False
    if not isinstance(raw_draft, bool):
        raise ValueError("Markdown front matter 'draft' must be a boolean")
    return raw_draft


def _normalize_document_id(raw_document_id: Any) -> int | None:
    if raw_document_id is None:
        return None
    if isinstance(raw_document_id, int):
        return raw_document_id
    if isinstance(raw_document_id, str) and raw_document_id.isdigit():
        return int(raw_document_id)
    raise ValueError("Markdown front matter 'id' must be an integer when present")


def _render_post(path: Path, post: frontmatter.Post) -> str:
    rendered = _normalize_newlines(frontmatter.dumps(post))
    newline, had_trailing_newline = _detect_newline_style(path)

    if newline != "\n":
        rendered = rendered.replace("\n", newline)

    if had_trailing_newline and not rendered.endswith(newline):
        rendered = f"{rendered}{newline}"
    if not had_trailing_newline and rendered.endswith(newline):
        rendered = rendered[: -len(newline)]

    return rendered


def _detect_newline_style(path: Path) -> tuple[str, bool]:
    content = path.read_bytes()

    if b"\r\n" in content:
        newline = "\r\n"
    elif b"\n" in content:
        newline = "\n"
    elif b"\r" in content:
        newline = "\r"
    else:
        newline = "\n"

    had_trailing_newline = content.endswith((b"\r\n", b"\n", b"\r"))
    return newline, had_trailing_newline


def _normalize_newlines(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")
