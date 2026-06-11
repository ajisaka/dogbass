# `dogbass init` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `dogbass init <file>` subcommand that prepends dogbass YAML Front Matter (with template comments) to an existing plain file, using `Path.stem` as the title and preserving the original body bytes and newline style.

**Architecture:** Add a small helper `_has_front_matter` and a new public function `init_markdown_document` to `dogbass/markdown.py`. Reuse the existing template-comment renderer (`_render_new_document`) for the FM block, then post-process to keep the original file's newline style. Wire a thin `init_command` in `dogbass/cli.py` that mirrors `new_command`'s best-effort `DocBaseClient.list_groups()` pattern.

**Tech Stack:** Python 3.12, `click`, `python-frontmatter`, `ruamel.yaml`, `unittest` + `click.testing.CliRunner`, `uv`.

**Reference spec:** `docs/superpowers/specs/2026-06-11-dogbass-init-design.md`

---

## File Structure

- Modify: `dogbass/markdown.py` — add `_has_front_matter(text: str) -> bool` and `init_markdown_document(path, title, available_groups=None) -> None`.
- Modify: `dogbass/cli.py` — add `@main.command("init")` and the `init_command` handler.
- Modify: `tests/test_cli.py` — add unit tests for `init_markdown_document` and integration tests for the CLI.

No new files. No deletions.

---

## Task 1: Add `_has_front_matter` helper

**Files:**
- Modify: `dogbass/markdown.py` (add a new private helper near `_extract_raw_front_matter_yaml`)
- Modify: `tests/test_cli.py` (add tests)

This helper answers "does this text already have a YAML front matter block?" using the same parsing rules as `_extract_raw_front_matter_yaml`: LF-normalize, require leading `---\n`, require a closing `---` line afterward.

- [ ] **Step 1: Write failing tests for `_has_front_matter`**

Add to `tests/test_cli.py` (alongside existing tests; import is the new line):

```python
from dogbass.markdown import _has_front_matter, create_markdown_document, load_markdown_document
```

```python
    def test_has_front_matter_detects_lf_block(self) -> None:
        text = "---\ntitle: x\n---\n\nbody\n"
        self.assertTrue(_has_front_matter(text))

    def test_has_front_matter_detects_crlf_block(self) -> None:
        text = "---\r\ntitle: x\r\n---\r\n\r\nbody\r\n"
        self.assertTrue(_has_front_matter(text))

    def test_has_front_matter_rejects_plain_text(self) -> None:
        self.assertFalse(_has_front_matter("# Heading\n\nbody\n"))

    def test_has_front_matter_rejects_empty_text(self) -> None:
        self.assertFalse(_has_front_matter(""))

    def test_has_front_matter_rejects_unterminated_marker(self) -> None:
        self.assertFalse(_has_front_matter("---\ntitle: x\nbody without closing marker\n"))

    def test_has_front_matter_rejects_horizontal_rule(self) -> None:
        # A markdown horizontal rule mid-document is not front matter.
        self.assertFalse(_has_front_matter("# Title\n\n---\n\nbody\n"))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run python -m unittest tests.test_cli -v 2>&1 | grep -E "(has_front_matter|FAIL|ERROR)"`
Expected: ImportError on `_has_front_matter` (the symbol does not yet exist).

- [ ] **Step 3: Implement `_has_front_matter` in `dogbass/markdown.py`**

Insert this helper directly above `_extract_raw_front_matter_yaml` so they sit next to each other:

```python
def _has_front_matter(content: str) -> bool:
    """Return True iff ``content`` starts with a closed YAML front matter block."""
    normalized = content.replace("\r\n", "\n").replace("\r", "\n")
    if not normalized.startswith("---\n"):
        return False
    rest = normalized[4:]
    return re.search(r"(?m)^---(?:\n|$)", rest) is not None
```

- [ ] **Step 4: Run the new tests to verify they pass**

Run: `uv run python -m unittest tests.test_cli -v 2>&1 | grep "has_front_matter"`
Expected: all six `test_has_front_matter_*` cases report `ok`.

