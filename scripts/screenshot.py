"""Capture dashboard screenshots with Playwright (headless).

Requires the stack running (scripts/dev.sh). Produces:
  docs/dashboard-failure.png   a failed help-desk sync with the Retry button
  docs/dashboard-recovered.png after clicking Retry once the API recovers

    pip install playwright && playwright install chromium   # or set CHROME_PATH to a local Chrome
    python scripts/screenshot.py
"""

import json
import os
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

UI = os.getenv("UI_URL", "http://localhost:3000")
API = os.getenv("API_URL", "http://127.0.0.1:8000")
MOCK = os.getenv("MOCK_URL", "http://127.0.0.1:9100")
DOCS = Path(__file__).resolve().parent.parent / "docs"


def post(url: str, body: dict | None = None) -> dict:
    req = urllib.request.Request(url, data=json.dumps(body or {}).encode(), method="POST",
                                 headers={"content-type": "application/json"})
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read() or b"{}")


def wait_idle() -> None:
    for _ in range(60):
        with urllib.request.urlopen(f"{API}/api/runs?limit=5") as r:
            if all(x["status"] != "running" for x in json.load(r)):
                return
        time.sleep(0.5)


def main() -> None:
    wait_idle()
    post(f"{MOCK}/__chaos", {"source": "stripe", "fail_next": 2})
    post(f"{API}/api/sync?source=stripe")
    wait_idle()
    post(f"{MOCK}/__chaos", {"source": "helpdesk", "fail_next": 100})
    post(f"{API}/api/sync?source=helpdesk")
    wait_idle()

    with sync_playwright() as p:
        launch = {"headless": True}
        if os.getenv("CHROME_PATH"):
            launch["executable_path"] = os.environ["CHROME_PATH"]
        browser = p.chromium.launch(**launch)
        page = browser.new_page(viewport={"width": 1440, "height": 1180}, device_scale_factor=1)
        page.goto(UI)
        page.wait_for_selector("text=Sync runs")
        page.wait_for_selector("button:has-text('Retry')")
        time.sleep(1)
        page.screenshot(path=str(DOCS / "dashboard-failure.png"), full_page=True)

        post(f"{MOCK}/__chaos", {"source": "helpdesk", "fail_next": 0})
        page.locator("button:has-text('Retry')").first.click()
        page.wait_for_selector("text=retry of #", timeout=15000)
        time.sleep(5)  # let polling refresh source health
        page.screenshot(path=str(DOCS / "dashboard-recovered.png"), full_page=True)
        browser.close()
    print("saved", DOCS / "dashboard-failure.png", DOCS / "dashboard-recovered.png")


if __name__ == "__main__":
    main()
