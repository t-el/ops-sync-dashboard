"""Offline stand-ins for the Stripe API and a Zendesk-style help-desk API.

Same shapes as the real APIs where it matters (Bearer auth, Stripe cursor pagination with
``starting_after``/``has_more``, help-desk page pagination with ``next_page``), plus a
``/__chaos`` endpoint to inject failures so retries and the failure UI can be demonstrated.

    uvicorn mock_apis.server:app --port 9100
"""

from __future__ import annotations

from typing import Optional

from fastapi import FastAPI, Header, HTTPException, Request
from pydantic import BaseModel

from .fixtures import make_charges, make_tickets

app = FastAPI(title="Mock Stripe + Help Desk")
STATE: dict = {"charges": make_charges(), "tickets": make_tickets(), "chaos": {"stripe": 0, "helpdesk": 0}, "status": 503}


class Chaos(BaseModel):
    source: str  # stripe | helpdesk
    fail_next: int = 3
    status: int = 503


@app.post("/__chaos")
def chaos(c: Chaos) -> dict:
    STATE["chaos"][c.source] = c.fail_next
    STATE["status"] = c.status
    return STATE["chaos"]


@app.post("/__reset")
def reset() -> dict:
    STATE.update(charges=make_charges(), tickets=make_tickets(), chaos={"stripe": 0, "helpdesk": 0}, status=503)
    return {"ok": True}


def _maybe_fail(source: str) -> None:
    if STATE["chaos"][source] > 0:
        STATE["chaos"][source] -= 1
        raise HTTPException(status_code=STATE["status"], detail=f"{source} temporarily unavailable (chaos)")


def _auth(authorization: Optional[str], prefix: str) -> None:
    if not authorization or not authorization.startswith("Bearer ") or not authorization[7:].startswith(prefix):
        raise HTTPException(status_code=401, detail="invalid API key")


@app.get("/stripe/v1/charges")
def list_charges(request: Request, limit: int = 25, starting_after: Optional[str] = None,
                 authorization: Optional[str] = Header(default=None)) -> dict:
    _auth(authorization, "sk_test_")
    _maybe_fail("stripe")
    gte = request.query_params.get("created[gte]")
    data = [c for c in STATE["charges"] if gte is None or c["created"] >= int(gte)]
    start = 0
    if starting_after:
        ids = [c["id"] for c in data]
        start = ids.index(starting_after) + 1 if starting_after in ids else len(data)
    page = data[start:start + min(limit, 100)]
    return {"object": "list", "data": page, "has_more": start + len(page) < len(data), "url": "/v1/charges"}


@app.get("/helpdesk/api/v2/tickets")
def list_tickets(page: int = 1, per_page: int = 20, updated_since: Optional[int] = None,
                 authorization: Optional[str] = Header(default=None)) -> dict:
    _auth(authorization, "hd_")
    _maybe_fail("helpdesk")
    data = [t for t in STATE["tickets"] if updated_since is None or t["updated_at"] >= updated_since]
    data.sort(key=lambda t: t["id"])
    chunk = data[(page - 1) * per_page: page * per_page]
    has_next = page * per_page < len(data)
    return {"tickets": chunk, "count": len(data), "next_page": page + 1 if has_next else None}


@app.get("/health")
def health() -> dict:
    return {"ok": True}
