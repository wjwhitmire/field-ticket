"""Browser test of the published site: placeholders filled, served under /field-ticket/.

Runs the main workflows in headless Chromium. Skips when Playwright or its
browser is not installed (pip install playwright && playwright install chromium).
"""

from __future__ import annotations

import json

import pytest

from pages_site import install_routes, pages_root, release_tree, serve, watch

sync_api = pytest.importorskip("playwright.sync_api")
NAME = "field-ticket"


@pytest.fixture(scope="module")
def site(tmp_path_factory):
    tree = release_tree(tmp_path_factory.mktemp("release"), NAME)
    for p in tree.rglob("*"):
        if p.is_file() and p.suffix in (".html", ".md", ".json", ".py"):
            assert "{{" + "LIVE_URL}}" not in p.read_text(encoding="utf-8"), p
    with serve(pages_root(tree), NAME) as url:
        yield url


@pytest.fixture(scope="module")
def browser():
    with sync_api.sync_playwright() as p:
        try:
            b = p.chromium.launch()
        except Exception as exc:  # browser binary missing
            pytest.skip(f"Chromium not available: {exc}")
        yield b
        b.close()


def open_page(browser, url, errors, **kw):
    ctx = browser.new_context(accept_downloads=True, **kw)
    install_routes(ctx, url.split("/" + NAME)[0], errors)
    page = ctx.new_page()
    watch(page, errors)
    page.goto(url)
    page.wait_for_selector("#doc-list")
    return ctx, page


def test_invoice_workflow_and_pdf(site, browser, tmp_path):
    errors: list = []
    ctx, page = open_page(browser, site, errors)
    assert page.title() == "Field Ticket"
    assert page.locator("#doc-list li").count() == 2
    page.click("#new-invoice")
    page.select_option("#cu-pick", index=1)
    page.select_option("#it-catalog", index=4)
    page.fill("#it-0-qty", "3")
    page.click("#it-add")
    page.fill("#it-1-name", "Vac truck")
    page.fill("#it-1-qty", "19.75")
    page.fill("#it-1-rate", "125")
    page.click("#pr-tmode-line")
    page.wait_for_timeout(200)
    assert "$2,607.58" in page.inner_text("#totals")
    if page.evaluate("() => !!(window.jspdf && window.jspdf.jsPDF)"):
        with page.expect_download(timeout=15000) as dl:
            page.click("#pdf-download")
        out = tmp_path / "inv.pdf"
        dl.value.save_as(out)
        data = out.read_bytes()
        assert data.startswith(b"%PDF-") and b"%%EOF" in data[-64:]
        pypdf = pytest.importorskip("pypdf")
        text = pypdf.PdfReader(str(out)).pages[0].extract_text()
        assert "2,607.58" in text and "INV-0002" in text
    else:
        page.click("#pdf-download")
        assert "did not load" in page.inner_text("#pdf-note")
    assert page.evaluate("() => window.__csp") == []
    assert errors == []
    ctx.close()


def test_ticket_hours_labor_rate_and_bundle_with_minimal_input(site, browser):
    errors: list = []
    ctx, page = open_page(browser, site, errors)
    # A finished job with a labor line sets the rate the next ticket reuses.
    page.click("#new-ticket")
    page.fill("#cu-name", "Sample Operating LLC")
    page.fill("#day-0-start", "06:00")
    page.fill("#day-0-end", "16:00")
    page.click("#day-labor")
    page.fill("#it-0-rate", "85")
    page.click("#ed-back")
    page.click("#new-ticket")
    page.fill("#cu-name", "sample operating llc")
    page.fill("#day-0-start", "19:00")
    page.fill("#day-0-end", "03:15")
    page.wait_for_timeout(200)
    assert "8.25" in page.inner_text("#day-0-hrs")
    page.click("#day-labor")
    assert page.input_value("#it-0-qty") == "8.25"
    assert page.input_value("#it-0-rate") == "85.00"
    assert "last labor line" in page.inner_text("#day-msg")
    # Bundle picks every open ticket for the customer; tax differs, so it asks once.
    page.click("#ac-bundle")
    assert "Picked the 3 open tickets" in page.inner_text("#bundle-why")
    page.click("#bundle-make")
    assert "Which one applies" in page.inner_text("#bundle-msg")
    page.locator("#bundle-fix button").first.click()
    page.wait_for_selector("#ed-h")
    assert page.inner_text("#ed-h").lower().startswith("invoice")
    assert page.locator(".item").count() == 6
    assert errors == []
    ctx.close()


def test_backup_round_trip_and_phone_layout(site, browser):
    errors: list = []
    ctx, page = open_page(browser, site, errors, viewport={"width": 400, "height": 800}, has_touch=True, is_mobile=True)
    assert page.evaluate("() => document.documentElement.scrollWidth - document.documentElement.clientWidth") <= 0
    page.click("#nav-backup")
    page.click("#bk-export")
    text = page.input_value("#bk-export-text")
    assert json.loads(text)["app"] == NAME
    page.fill("#im-text", "{nope")
    page.click("#im-go")
    assert "not valid JSON" in page.inner_text("#im-msg")
    page.fill("#im-text", text)
    page.click("#im-go")
    page.locator("#view .confirm button.danger").click()
    page.wait_for_selector("#doc-list")
    assert page.locator("#doc-list li").count() == 2
    assert errors == []
    ctx.close()