- [ ] **Step 5: Run the full lint + test suite**

Run: `uv run ruff check . && uv run mypy . && uv run python -m unittest discover -s tests`
Expected: no lint errors, no type errors, all tests pass.

- [ ] **Step 6: Commit**

```bash
git add dogbass/markdown.py tests/test_cli.py
git commit -m "feat(markdown): add _has_front_matter helper"
```

---

## Task 2: Add `init_markdown_document` to `dogbass/markdown.py`

**Files:**
- Modify: `dogbass/markdown.py` (add the new public function near `create_markdown_document`)
- Modify: `tests/test_cli.py` (add unit tests)

This function is the core of the feature. It validates the path, refuses files that already have front matter, builds a `MarkdownDocument` whose body is the file's original content (LF-normalized internally), renders the FM block with template comments via `_render_new_document`, then restores the file's original newline style and trailing-newline state.

### 2a. Happy path on LF body

- [ ] **Step 1: Write the failing test for an LF body**

Add to `tests/test_cli.py`:

```python
    def test_init_markdown_document_adds_front_matter_to_plain_lf_file(self) -> None:
        from dogbass.markdown import init_markdown_document

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "notes.md"
            path.write_text("# Heading\n\nHello world.\n", encoding="utf-8")

            init_markdown_document(path, "notes")

            document = load_markdown_document(path)
            self.assertEqual(document.title, "notes")
            self.assertTrue(document.draft)
            self.assertTrue(document.notice)
            self.assertEqual(document.scope, "private")
            self.assertEqual(document.tags, [])
            self.assertEqual(document.groups, [])
            self.assertIsNone(document.document_id)
            self.assertIn("# Heading", document.body)
            self.assertIn("Hello world.", document.body)
            content = path.read_text(encoding="utf-8")
            self.assertTrue(content.startswith("---\n"))
            self.assertIn("# notice: false", content)
            self.assertIn("# scope: everyone", content)
            self.assertIn("# scope: group", content)
            self.assertIn("# groups: [123]  # required when scope is group", content)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run python -m unittest tests.test_cli.DogbassTests.test_init_markdown_document_adds_front_matter_to_plain_lf_file -v`
Expected: `ImportError: cannot import name 'init_markdown_document'`.

- [ ] **Step 3: Implement `init_markdown_document`**

Add this function to `dogbass/markdown.py`, immediately after `create_markdown_document`:

```python
def init_markdown_document(
    path: Path,
    title: str,
    available_groups: list[dict[str, Any]] | None = None,
) -> None:
    if not path.exists() or not path.is_file():
        raise ValidationError(f"file not found: {path}")
    if not title.strip():
        raise ValidationError("title must not be empty")

    raw_bytes = path.read_bytes()
    raw_text = raw_bytes.decode("utf-8")
    if _has_front_matter(raw_text):
        raise FileConflictError(f"file already has front matter: {path}")

    if b"\r\n" in raw_bytes:
        newline = "\r\n"
    elif b"\n" in raw_bytes:
        newline = "\n"
    elif b"\r" in raw_bytes:
        newline = "\r"
    else:
        newline = "\n"
    had_trailing_newline = raw_bytes.endswith((b"\r\n", b"\n", b"\r"))

    body = raw_text.replace("\r\n", "\n").replace("\r", "\n")

    document = MarkdownDocument(
        path=path,
        title=title.strip(),
        body=body,
        tags=[],
        draft=True,
        notice=True,
        scope="private",
        groups=[],
        document_id=None,
    )
    metadata = {
        "title": document.title,
        "tags": document.tags,
        "draft": document.draft,
        "notice": document.notice,
        "scope": document.scope,
    }
    post = frontmatter.Post(document.body, **metadata)
    rendered = _render_new_document(post, document, available_groups)

    if newline != "\n":
        rendered = rendered.replace("\n", newline)
    if had_trailing_newline and not rendered.endswith(newline):
        rendered = f"{rendered}{newline}"
    if not had_trailing_newline and rendered.endswith(newline):
        rendered = rendered[: -len(newline)]

    path.write_text(rendered, encoding="utf-8", newline="")
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run python -m unittest tests.test_cli.DogbassTests.test_init_markdown_document_adds_front_matter_to_plain_lf_file -v`
Expected: PASS.

