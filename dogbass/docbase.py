from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import httpx

API_BASE_URL = "https://api.docbase.io"


class DocBaseConfigurationError(ValueError):
    """Raised when required DocBase configuration is missing."""


class DocBaseApiError(RuntimeError):
    """Raised when the DocBase API returns an error response."""


@dataclass(slots=True)
class DocBaseClient:
    domain: str
    token: str
    client: httpx.Client | None = None

    @classmethod
    def from_env(cls) -> "DocBaseClient":
        domain = os.environ.get("DOCBASE_DOMAIN")
        token = os.environ.get("DOCBASE_TOKEN")

        missing = [
            name
            for name, value in (
                ("DOCBASE_DOMAIN", domain),
                ("DOCBASE_ACCESS_TOKEN", token),
            )
            if not value
        ]
        if missing:
            missing_names = ", ".join(missing)
            raise DocBaseConfigurationError(
                f"Missing required environment variables: {missing_names}"
            )

        assert domain is not None
        assert token is not None
        return cls(domain=domain, token=token)

    def create_post(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", f"/teams/{self.domain}/posts", payload)

    def update_post(self, post_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("PATCH", f"/teams/{self.domain}/posts/{post_id}", payload)

    def _request(
        self, method: str, path: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        headers = {
            "X-DocBaseToken": self.token,
            "Content-Type": "application/json",
        }

        if self.client is None:
            with httpx.Client(base_url=API_BASE_URL, timeout=30.0) as client:
                response = client.request(method, path, headers=headers, json=payload)
        else:
            response = self.client.request(method, path, headers=headers, json=payload)

        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            details = _extract_error_details(exc.response)
            raise DocBaseApiError(
                f"DocBase API request failed ({exc.response.status_code}): {details}"
            ) from exc

        data = response.json()
        if not isinstance(data, dict):
            raise DocBaseApiError("DocBase API returned a non-object JSON response")
        return data


def _extract_error_details(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        text = response.text.strip()
        return text or "No response body"

    if isinstance(payload, dict):
        errors = payload.get("errors")
        if isinstance(errors, list) and errors:
            return ", ".join(str(error) for error in errors)

        message = payload.get("message")
        if isinstance(message, str) and message:
            return message

    return str(payload)
