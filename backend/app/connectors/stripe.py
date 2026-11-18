"""Stripe charges connector: cursor pagination + incremental sync on ``created``.

Works against the real API (https://api.stripe.com with an sk_test_/rk_ key) or the bundled mock.
"""

from __future__ import annotations

from typing import Iterator

import httpx

from ..retry import check_response


class StripeConnector:
    name = "stripe"

    def __init__(self, base_url: str, api_key: str, client: httpx.Client | None = None, timeout: float = 15):
        self.base_url = base_url.rstrip("/")
        self.client = client or httpx.Client(timeout=timeout)
        self.headers = {"Authorization": f"Bearer {api_key}"}

    def fetch_page(self, starting_after: str | None, since: int | None, limit: int = 100) -> dict:
        params: dict = {"limit": limit}
        if starting_after:
            params["starting_after"] = starting_after
        if since:
            params["created[gte]"] = since
        resp = self.client.get(f"{self.base_url}/v1/charges", params=params, headers=self.headers)
        return check_response(resp, "stripe").json()

    @staticmethod
    def normalize(c: dict) -> dict:
        return {
            "id": c["id"], "amount": int(c["amount"]), "currency": c["currency"].upper(),
            "status": "refunded" if c.get("refunded") else c["status"], "refunded": int(bool(c.get("refunded"))),
            "failure_message": c.get("failure_message"),
            "customer_email": (c.get("billing_details") or {}).get("email") or c.get("receipt_email"),
            "description": c.get("description"), "created": int(c["created"]),
        }

    def pages(self, since: int | None, fetch=None) -> Iterator[list[dict]]:
        """Yield normalized pages. ``fetch`` lets the sync engine wrap each page call in retries."""
        fetch = fetch or self.fetch_page
        cursor = None
        while True:
            body = fetch(cursor, since)
            data = body.get("data", [])
            if data:
                yield [self.normalize(c) for c in data]
            if not body.get("has_more") or not data:
                return
            cursor = data[-1]["id"]