### 2b. CRLF preservation

- [ ] **Step 5: Write the failing CRLF test**

Add to `tests/test_cli.py`:

```python
    def test_init_markdown_document_preserves_crlf_newlines(self) -> None:
        from dogbass.markdown import init_markdown_document

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "crlf.md"
            path.write_bytes(b"# Heading\r\n\r\nHello.\r\n")

            init_markdown_document(path, "crlf")

            content = path.read_bytes()
            self.assertIn(b"\r\n", content)
            self.assertNotIn(b"\r\r\n", content)
            self.assertTrue(content.startswith(b"---\r\n"))
            self.assertTrue(content.endswith(b"\r\n"))
            self.assertIn(b"# Heading\r\n", content)
```

- [ ] **Step 6: Run the test to verify it passes**

Run: `uv run python -m unittest tests.test_cli.DogbassTests.test_init_markdown_document_preserves_crlf_newlines -v`
Expected: PASS (the implementation in 2a already handles this).

### 2c. Already-has-front-matter is rejected

- [ ] **Step 7: Write the failing rejection test**

Add to `tests/test_cli.py`:

```python
    def test_init_markdown_document_rejects_file_with_existing_front_matter(self) -> None:
        from dogbass.markdown import init_markdown_document
        from dogbass.errors import FileConflictError

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "already.md"
            original = "---\ntitle: x\n---\n\nbody\n"
            path.write_text(original, encoding="utf-8")

            with self.assertRaises(FileConflictError):
                init_markdown_document(path, "already")

            self.assertEqual(path.read_text(encoding="utf-8"), original)
```

- [ ] **Step 8: Run the test to verify it passes**

Run: `uv run python -m unittest tests.test_cli.DogbassTests.test_init_markdown_document_rejects_file_with_existing_front_matter -v`
Expected: PASS (implementation already raises `FileConflictError`).

### 2d. Missing file and empty title

- [ ] **Step 9: Write the failing validation tests**

Add to `tests/test_cli.py`:

```python
    def test_init_markdown_document_rejects_missing_file(self) -> None:
        from dogbass.markdown import init_markdown_document
        from dogbass.errors import ValidationError

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "does-not-exist.md"

            with self.assertRaises(ValidationError):
                init_markdown_document(path, "anything")

    def test_init_markdown_document_rejects_empty_title(self) -> None:
        from dogbass.markdown import init_markdown_document
        from dogbass.errors import ValidationError

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "notes.md"
            path.write_text("body\n", encoding="utf-8")

            with self.assertRaises(ValidationError):
                init_markdown_document(path, "   ")
```

- [ ] **Step 10: Run the tests to verify they pass**

Run: `uv run python -m unittest tests.test_cli.DogbassTests.test_init_markdown_document_rejects_missing_file tests.test_cli.DogbassTests.test_init_markdown_document_rejects_empty_title -v`
Expected: PASS.

### 2e. Lint and commit

- [ ] **Step 11: Run lint + mypy + full test suite**

Run: `uv run ruff check . && uv run mypy . && uv run python -m unittest discover -s tests`
Expected: no errors, all tests pass.

- [ ] **Step 12: Commit**

```bash
git add dogbass/markdown.py tests/test_cli.py
git commit -m "feat(markdown): add init_markdown_document to attach front matter to existing files"
```

---

## Task 3: Wire `init` subcommand into the CLI

**Files:**
- Modify: `dogbass/cli.py` (import the new function, register the new command)
- Modify: `tests/test_cli.py` (integration tests against `main`)

### 3a. Integration test: happy path on .md file

- [ ] **Step 1: Write the failing CLI test**

Add to `tests/test_cli.py`:

