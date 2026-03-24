from __future__ import annotations

import io
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner

from dogbass.cli import main, new_markdown_file, pull_markdown_file, push_markdown_file
from dogbass.docbase import DocBaseClient
from dogbass.errors import DocBaseRequestError
from dogbass.markdown import create_markdown_document, load_markdown_document


class FakeDocBaseClient(DocBaseClient):
    def __init__(self) -> None:
        super().__init__(domain="example", token="secret")
        self.created_payloads: list[dict[str, object]] = []
        self.updated_payloads: list[tuple[int, dict[str, object]]] = []

    def create_post(self, payload: dict[str, object]) -> dict[str, object]:
        self.created_payloads.append(payload)
        return {"id": 42}

    def update_post(
        self, post_id: int, payload: dict[str, object]
    ) -> dict[str, object]:
        self.updated_payloads.append((post_id, payload))
        return {"id": post_id}

    def get_post(self, post_id: int) -> dict[str, object]:
        return {
            "id": post_id,
            "title": "Pulled Post",
            "body": "Pulled body",
            "draft": True,
            "tags": [{"name": "remote"}, {"name": "docbase"}],
        }


class DogbassTests(unittest.TestCase):
    def setUp(self) -> None:
        self.runner = CliRunner()

    def test_create_markdown_document_uses_draft_true_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "new.md"

            create_markdown_document(path, "Fresh Document")

            document = load_markdown_document(path)
            self.assertEqual(document.title, "Fresh Document")
            self.assertTrue(document.draft)
            self.assertEqual(document.tags, [])
            self.assertIsNone(document.document_id)
            self.assertEqual(document.body, "")

    def test_new_markdown_file_prompts_until_non_empty_title(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "prompted.md"
            output = io.StringIO()

            with (
                patch("dogbass.cli.click.prompt", side_effect=["", "Prompted Title"]),
                redirect_stdout(output),
            ):
                exit_code = new_markdown_file(path)

            self.assertEqual(exit_code, 0)
            self.assertIn("Title must not be empty.", output.getvalue())
            document = load_markdown_document(path)
            self.assertEqual(document.title, "Prompted Title")
            self.assertTrue(document.draft)

    def test_main_supports_new_command_without_docbase_env(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "new-command.md"
            previous_domain = os.environ.pop("DOCBASE_DOMAIN", None)
            previous_token = os.environ.pop("DOCBASE_TOKEN", None)
            self.addCleanup(_restore_env_var, "DOCBASE_DOMAIN", previous_domain)
            self.addCleanup(_restore_env_var, "DOCBASE_TOKEN", previous_token)

            result = self.runner.invoke(
                main, ["new", str(path)], input="CLI New Title\n"
            )

            self.assertEqual(result.exit_code, 0)
            self.assertIn("Created Markdown file", result.output)
            document = load_markdown_document(path)
            self.assertEqual(document.title, "CLI New Title")
            self.assertTrue(document.draft)

    def test_load_markdown_document_reads_expected_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "sample.md"
            path.write_text(
                "---\n"
                "title: Test Title\n"
                "tags: [alpha, beta]\n"
                "draft: true\n"
                "id: 123\n"
                "---\n"
                "\n"
                "Hello DocBase!\n",
                encoding="utf-8",
            )

            document = load_markdown_document(path)

            self.assertEqual(document.title, "Test Title")
            self.assertEqual(document.tags, ["alpha", "beta"])
            self.assertTrue(document.draft)
            self.assertEqual(document.document_id, 123)
            self.assertIn("Hello DocBase!", document.body)

    def test_push_markdown_file_creates_post_and_writes_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "new-post.md"
            path.write_text(
                "---\ntitle: New Post\ntags: [docs]\ndraft: false\n---\n\nPost body\n",
                encoding="utf-8",
            )
            client = FakeDocBaseClient()

            exit_code = push_markdown_file(path, client)

            self.assertEqual(exit_code, 0)
            self.assertEqual(
                client.created_payloads,
                [
                    {
                        "title": "New Post",
                        "body": "Post body",
                        "draft": False,
                        "tags": ["docs"],
                    }
                ],
            )
            self.assertEqual(client.updated_payloads, [])
            updated_text = path.read_text(encoding="utf-8")
            self.assertIn("id: 42", updated_text)

    def test_push_markdown_file_updates_existing_post(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "existing-post.md"
            path.write_text(
                "---\n"
                "title: Existing Post\n"
                "tags: [docs]\n"
                "draft: false\n"
                "id: 7\n"
                "---\n"
                "\n"
                "Existing body\n",
                encoding="utf-8",
            )
            client = FakeDocBaseClient()

            exit_code = push_markdown_file(path, client)

            self.assertEqual(exit_code, 0)
            self.assertEqual(client.created_payloads, [])
            self.assertEqual(
                client.updated_payloads,
                [
                    (
                        7,
                        {
                            "title": "Existing Post",
                            "body": "Existing body",
                            "draft": False,
                            "tags": ["docs"],
                        },
                    )
                ],
            )

    def test_main_requires_docbase_environment_variables(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "sample.md"
            path.write_text(
                "---\ntitle: Sample\ndraft: false\n---\n\nBody\n",
                encoding="utf-8",
            )

            previous_domain = os.environ.pop("DOCBASE_DOMAIN", None)
            previous_token = os.environ.pop("DOCBASE_TOKEN", None)
            self.addCleanup(_restore_env_var, "DOCBASE_DOMAIN", previous_domain)
            self.addCleanup(_restore_env_var, "DOCBASE_TOKEN", previous_token)

            result = self.runner.invoke(main, ["push", str(path)])
            self.assertEqual(result.exit_code, 1)
            self.assertIn(
                "Error: missing environment variables: DOCBASE_DOMAIN, DOCBASE_TOKEN",
                result.output,
            )

    def test_main_supports_push_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "command-post.md"
            path.write_text(
                "---\ntitle: Command Post\ndraft: false\n---\n\nCLI body\n",
                encoding="utf-8",
            )

            previous_domain = os.environ.get("DOCBASE_DOMAIN")
            previous_token = os.environ.get("DOCBASE_TOKEN")
            self.addCleanup(_restore_env_var, "DOCBASE_DOMAIN", previous_domain)
            self.addCleanup(_restore_env_var, "DOCBASE_TOKEN", previous_token)
            os.environ["DOCBASE_DOMAIN"] = "example"
            os.environ["DOCBASE_TOKEN"] = "secret"

            fake_client = FakeDocBaseClient()

            with patch.object(DocBaseClient, "from_env", return_value=fake_client):
                result = self.runner.invoke(main, ["push", str(path)])

            self.assertEqual(result.exit_code, 0)
            self.assertIn("Created DocBase post 42", result.output)

    def test_pull_markdown_file_updates_local_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "pulled-post.md"
            path.write_text(
                "---\ntitle: Old Title\ndraft: false\nid: 7\n---\n\nOld body\n",
                encoding="utf-8",
            )
            client = FakeDocBaseClient()

            exit_code = pull_markdown_file(path, client)

            self.assertEqual(exit_code, 0)
            document = load_markdown_document(path)
            self.assertEqual(document.document_id, 7)
            self.assertEqual(document.title, "Pulled Post")
            self.assertEqual(document.body, "Pulled body")
            self.assertEqual(document.tags, ["remote", "docbase"])
            self.assertTrue(document.draft)

    def test_pull_markdown_file_creates_new_file_when_id_is_given(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "imported-post.md"
            client = FakeDocBaseClient()

            exit_code = pull_markdown_file(path, client, document_id=7)

            self.assertEqual(exit_code, 0)
            document = load_markdown_document(path)
            self.assertEqual(document.document_id, 7)
            self.assertEqual(document.title, "Pulled Post")
            self.assertEqual(document.body, "Pulled body")
            self.assertEqual(document.tags, ["remote", "docbase"])
            self.assertTrue(document.draft)

    def test_pull_markdown_file_preserves_crlf_newlines(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "pulled-crlf.md"
            path.write_bytes(
                b"---\r\ntitle: Old Title\r\ndraft: false\r\nid: 7\r\n---\r\n\r\nOld body\r\n"
            )
            client = FakeDocBaseClient()

            exit_code = pull_markdown_file(path, client)

            self.assertEqual(exit_code, 0)
            content = path.read_bytes()
            self.assertIn(b"\r\n", content)
            self.assertNotIn(b"---\n", content)
            self.assertTrue(content.endswith(b"\r\n"))

    def test_pull_markdown_file_normalizes_remote_crlf_before_writing(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "pulled-remote-crlf.md"
            path.write_bytes(
                b"---\r\ntitle: Old Title\r\ndraft: false\r\nid: 7\r\n---\r\n\r\nOld body\r\n"
            )
            client = FakeDocBaseClient()

            def get_post_with_crlf(post_id: int) -> dict[str, object]:
                return {
                    "id": post_id,
                    "title": "Pulled Post",
                    "body": "Line 1\r\nLine 2\r\n",
                    "draft": True,
                    "tags": [{"name": "remote"}],
                }

            client.get_post = get_post_with_crlf  # type: ignore[method-assign]

            exit_code = pull_markdown_file(path, client)

            self.assertEqual(exit_code, 0)
            content = path.read_bytes()
            self.assertNotIn(b"\r\r\n", content)
            self.assertIn(b"Line 1\r\nLine 2\r\n", content)

    def test_main_supports_pull_id_for_new_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "pull-id.md"
            previous_domain = os.environ.get("DOCBASE_DOMAIN")
            previous_token = os.environ.get("DOCBASE_TOKEN")
            self.addCleanup(_restore_env_var, "DOCBASE_DOMAIN", previous_domain)
            self.addCleanup(_restore_env_var, "DOCBASE_TOKEN", previous_token)
            os.environ["DOCBASE_DOMAIN"] = "example"
            os.environ["DOCBASE_TOKEN"] = "secret"

            fake_client = FakeDocBaseClient()

            with patch.object(DocBaseClient, "from_env", return_value=fake_client):
                result = self.runner.invoke(main, ["pull", "--id", "7", str(path)])

            self.assertEqual(result.exit_code, 0)
            self.assertIn("Pulled DocBase post 7", result.output)
            document = load_markdown_document(path)
            self.assertEqual(document.document_id, 7)

    def test_main_rejects_pull_id_when_target_file_exists(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "pull-id-existing.md"
            path.write_text(
                "---\ntitle: Existing\ndraft: false\nid: 7\n---\n\nExisting body\n",
                encoding="utf-8",
            )

            previous_domain = os.environ.get("DOCBASE_DOMAIN")
            previous_token = os.environ.get("DOCBASE_TOKEN")
            self.addCleanup(_restore_env_var, "DOCBASE_DOMAIN", previous_domain)
            self.addCleanup(_restore_env_var, "DOCBASE_TOKEN", previous_token)
            os.environ["DOCBASE_DOMAIN"] = "example"
            os.environ["DOCBASE_TOKEN"] = "secret"

            fake_client = FakeDocBaseClient()

            with patch.object(DocBaseClient, "from_env", return_value=fake_client):
                result = self.runner.invoke(main, ["pull", "--id", "7", str(path)])

            self.assertEqual(result.exit_code, 1)
            self.assertIn("Error: refusing to overwrite existing file", result.output)

    def test_main_shows_concise_error_for_missing_document_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "missing-id.md"
            path.write_text(
                "---\ntitle: Sample\ndraft: false\n---\n\nBody\n",
                encoding="utf-8",
            )

            previous_domain = os.environ.get("DOCBASE_DOMAIN")
            previous_token = os.environ.get("DOCBASE_TOKEN")
            self.addCleanup(_restore_env_var, "DOCBASE_DOMAIN", previous_domain)
            self.addCleanup(_restore_env_var, "DOCBASE_TOKEN", previous_token)
            os.environ["DOCBASE_DOMAIN"] = "example"
            os.environ["DOCBASE_TOKEN"] = "secret"

            result = self.runner.invoke(main, ["pull", str(path)])

            self.assertEqual(result.exit_code, 1)
            self.assertIn("Error: missing document id in front matter", result.output)

    def test_main_shows_concise_docbase_api_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "command-post.md"
            path.write_text(
                "---\ntitle: Command Post\ndraft: false\n---\n\nCLI body\n",
                encoding="utf-8",
            )

            previous_domain = os.environ.get("DOCBASE_DOMAIN")
            previous_token = os.environ.get("DOCBASE_TOKEN")
            self.addCleanup(_restore_env_var, "DOCBASE_DOMAIN", previous_domain)
            self.addCleanup(_restore_env_var, "DOCBASE_TOKEN", previous_token)
            os.environ["DOCBASE_DOMAIN"] = "example"
            os.environ["DOCBASE_TOKEN"] = "secret"

            with patch.object(
                DocBaseClient,
                "from_env",
                side_effect=DocBaseRequestError("DocBase API error (403): forbidden"),
            ):
                result = self.runner.invoke(main, ["push", str(path)])

            self.assertEqual(result.exit_code, 1)
            self.assertIn("Error: DocBase API error (403): forbidden", result.output)


def _restore_env_var(name: str, value: str | None) -> None:
    if value is None:
        os.environ.pop(name, None)
    else:
        os.environ[name] = value


if __name__ == "__main__":
    unittest.main()
