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
    path.write_text(frontmatter.dumps(post), encoding="utf-8")


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