```python
    def test_main_supports_init_command_on_md_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "Existing Notes.md"
            path.write_text("Hello world.\n", encoding="utf-8")
            fake_client = FakeDocBaseClient()

            with patch("dogbass.cli.DocBaseClient.from_env", return_value=fake_client):
                result = self.runner.invoke(main, ["init", str(path)])

            self.assertEqual(result.exit_code, 0)
            self.assertIn("Initialized front matter in", result.output)
            document = load_markdown_document(path)
            self.assertEqual(document.title, "Existing Notes")
            self.assertTrue(document.draft)
            self.assertEqual(document.scope, "private")
            self.assertIn("Hello world.", document.body)
            content = path.read_text(encoding="utf-8")
            self.assertIn(
                "# groups:\n#   - 1  # DocBase\n#   - 2  # engineering", content
            )
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run python -m unittest tests.test_cli.DogbassTests.test_main_supports_init_command_on_md_file -v`
Expected: FAIL with `No such command 'init'`.

- [ ] **Step 3: Register the `init` command in `dogbass/cli.py`**

Update the import block at the top of `dogbass/cli.py` (the existing `from dogbass.markdown import (...)` block):

```python
from dogbass.markdown import (
    create_markdown_document,
    init_markdown_document,
    is_dogbass_markdown,
    load_document_id,
    load_markdown_document,
    markdown_document_from_docbase,
    render_new_markdown_content,
    write_document_id,
    write_markdown_document,
)
```

Append this new command at the bottom of `dogbass/cli.py`, after `sync_commit_command`:

```python
@main.command("init")
@click.argument(
    "file",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
)
@app_error_handler
def init_command(file: Path) -> None:
    """Add dogbass front matter to an existing file (title from filename stem)."""
    title = file.stem
    if not title.strip():
        raise ValidationError("filename must have a non-empty stem")
    available_groups: list[dict[str, Any]] = []
    try:
        client = DocBaseClient.from_env()
        available_groups = client.list_groups()
    except AppError:
        pass
    init_markdown_document(file, title, available_groups=available_groups)
    click.echo(f"Initialized front matter in {file}")
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run python -m unittest tests.test_cli.DogbassTests.test_main_supports_init_command_on_md_file -v`
Expected: PASS.

### 3b. Integration test: extension other than .md

- [ ] **Step 5: Write the failing test for a `.txt` file**

Add to `tests/test_cli.py`:

```python
    def test_main_init_command_works_on_non_md_extension(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "notes.txt"
            path.write_text("plain text body\n", encoding="utf-8")
            previous_domain = os.environ.pop("DOCBASE_DOMAIN", None)
            previous_token = os.environ.pop("DOCBASE_TOKEN", None)
            self.addCleanup(_restore_env_var, "DOCBASE_DOMAIN", previous_domain)
            self.addCleanup(_restore_env_var, "DOCBASE_TOKEN", previous_token)

            result = self.runner.invoke(main, ["init", str(path)])

            self.assertEqual(result.exit_code, 0)
            content = path.read_text(encoding="utf-8")
            self.assertTrue(content.startswith("---\n"))
            self.assertIn("title: notes", content)
            self.assertIn("plain text body", content)
            # Without DocBase credentials, falls back to the simple groups hint.
            self.assertIn("# groups: [123]  # required when scope is group", content)
```

- [ ] **Step 6: Run the test to verify it passes**

Run: `uv run python -m unittest tests.test_cli.DogbassTests.test_main_init_command_works_on_non_md_extension -v`
Expected: PASS.

### 3c. Integration test: file with no extension

- [ ] **Step 7: Write the failing test for an extensionless file**

Add to `tests/test_cli.py`:

```python
    def test_main_init_command_works_on_extensionless_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "README"
            path.write_text("plain readme\n", encoding="utf-8")
            previous_domain = os.environ.pop("DOCBASE_DOMAIN", None)
            previous_token = os.environ.pop("DOCBASE_TOKEN", None)
            self.addCleanup(_restore_env_var, "DOCBASE_DOMAIN", previous_domain)
            self.addCleanup(_restore_env_var, "DOCBASE_TOKEN", previous_token)

            result = self.runner.invoke(main, ["init", str(path)])

            self.assertEqual(result.exit_code, 0)
            content = path.read_text(encoding="utf-8")
            self.assertIn("title: README", content)
            self.assertIn("plain readme", content)
```

