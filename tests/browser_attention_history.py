"""Read-only browser fixture for responsive recent-history diagnostics."""

import json
import os
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright

BASE = os.environ.get("MARQUEE_SMOKE_URL", "http://127.0.0.1:18084").rstrip("/")
assert urlparse(BASE).hostname in ("127.0.0.1", "localhost")
FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "attention-history.json").read_text())
VIEWPORTS = [(1500, 900), (1024, 600), (700, 900), (393, 852)]
EVIDENCE = Path(os.environ.get("MARQUEE_EVIDENCE_DIR", "/tmp/marquee-2.10.56-history-evidence"))


with sync_playwright() as playwright:
    browser = playwright.chromium.launch(
        executable_path=os.environ.get("MARQUEE_CHROMIUM"), args=["--no-sandbox"]
    )
    seed_page = browser.new_page()
    response = seed_page.request.get(BASE + "/api/attention")
    assert response.ok, response.status
    payload = response.json()
    payload["history"] = [
        dict(item, at=1800000000, source=f"fixture-source-{index}", id=f"fixture-event-{index}")
        for index, item in enumerate((FIXTURE * 80)[:150])
    ]
    for width, height in VIEWPORTS:
        EVIDENCE.mkdir(parents=True, exist_ok=True)
        page = browser.new_page(viewport={"width": width, "height": height})
        page.route("**/api/attention", lambda route: route.fulfill(json=payload))
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(BASE + "/admin/attention", wait_until="domcontentloaded")
        page.wait_for_function("document.getElementById('status').textContent.startsWith('Updated')")
        page.get_by_text("Recent history", exact=True).click()
        assert page.locator(".history-row").count() == 40
        labels = page.locator(".history-details summary").evaluate_all(
            "summaries => summaries.map(summary => summary.getAttribute('aria-label'))"
        )
        assert len(set(labels)) == 40
        assert all("source fixture-source-" in label and "id fixture-event-" in label for label in labels)
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        disclosure = page.locator(".history-details summary").first
        disclosure.focus()
        disclosure.press("Enter")
        assert page.locator(".history-details").first.get_attribute("open") is not None
        assert page.locator(".history-payload").first.is_visible()
        disclosure.press("Enter")
        assert page.locator(".history-details").first.get_attribute("open") is None
        page.locator(".history-controls button").click()
        assert page.locator(".history-row").count() == 80
        assert not errors, errors
        page.screenshot(path=str(EVIDENCE / f"history-{width}x{height}.png"), full_page=True)
        print(f"history {width}x{height}: responsive disclosure, keyboard, pagination PASS")
        page.close()

    empty = dict(payload)
    empty["history"] = []
    page = browser.new_page(viewport={"width": 393, "height": 852})
    page.route("**/api/attention", lambda route: route.fulfill(json=empty))
    page.goto(BASE + "/admin/attention", wait_until="domcontentloaded")
    page.wait_for_function("document.getElementById('status').textContent.startsWith('Updated')")
    page.get_by_text("Recent history", exact=True).click()
    assert page.get_by_text("No recent attention history.", exact=True).is_visible()
    page.close()

    unavailable = browser.new_page(viewport={"width": 393, "height": 852})
    unavailable.route("**/api/attention", lambda route: route.abort("failed"))
    unavailable.goto(BASE + "/admin/attention", wait_until="domcontentloaded")
    unavailable.wait_for_function("document.getElementById('status').classList.contains('error')")
    unavailable.get_by_text("Recent history", exact=True).click()
    assert unavailable.get_by_text("History unavailable:", exact=False).is_visible()
    unavailable.close()
    browser.close()
