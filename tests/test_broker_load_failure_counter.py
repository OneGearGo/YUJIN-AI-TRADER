#!/usr/bin/env python3.11
# -*- coding: utf-8 -*-
"""
Polish #7.5: Playwright contract for the `window.__brokers_load_failures` counter
shipped at Polish #7.1 (commit ddb0578).

This test closes the Polish #7.1 code-reviewer 🟡-MEDIUM gap: the loadBrokers()
.catch handler in `static/index.html` had no automated regression contract.
Removing the counter increment would silently pass CI; this test pins that
exactly N simulated broker-load failures increase the counter by exactly N.

Mirror precedent: tests/test_broker_ui_resilience.py (page.route failure
injection pattern).

Cross-run safety: importorskip('playwright.sync_api') skips the whole module
if a runner lacks the UI test stack. A `skipif` module marker also bails if
`static/index.html` is missing (e.g. CI runners that git-clone but checkout
an unrelated ref).
"""
from __future__ import annotations

from pathlib import Path

import pytest

# Cross-run safety: skip the whole module if playwright sync_api isn't present.
# pytest-playwright exposes sync_api via its `page` fixture; playwright core
# provides the underlying sync_api namespace. importorskip fires at
# collection-time so absent deps don't break unrelated tests.
pytest.importorskip("playwright.sync_api")

REPO_ROOT = Path(__file__).resolve().parents[1]
STATIC_HTML = REPO_ROOT / "static" / "index.html"

# Glob for any URL loadBrokers() in static/index.html might fetch. Deliberately
# tolerant of route evolution (e.g. /api/brokers -> /brokers/list).
_BROKER_URL_GLOB = "**/*broker*"

# Module-level skipif: bail the whole file if static/index.html isn't present
# (e.g. sparse checkout). Keeps the test isolated from non-frontend envs.
pytestmark = pytest.mark.skipif(
    not STATIC_HTML.exists(),
    reason=f"static/index.html not found at {STATIC_HTML}",
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _force_broker_route_to_fail(page) -> None:
    """Block any URL matching the broker glob with an HTTP 500 mock response.

    Mirrors tests/test_broker_ui_resilience.py page.route failure-injection
    style: deterministic, upstream-independent, no FastAPI app required.
    """
    def _fulfill_500(route):
        route.fulfill(
            status=500,
            content_type="application/json",
            body='{"error": "simulated broker-load failure"}',
        )
    page.route(_BROKER_URL_GLOB, _fulfill_500)


def _reset_counter_via_init_script(page) -> None:
    """Inject a baseline reset of the telemetry counter BEFORE DOM parses.

    addInitScript runs in every new document; this guarantees that even if a
    previous test in this browser context left the counter > 0, the new test
    starts at 0 deterministically. The loadBrokers increment `(x || 0) + 1`
    (Polish #7.1) collapses undefined to 0 itself; this init-script is
    belt-and-suspenders so we can assert "counter STARTS at 0" too.
    """
    page.add_init_script(
        "try { window.__brokers_load_failures = 0; } catch (_) {}"
    )


def _invoke_load_brokers_N_times(page, n: int) -> None:
    """Call window.loadBrokers() exactly N times.

    page.evaluate auto-awaits Promises returned from async functions, so each
    call returns only after the rejected promise has been swallowed by the
    .catch handler (which is precisely when the counter increments).
    """
    js = """
        async () => {
            for (let i = 0; i < %d; i++) {
                if (typeof window.loadBrokers === 'function') {
                    try {
                        await window.loadBrokers();
                    } catch (_) {
                        // The .catch handler in loadBrokers itself should
                        // swallow; this outer try/catch is belt-and-suspenders
                        // so page.evaluate doesn't surface a leaked throw.
                    }
                }
            }
            return true;
        }
    """ % int(n)
    page.evaluate(js)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("t_failures", [1, 3])
def test_counter_increments_by_exactly_N(page, t_failures):
    """Pin the Polish #7.1 contract: N failures -> counter == N.

    Two sub-cases catch both single-call regression AND repeated-invocation
    drift in the `(x || 0) + 1` increment expression.
    """
    _force_broker_route_to_fail(page)
    _reset_counter_via_init_script(page)

    page.goto(STATIC_HTML.as_uri())  # file:// protocol - no app needed
    page.wait_for_load_state("domcontentloaded")

    # Some pages auto-fire loadBrokers on DOM-start; reset to 0 BEFORE our
    # explicit N invocations so the final assertion is deterministic.
    page.evaluate("window.__brokers_load_failures = 0;")

    _invoke_load_brokers_N_times(page, t_failures)

    actual = page.evaluate("window.__brokers_load_failures")
    assert actual == t_failures, (
        f"Polish #7.5 regression (N={t_failures}): expected "
        f"window.__brokers_load_failures == {t_failures}, observed {actual}. "
        "Either the .catch handler no longer increments, OR page.route is not "
        "intercepting the broker URLs."
    )


def test_counter_starts_at_zero_baseline(page):
    """Pin the reset-on-init-script branch + the (x || 0) + 1 idiom baseline.

    Independent of the increment path; this asserts the counter is 0 BEFORE
    any failure occurs (init-script forced 0).
    """
    _reset_counter_via_init_script(page)

    page.goto(STATIC_HTML.as_uri())
    page.wait_for_load_state("domcontentloaded")

    baseline = page.evaluate("window.__brokers_load_failures")
    # With the init-script baseline, the pre-failure value must be EXACTLY 0,
    # not undefined and not null.
    assert baseline == 0, (
        f"Polish #7.5 baseline regression: expected counter to start at 0 "
        f"(init-script), observed {baseline!r}. The "
        f"window.__brokers_load_failures || 0 idiom OR the add_init_script "
        f"reset has drifted."
    )


def test_load_brokers_function_exists_on_page(page):
    """Sanity-guard the function name. If loadBrokers is renamed, the .catch
    increment block in static/index.html needs to be re-pointed; this test
    ensures Polish #7.5 won't silently no-op against a renamed function.
    """
    page.goto(STATIC_HTML.as_uri())
    page.wait_for_load_state("domcontentloaded")
    has_function = page.evaluate(
        "typeof window.loadBrokers === 'function'"
    )
    assert has_function, (
        "Polish #7.5 regression: window.loadBrokers is gone from "
        "static/index.html. If intentionally renamed, update this contract "
        "test AND the .catch handler at the Polish #7.1 block."
    )