- [ ] **Step 8: Run the test to verify it passes**

Run: `uv run python -m unittest tests.test_cli.DogbassTests.test_main_init_command_works_on_extensionless_file -v`
Expected: PASS.

### 3d. Integration test: refuses existing front matter

- [ ] **Step 9: Write the failing rejection test**

Add to `tests/test_cli.py`:

```python
    def test_main_init_command_refuses_file_with_existing_front_matter(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "already.md"
            original = "---\ntitle: x\n---\n\nbody\n"
            path.write_text(original, encoding="utf-8")
            previous_domain = os.environ.pop("DOCBASE_DOMAIN", None)
            previous_token = os.environ.pop("DOCBASE_TOKEN", None)
            self.addCleanup(_restore_env_var, "DOCBASE_DOMAIN", previous_domain)
            self.addCleanup(_restore_env_var, "DOCBASE_TOKEN", previous_token)

            result = self.runner.invoke(main, ["init", str(path)])

            self.assertEqual(result.exit_code, 1)
            self.assertIn("Error: file already has front matter", result.output)
            self.assertEqual(path.read_text(encoding="utf-8"), original)
```

- [ ] **Step 10: Run the test to verify it passes**

Run: `uv run python -m unittest tests.test_cli.DogbassTests.test_main_init_command_refuses_file_with_existing_front_matter -v`
Expected: PASS.

### 3e. Integration test: refuses missing file (Click usage error)

- [ ] **Step 11: Write the failing test for a missing file**

Add to `tests/test_cli.py`:

```python
    def test_main_init_command_rejects_missing_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            missing = Path(tmpdir) / "missing.md"

            result = self.runner.invoke(main, ["init", str(missing)])

            self.assertNotEqual(result.exit_code, 0)
            self.assertIn("does not exist", result.output)
```

- [ ] **Step 12: Run the test to verify it passes**

Run: `uv run python -m unittest tests.test_cli.DogbassTests.test_main_init_command_rejects_missing_file -v`
Expected: PASS. Click's `Path(exists=True)` produces the "does not exist" message and a non-zero exit code automatically.

### 3f. Final verification and commit

- [ ] **Step 13: Run the full lint + type + test suite**

Run: `uv run ruff check . && uv run mypy . && uv run python -m unittest discover -s tests`
Expected: no errors, all tests pass.

- [ ] **Step 14: Smoke test the CLI end-to-end**

```bash
TMP=$(mktemp -d)
printf '# Note\n\nbody\n' > "$TMP/example.md"
uv run dogbass init "$TMP/example.md"
cat "$TMP/example.md"
rm -rf "$TMP"
```

Expected output from `cat` (the body follows the closing `---` directly — `python-frontmatter` does not add a blank line between them):

```
---
title: example
tags: []
draft: true
notice: true
# notice: false
scope: private
# scope: everyone
# scope: group
# groups: [123]  # required when scope is group
---
# Note

body
```

(If `DOCBASE_DOMAIN` and `DOCBASE_TOKEN` are set and reachable, the `# groups:` block will list real group IDs instead of the placeholder; that is also acceptable.)

- [ ] **Step 15: Commit**

```bash
git add dogbass/cli.py tests/test_cli.py
git commit -m "feat(cli): add \`init\` command to attach front matter to plain files"
```

---

## Done Criteria

- `uv run dogbass --help` lists `init` as a subcommand.
- `uv run dogbass init <file>` rewrites `<file>` with a dogbass front matter block, original body intact, original newline style preserved.
- Title is `<file>.stem` (e.g. `notes.md` → `notes`, `README` → `README`).
- Running `init` on a file that already has front matter exits non-zero and leaves the file unmodified.
- `uv run ruff check .`, `uv run mypy .`, and `uv run python -m unittest discover -s tests` all succeed.
