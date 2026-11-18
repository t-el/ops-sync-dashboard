"""Deterministic fake data so the dashboard looks real offline (seeded, so tests are stable)."""

from __future__ import annotations

import random
import time

CUSTOMERS = [
    "ana@brightcart.io", "ops@northwind-logistics.com", "billing@atlas-dental.fr", "mia@lumen-legal.de",
    "finance@greenleaf.co", "admin@pixelforge.dev", "hello@sunrise-yoga.ma", "team@cobalt-analytics.com",
    "accounts@harbor-freight.example", "cto@quanta-labs.io", "owner@casablanca-coffee.ma", "it@fjord-design.no",
]
PRODUCTS = [("Starter plan", 2900), ("Pro plan", 9900), ("Team plan", 24900), ("Add-on: extra seats", 1500)]
SUBJECTS = [
    "Can't log in after password reset", "Invoice shows wrong VAT number", "Card declined but I was charged",
    "How do I add a teammate?", "Export to CSV is timing out", "Request: SSO support", "Refund for duplicate charge",
    "Webhook deliveries failing", "Cancel my subscription", "Dashboard is slow this morning",
]
DAY = 86400


def make_charges(n: int = 140, seed: int = 7, now: int | None = None) -> list[dict]:
    rnd = random.Random(seed)
    now = now or int(time.time())
    charges = []
    for i in range(n):
        name, amount = rnd.choice(PRODUCTS)
        status = rnd.choices(["succeeded", "failed", "refunded"], weights=[86, 10, 4])[0]
        charges.append({
            "id": f"ch_{seed}{i:05d}",
            "object": "charge",
            "amount": amount,
            "currency": "usd",
            "status": "succeeded" if status == "refunded" else status,
            "refunded": status == "refunded",
            "paid": status != "failed",
            "failure_message": "Your card was declined." if status == "failed" else None,
            "billing_details": {"email": rnd.choice(CUSTOMERS)},
            "description": name,
            "created": now - int(rnd.uniform(0, 30) * DAY),
        })
    charges.sort(key=lambda c: c["created"], reverse=True)  # Stripe lists newest first
    return charges


def make_tickets(n: int = 48, seed: int = 11, now: int | None = None) -> list[dict]:
    rnd = random.Random(seed)
    now = now or int(time.time())
    tickets = []
    for i in range(n):
        created = now - int(rnd.uniform(0, 21) * DAY)
        tickets.append({
            "id": 1000 + i,
            "subject": rnd.choice(SUBJECTS),
            "status": rnd.choices(["open", "pending", "solved"], weights=[30, 20, 50])[0],
            "priority": rnd.choices(["low", "normal", "high", "urgent"], weights=[20, 50, 20, 10])[0],
            "requester_email": rnd.choice(CUSTOMERS),
            "created_at": created,
            "updated_at": min(now, created + int(rnd.uniform(0, 3) * DAY)),
        })
    return tickets
