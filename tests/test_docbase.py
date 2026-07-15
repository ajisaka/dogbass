from __future__ import annotations

import unittest

import httpx

from dogbass.docbase import DocBaseClient


class DocBaseClientTests(unittest.TestCase):
    def test_get_profile_requests_profile_endpoint(self) -> None:
        captured: dict[str, object] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["path"] = request.url.path
            return httpx.Response(200, json={"id": 99, "name": "Alice"})

        http_client = httpx.Client(
            transport=httpx.MockTransport(handler),
            base_url="https://api.docbase.io",
        )
        client = DocBaseClient(domain="example", token="secret", client=http_client)

        result = client.get_profile()

        self.assertEqual(result, {"id": 99, "name": "Alice"})
        self.assertEqual(captured["path"], "/teams/example/profile")

    def test_list_posts_sends_query_page_and_per_page(self) -> None:
        captured: dict[str, object] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["path"] = request.url.path
            captured["params"] = dict(request.url.params)
            return httpx.Response(200, json={"posts": [], "meta": {}})

        http_client = httpx.Client(
            transport=httpx.MockTransport(handler),
            base_url="https://api.docbase.io",
        )
        client = DocBaseClient(domain="example", token="secret", client=http_client)

        result = client.list_posts("author_id:1 is:draft", page=2, per_page=100)

        self.assertEqual(result, {"posts": [], "meta": {}})
        self.assertEqual(captured["path"], "/teams/example/posts")
        self.assertEqual(
            captured["params"],
            {"q": "author_id:1 is:draft", "page": "2", "per_page": "100"},
        )


if __name__ == "__main__":
    unittest.main()
