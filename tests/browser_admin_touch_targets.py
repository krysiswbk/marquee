"""Browser contract for admin hit areas, numeric semantics, and narrow overflow."""

import os
from urllib.parse import urljoin

from playwright.sync_api import sync_playwright
from copy import deepcopy
import json

BASE = os.environ.get("MARQUEE_SMOKE_URL", "http://127.0.0.1:18086")
ROUTES = [
    "/settings",
    "/settings/layout?profile=cast",
    "/settings/layout?profile=live",
    "/settings/attention",
    "/settings/tests",
]
VIEWPORTS = [(1500, 900), (1024, 600), (700, 900), (393, 852)]
TARGETS = (
    "button:not([hidden])",
    "summary:not([hidden])",
    "select:not([hidden])",
    "input[type=number]:not([hidden])",
    "input[type=range]:not([hidden])",
    ".workspace-nav a:not([hidden])",
    ".mq-profile-picker a:not([hidden])",
)


with sync_playwright() as playwright:
    browser = playwright.chromium.launch(
        executable_path=os.environ.get("MARQUEE_CHROMIUM"), args=["--no-sandbox"]
    )
    for width, height in VIEWPORTS:
        for route in ROUTES:
            page = browser.new_page(viewport={"width": width, "height": height})
            errors: list[str] = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(urljoin(BASE, route), wait_until="domcontentloaded")
            page.wait_for_timeout(500)
            for selector in TARGETS:
                for box in page.locator(selector).evaluate_all(
                    "els => els.filter(el => { const s=getComputedStyle(el); "
                    "return s.display !== 'none' && s.visibility !== 'hidden' && "
                    "el.getBoundingClientRect().width > 0; }).map(el => "
                    "({tag:el.tagName,id:el.id,rect:el.getBoundingClientRect().toJSON()}))"
                ):
                    assert box["rect"]["height"] >= 44, (width, height, route, selector, box)
            for control in page.locator('input[type="number"], input[type="range"]').evaluate_all(
                "els => els.filter(el => { const r=el.getBoundingClientRect(); "
                "return r.width > 0 && r.height > 0; }).map(el => ({id:el.id,min:el.min,max:el.max,step:el.step,described:el.getAttribute('aria-describedby'),name:el.getAttribute('aria-label') || document.querySelector(`label[for=\"${el.id}\"]`)?.innerText || el.closest('label')?.innerText || ''}))"
            ):
                assert control["min"] and control["max"] and control["step"], (route, control)
                assert control["described"], (route, control)
                assert control["name"].strip(), (route, control)
            for control in page.locator('input[type="number"], input[type="range"]').evaluate_all(
                "els => els.map(el => ({id:el.id,min:el.min,max:el.max,step:el.step,name:el.getAttribute('aria-label') || document.querySelector(`label[for=\"${el.id}\"]`)?.innerText || el.closest('label')?.innerText || '',described:el.getAttribute('aria-describedby')}))"
            ):
                assert control["min"] != '' and control["max"] != '' and control["step"] != '', (route, control)
                assert control["name"].strip() and control["described"], (route, control)
            audit = page.evaluate("""() => {
                const ids = [...document.querySelectorAll('[id]')].map(node => node.id);
                const duplicateIds = [...new Set(ids.filter((id, index) => ids.indexOf(id) !== index))];
                const broken = [];
                for (const node of document.querySelectorAll('label[for], [aria-describedby], [aria-controls]')) {
                    for (const attribute of ['for', 'aria-describedby', 'aria-controls']) {
                        const value = node.getAttribute(attribute);
                        if (!value) continue;
                        for (const id of (attribute === 'for' ? [value] : value.split(/\\s+/))) {
                            if (id && !document.getElementById(id)) broken.push({attribute, id, tag: node.tagName});
                        }
                    }
                }
                return {duplicateIds, broken};
            }""")
            assert not audit["duplicateIds"], (route, audit)
            assert not audit["broken"], (route, audit)
            assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1"), (width, height, route)
            if route != "/settings/layout?profile=live":
                dock = page.locator(".savebar").last
                if dock.count():
                    dock_box = dock.bounding_box()
                    if dock_box:
                        assert dock_box["y"] + dock_box["height"] <= height + 1, (width, height, route)
            assert not errors, (width, height, route, errors)
            page.close()
    seed = browser.new_page()
    response = seed.request.get(BASE + "/api/attention")
    if response.ok:
        payload = response.json()
        config = deepcopy(payload.get("config", {}))
        rules = config.get("rules", [])
        if rules:
            fixture = deepcopy(rules[0])
            fixture["id"] = "fixture-second-rule"
            fixture["title"] = "Fixture duplicate-stage rule"
            fixture.setdefault("escalation", []).append(deepcopy(fixture["escalation"][0]))
            fixture["escalation"][0]["id"] = "repeated-stage"
            fixture["escalation"][1]["id"] = "repeated-stage"
            fixture["escalation"][0]["when"] = {"field": "context.home", "op": "eq", "value": True}
            fixture["modifiers"] = [{"id": "same-modifier", "delta": 5, "when": {"field": "context.home", "op": "eq", "value": True}}]
            rules[0]["escalation"][0]["id"] = "repeated-stage"
            config["rules"] = [rules[0], fixture]
            fixture_payload = dict(payload, config=config)
            page = browser.new_page(viewport={"width": 393, "height": 852})
            page.route("**/api/attention", lambda route: route.fulfill(json=fixture_payload))
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(BASE + "/admin/attention", wait_until="domcontentloaded")
            page.wait_for_function("document.getElementById('status').textContent.includes('Updated')")
            audit = page.evaluate("""() => {
                const ids = [...document.querySelectorAll('[id]')].map(node => node.id);
                const duplicateIds = [...new Set(ids.filter((id, index) => ids.indexOf(id) !== index))];
                const broken = [];
                for (const node of document.querySelectorAll('label[for], [aria-describedby], [aria-controls]')) {
                    for (const attribute of ['for', 'aria-describedby', 'aria-controls']) {
                        const value = node.getAttribute(attribute);
                        if (!value) continue;
                        for (const id of (attribute === 'for' ? [value] : value.split(/\\s+/))) {
                            if (id && !document.getElementById(id)) broken.push({attribute, id});
                        }
                    }
                }
                return {duplicateIds, broken};
            }""")
            assert not audit["duplicateIds"], audit
            assert not audit["broken"], audit
            stage_controls = page.locator('[data-attention-field="stage_after"]').evaluate_all(
                "els => els.map(el => ({id: el.id, described: el.getAttribute('aria-describedby')}))"
            )
            assert len(stage_controls) >= 3, stage_controls
            stage_ids = [control["id"] for control in stage_controls]
            assert len(stage_ids) == len(set(stage_ids)), stage_controls
            for control in stage_controls:
                assert control["described"], control
                for target in control["described"].split():
                    assert page.locator(f"#{target}").count() == 1, (control, target)
            page.get_by_role("button", name="Edit policy").click()
            invalid = page.locator("#attention-signal-ttl")
            assert invalid.is_visible()
            invalid.fill("-1")
            assert invalid.get_attribute("aria-invalid") == "true"
            assert page.locator("#save").is_disabled()
            described = invalid.get_attribute("aria-describedby").split()
            assert {"attention-signal-ttl-help", "attention-signal-ttl-error"}.issubset(described)
            for target in described:
                assert page.locator(f"#{target}").count() == 1
            page.locator("#discard").click()
            assert not page.locator('[aria-invalid="true"]').count()
            assert page.locator("#save").is_disabled()
            assert invalid.input_value() != "-1"
            assert not errors, errors
            page.close()
    seed.close()
    print("PASS: admin targets, numeric semantics, overflow, dock reachability, and console errors across 5 routes × 4 viewports")
    browser.close()
