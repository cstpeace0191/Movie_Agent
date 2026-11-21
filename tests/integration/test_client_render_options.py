"""Feature 002, US1 client test (T078): transition controls work with the keyboard alone."""

import pytest

pytestmark = pytest.mark.browser

MAX_TABS = 80


def _tab_to(page, element_id: str) -> None:
    for _ in range(MAX_TABS):
        page.keyboard.press("Tab")
        if page.evaluate("document.activeElement && document.activeElement.id") == element_id:
            return
    raise AssertionError(f"#{element_id} is not reachable with Tab")


def _fill_scenario(page) -> None:
    page.fill("#scenario-text", "A quiet beach at sunrise.\n\nWaves roll onto the sand.")


def test_keyboard_only_transition_choice_is_submitted(logged_in_page):
    page = logged_in_page
    _fill_scenario(page)

    _tab_to(page, "opt-transition")
    page.keyboard.press("ArrowDown")  # none -> fade
    assert page.eval_on_selector("#opt-transition", "el => el.value") == "fade"

    _tab_to(page, "opt-transition-seconds")
    page.keyboard.press("Control+A")
    page.keyboard.type("1.0")

    with page.expect_request(
        lambda r: r.url.endswith("/api/jobs") and r.method == "POST", timeout=15000
    ) as req_info:
        page.keyboard.press("Enter")
    body = req_info.value.post_data or ""
    assert 'name="transition"\r\n\r\nfade' in body
    assert 'name="transition_seconds"\r\n\r\n1' in body


def test_out_of_range_length_shows_text_error_and_is_not_sent(logged_in_page):
    page = logged_in_page
    _fill_scenario(page)
    page.select_option("#opt-transition", "dissolve")
    page.fill("#opt-transition-seconds", "2.5")

    error = page.locator("#opt-transition-seconds-error")
    assert error.is_visible()
    assert "0.1" in error.inner_text() and "2.0" in error.inner_text()

    sent: list[str] = []
    page.on(
        "request",
        lambda r: (
            sent.append(r.url) if r.url.endswith("/api/jobs") and r.method == "POST" else None
        ),
    )
    page.locator("#job-form button[type=submit]").click()
    page.wait_for_timeout(1000)
    assert sent == []


def test_transition_controls_have_no_serious_axe_violations(logged_in_page):
    from tests.integration.conftest import axe_scan

    page = logged_in_page
    page.select_option("#opt-transition", "fade")
    violations = [
        v
        for v in axe_scan(page)
        if any(
            "render-options" in (node.get("html", "") + " ".join(node.get("target", [])))
            or "opt-transition" in " ".join(node.get("target", []))
            for node in v.get("nodes", [])
        )
    ]
    assert violations == [], violations
