from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import frontmatter  # type: ignore[import-untyped]

from dogbass.errors import DocBaseResponseError, FileConflictError, ValidationError


@dataclass(slots=True)
class MarkdownDocument:
    path: Path
    title: str
    body: str
    tags: list[str]
    draft: bool
    notice: bool | None
    scope: str | None
    groups: list[int]
    document_id: int | None

    def to_docbase_payload(
        self,
        *,
        default_scope: str | None = None,
        notice_override: bool | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "title": self.title,
            "body": self.body,
            "draft": self.draft,
        }
        notice = self.notice if notice_override is None else notice_override
        if notice is not None:
            payload["notice"] = notice
        if self.tags:
            payload["tags"] = self.tags
        scope = self.scope if self.scope is not None else default_scope
        if scope is not None:
            payload["scope"] = scope
            if scope == "group":
                payload["groups"] = self.groups
        return payload


def create_markdown_document(path: Path, title: str) -> None:
    if path.exists():
        raise FileConflictError(f"file already exists: {path}")
    if not title.strip():
        raise ValidationError("title must not be empty")

    document = MarkdownDocument(
        path=path,
        title=title.strip(),
        body="",
        tags=[],
        draft=True,
        notice=True,
        scope="private",
        groups=[],
        document_id=None,
    )
    write_markdown_document(document)


def load_document_id(path: Path) -> int:
    if path.suffix != ".md":
        raise ValidationError(f"expected a Markdown file: {path}")
    if not path.exists():
        raise ValidationError(f"file not found: {path}")

    post = frontmatter.load(path)
    document_id = _normalize_document_id(post.metadata.get("id"))
    if document_id is None:
        raise ValidationError("missing document id in front matter")
    return document_id


