"""Help-desk tickets connector (Zendesk-style page pagination, incremental on updated_at)."""

from __future__ import annotations

from typing import Iterator

import httpx

from ..retry import check_response


class HelpdeskConnector:
    name = "helpdesk"

    def __init__(self, base_url: str, api_key: str, client: httpx.Client | None = None, timeout: float = 15):
        self.base_url = base_url.rstrip("/")
        self.client = client or httpx.Client(timeout=timeout)
        self.headers = {"Authorization": f"Bearer {api_key}"}

    def fetch_page(self, page: int | None, since: int | None) -> dict:
        params: dict = {"page": page or 1, "per_page": 50}
        if since:
            params["updated_since"] = since
        resp = self.client.get(f"{self.base_url}/api/v2/tickets", params=params, headers=self.headers)
        return check_response(resp, "helpdesk").json()

    @staticmethod
    def normalize(t: dict) -> dict:
        return {k: t.get(k) for k in ("id", "subject", "status", "priority", "requester_email", "created_at", "updated_at")}

    def pages(self, since: int | None, fetch=None) -> Iterator[list[dict]]:
        fetch = fetch or self.fetch_page
        page: int | None = 1
        while page:
            body = fetch(page, since)
            tickets = body.get("tickets", [])
            if tickets:
                yield [self.normalize(t) for t in tickets]
            page = body.get("next_page")