def load_markdown_document(path: Path) -> MarkdownDocument:
    if path.suffix != ".md":
        raise ValidationError(f"expected a Markdown file: {path}")
    if not path.exists():
        raise ValidationError(f"file not found: {path}")

    post = frontmatter.load(path)
    title = post.metadata.get("title")
    if not isinstance(title, str) or not title.strip():
        raise ValidationError("missing title in front matter")

    tags = _normalize_tags(post.metadata.get("tags"))
    draft = _normalize_draft(post.metadata.get("draft"))
    notice = _normalize_notice(post.metadata.get("notice"))
    scope = _normalize_scope(post.metadata.get("scope"))
    groups = _normalize_groups(post.metadata.get("groups"))
    document_id = _normalize_document_id(post.metadata.get("id"))
    _validate_scope_groups(scope, groups)

    return MarkdownDocument(
        path=path,
        title=title.strip(),
        body=post.content,
        tags=tags,
        draft=draft,
        notice=notice,
        scope=scope,
        groups=groups,
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
    if document.notice is not None:
        metadata["notice"] = document.notice
    if document.scope is not None:
        metadata["scope"] = document.scope
    if document.scope == "group":
        metadata["groups"] = document.groups
    if document.document_id is not None:
        metadata["id"] = document.document_id

    post = frontmatter.Post(document.body, **metadata)
    if document.path.exists():
        rendered = _render_post(document.path, post)
    else:
        rendered = _normalize_newlines(frontmatter.dumps(post))
        rendered = _insert_template_comments(rendered, document)
        if not rendered.endswith("\n"):
            rendered = f"{rendered}\n"
    document.path.write_text(rendered, encoding="utf-8", newline="")


def markdown_document_from_docbase(
    path: Path,
    payload: dict[str, Any],
    document_id: int,
    notice: bool | None = None,
) -> MarkdownDocument:
    title = payload.get("title")
    body = payload.get("body")
    draft = payload.get("draft")
    tags_payload = payload.get("tags")
    scope = _normalize_scope(payload.get("scope"))
    groups = _normalize_docbase_groups(payload.get("groups"))

    if not isinstance(title, str) or not title.strip():
        raise DocBaseResponseError("DocBase response is missing title")
    if not isinstance(body, str):
        raise DocBaseResponseError("DocBase response is missing body")
    if not isinstance(draft, bool):
        raise DocBaseResponseError("DocBase response is missing draft")
    if not isinstance(tags_payload, list):
        raise DocBaseResponseError("DocBase response is missing tags")
    _validate_scope_groups(scope, groups)

    tags: list[str] = []
    for tag in tags_payload:
        if not isinstance(tag, dict):
            raise DocBaseResponseError("DocBase response includes an invalid tag")
        name = tag.get("name")
        if not isinstance(name, str) or not name.strip():
            raise DocBaseResponseError("DocBase response includes an invalid tag")
        tags.append(name.strip())

    return MarkdownDocument(
        path=path,
        title=title.strip(),
        body=body,
        tags=tags,
        draft=draft,
        notice=notice,
        scope=scope,
        groups=groups,
        document_id=document_id,
    )


def _normalize_tags(raw_tags: Any) -> list[str]:
    if raw_tags is None:
        return []
    if not isinstance(raw_tags, list):
        raise ValidationError("front matter 'tags' must be a list")

    normalized_tags: list[str] = []
    for tag in raw_tags:
        if not isinstance(tag, str) or not tag.strip():
            raise ValidationError("front matter 'tags' must contain non-empty strings")
        normalized_tags.append(tag.strip())
    return normalized_tags


def _normalize_draft(raw_draft: Any) -> bool:
    if raw_draft is None:
        return False
    if not isinstance(raw_draft, bool):
        raise ValidationError("front matter 'draft' must be true or false")
    return raw_draft


def _normalize_notice(raw_notice: Any) -> bool | None:
    if raw_notice is None:
        return None
    if not isinstance(raw_notice, bool):
        raise ValidationError("front matter 'notice' must be true or false")
    return raw_notice


def _normalize_document_id(raw_document_id: Any) -> int | None:
    if raw_document_id is None:
        return None
    if isinstance(raw_document_id, int):
        return raw_document_id
    if isinstance(raw_document_id, str) and raw_document_id.isdigit():
        return int(raw_document_id)
    raise ValidationError("front matter 'id' must be an integer")


def _normalize_scope(raw_scope: Any) -> str | None:
    if raw_scope is None:
        return None
    if not isinstance(raw_scope, str):
        raise ValidationError("front matter 'scope' must be a string")

    normalized_scope = raw_scope.strip()
    if normalized_scope not in {"private", "everyone", "group"}:
        raise ValidationError(
            "front matter 'scope' must be private, everyone, or group"
        )
    return normalized_scope


def _normalize_groups(raw_groups: Any) -> list[int]:
    if raw_groups is None:
        return []
    if not isinstance(raw_groups, list):
        raise ValidationError("front matter 'groups' must be a list")

    groups: list[int] = []
    for group in raw_groups:
        if isinstance(group, int):
            groups.append(group)
            continue
        if isinstance(group, str) and group.isdigit():
            groups.append(int(group))
            continue
        raise ValidationError("front matter 'groups' must contain integers")
    return groups


def _normalize_docbase_groups(raw_groups: Any) -> list[int]:
    if raw_groups is None:
        return []
    if not isinstance(raw_groups, list):
        raise DocBaseResponseError("DocBase response is missing groups")

    groups: list[int] = []
    for group in raw_groups:
        if not isinstance(group, dict):
            raise DocBaseResponseError("DocBase response includes an invalid group")
        group_id = group.get("id")
        if not isinstance(group_id, int):
            raise DocBaseResponseError("DocBase response includes an invalid group")
        groups.append(group_id)
    return groups


def _validate_scope_groups(scope: str | None, groups: list[int]) -> None:
    if scope == "group" and not groups:
        raise ValidationError("front matter 'groups' is required when scope is group")
    if scope != "group" and groups:
        raise ValidationError(
            "front matter 'groups' can only be used when scope is group"
        )


def _insert_template_comments(rendered: str, document: MarkdownDocument) -> str:
    if document.notice is not None:
        notice_line = f"notice: {'true' if document.notice else 'false'}\n"
        commented_notice = (
            f"notice: {'true' if document.notice else 'false'}\n"
            f"# notice: {'false' if document.notice else 'true'}\n"
        )
        rendered = rendered.replace(notice_line, commented_notice, 1)

    if document.scope is not None:
        scope_line = f"scope: {document.scope}\n"
        commented_scope = (
            f"scope: {document.scope}\n"
            "# scope: everyone\n"
            "# scope: group\n"
            "# groups: [123]  # required when scope is group\n"
        )
        rendered = rendered.replace(scope_line, commented_scope, 1)

    return rendered


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
