"""
Phase 8 v8 UI regression tests — Playwright BAL chip color-toggle lock
=====================================================================

Two sites, one chip, two regression surfaces:

  1) docs/index.html  — static GitHub Pages mirror.  No backend.  BAL chip #bal-val
     is set to "10000/9970" after page load and enrolled into CSS @keyframes docsBal
     (12s amber↔red ease-in-out infinite) by docs/index.html's `initBackend` IIFE.

  2) static/index.html (real demo via tools/run_app_uvicorn.py on :8001) — full
     backend.  The launcher injects an animated account_info_async with phase UP
     (equity ∈ [10200,10600]) and DN (equity ∈ [9400,9800]) flipping every 2 calls
     (~10s given the 5s WS push_loop).  BAL chip #bal-val className gets appended
     `bal-up` (green) when equity >= balance, `bal-dn` (red) when below.

These tests skip cleanly module-wide if Playwright is not installed — run app CI
with `pip install playwright` (or use Chrome's installed browser via channel=chrome,
no ~150MB chromium download needed) to opt in.  Without the opt-in `pytest -q tests/`
exits "no tests ran" courtesy of pytestmark skipif.

Channel="chrome" reuses the locally installed Chrome (per SYSTEM_INFO: Chrome
installed) so `playwright install chromium` is NOT required.

Fixture lifecycle:
  · docs_server      (session) - http.server :8765 -d <repo>/docs
  · uvicorn_server   (session) - tools/run_app_uvicorn.py on :8001 (SHADOW mode)
  · pw_browser       (session) - one chrome process for the whole run
  · pw_page          (function) - fresh page per test, fresh nav, no cross-test pollution
"""
from __future__ import annotations

import json
import os
import sys
import time
import socket
import subprocess
import urllib.request
import urllib.error
from pathlib import Path

import pytest


# ── Skip-friendly import for environments without Playwright ────────────────
try:
    from playwright.sync_api import sync_playwright, Browser, Page
    _HAS_PLAYWRIGHT = True
except ImportError:
    _HAS_PLAYWRIGHT = False

pytestmark = pytest.mark.skipif(
    not _HAS_PLAYWRIGHT,
    reason="playwright not installed — `pip install playwright` to opt in · uses channel='chrome' so no chromium download required",
)
# Note: tests/conftest.py defines `_project_root` as autouse so no
# `pytestmark = pytest.mark.usefixtures(...)` is required — that line
# would overwrite the skipif above.


# ── Module constants ────────────────────────────────────────────────────────
REPO_ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = REPO_ROOT / "docs"
ARTIFACTS_DIR = Path(__file__).resolve().parent / "artifacts"
ARTIFACTS_DIR.mkdir(exist_ok=True)

DOCS_PORT = 8765
APP_PORT = 8001


# ── Helpers ─────────────────────────────────────────────────────────────────
def _port_open(host: str, port: int, timeout: float = 1.0) -> bool:
    """Cheap TCP probe — avoids netstat dep."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (OSError, socket.timeout):
        return False


def _purge_port(port: int) -> None:
    """Windows: best-effort kill anything holding `port`.  Idempotent."""
    if not _port_open("127.0.0.1", port, timeout=0.3):
        return
    if sys.platform != "win32":
        return
    try:
        r = subprocess.run(
            ["netstat", "-ano"], capture_output=True, text=True, timeout=5,
        )
        for line in r.stdout.splitlines():
            if f":{port}" in line and "LISTENING" in line:
                pid = line.split()[-1]
                if pid.isdigit():
                    subprocess.run(
                        ["taskkill", "/F", "/PID", pid],
                        capture_output=True, text=True, timeout=5,
                    )
    except Exception:
        pass
    # Settle
    for _ in range(10):
        if not _port_open("127.0.0.1", port, timeout=0.3):
            return
        time.sleep(0.2)


def _wait_http(url: str, deadline_s: int = 15) -> None:
    """Poll URL until HTTP 200 or timeout.  Raises on exhausted deadline."""
    end = time.time() + deadline_s
    last_err: Exception | None = None
    while time.time() < end:
        try:
            with urllib.request.urlopen(url, timeout=1) as r:
                if r.status == 200:
                    return
        except (urllib.error.URLError, ConnectionResetError, OSError) as e:
            last_err = e
        time.sleep(0.3)
    raise RuntimeError(f"server not ready within {deadline_s}s: {url} · last_err={last_err}")


def _parse_frame(raw) -> dict | None:
    """Decode bytes/str frame payload, parse JSON. Returns parsed dict or None
    on any failure (decode error, JSON parse error, non-string/bytes input).

    `routes_ws.py` uses `websocket.send_json(...)` so str is expected, but
    defensive bytes handling guards against future client upgrades that
    switch to binary frames.
    """
    if isinstance(raw, bytes):
        try:
            raw = raw.decode("utf-8")
        except UnicodeDecodeError:
            return None
    try:
        return json.loads(raw)
    except (ValueError, TypeError):
        return None


def _is_account_update(raw) -> bool:
    """True if WebSocket frame payload is an account_update JSON.

    Thin wrapper over `_parse_frame` for the most common frame-shape check.
    """
    return (_parse_frame(raw) or {}).get("type") == "account_update"


# ── Session fixtures: subprocess servers ────────────────────────────────────
@pytest.fixture(scope="session")
def docs_server():
    """Serve docs/ via http.server on :8765.  Started once per pytest run."""
    if not _HAS_PLAYWRIGHT:
        pytest.skip("playwright not installed")
    if not DOCS_DIR.exists():
        pytest.skip(f"docs dir missing: {DOCS_DIR}")
    _purge_port(DOCS_PORT)
    proc = subprocess.Popen(
        [sys.executable, "-m", "http.server", str(DOCS_PORT), "-d", str(DOCS_DIR)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        # Force UTF-8 so any startup log written to a captured pipe doesn't break codec-wise
        env={**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"},
    )
    try:
        _wait_http(f"http://127.0.0.1:{DOCS_PORT}/", deadline_s=10)
        yield f"http://127.0.0.1:{DOCS_PORT}/"
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=3)
        _purge_port(DOCS_PORT)


@pytest.fixture(scope="session")
def uvicorn_server():
    """Boot tools/run_app_uvicorn.py on :8001 in SHADOW mode (no real MT5)."""
    if not _HAS_PLAYWRIGHT:
        pytest.skip("playwright not installed")
    launcher = REPO_ROOT / "tools" / "run_app_uvicorn.py"
    if not launcher.exists():
        pytest.skip(f"launcher missing: {launcher}")
    _purge_port(APP_PORT)
    env = {
        **os.environ,
        "PYTHONIOENCODING": "utf-8",
        "PYTHONUTF8": "1",
        "MT5_DATA_MODE": "SHADOW",           # default; explicit for clarity
        "LIVE_TRADING_DISABLED": "true",     # safety: any /api/buy stays 423
        "APP_HOST": "127.0.0.1",
        "APP_PORT": str(APP_PORT),
    }
    proc = subprocess.Popen(
        [sys.executable, str(launcher)],
        cwd=str(REPO_ROOT),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=env,
    )
    try:
        # Uvicorn lifespan startup observes bridge + data_pool pre-stub — needs ~6s
        _wait_http(f"http://127.0.0.1:{APP_PORT}/api/health", deadline_s=20)
        yield f"http://127.0.0.1:{APP_PORT}/"
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)
        _purge_port(APP_PORT)


# ── Playwright lifecycle ────────────────────────────────────────────────────
@pytest.fixture(scope="session")
def pw_browser():
    """One chrome process for the whole pytest run.  channel='chrome' reuses
    the locally installed Chrome (no chromium download required).  Falls back
    to skip if Chrome is unavailable on the test box."""
    if not _HAS_PLAYWRIGHT:
        pytest.skip("playwright not installed")
    headless = os.environ.get("BAL_CHIP_HEADED", "0") != "1"
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(channel="chrome", headless=headless)
            yield browser
            browser.close()
    except Exception as e:
        pytest.skip(
            f"chrome channel unavailable ({type(e).__name__}: {str(e)[:120]}). "
            f"Install Chrome locally or run `playwright install chromium`."
        )


@pytest.fixture
def pw_page(pw_browser: Browser) -> Page:
    """Fresh page per test — no cross-test pollution."""
    ctx = pw_browser.new_context()
    page = ctx.new_page()
    console_errors: list[str] = []
    page.on(
        "console",
        lambda msg: console_errors.append(f"[{msg.type}] {msg.text}")
        if msg.type in {"error", "warning"}
        else None,
    )
    try:
        yield page
    finally:
        fatal = [m for m in console_errors if m.startswith("[error]")]
        if fatal:
            print(f"\n=== console errors during test ===\n" + "\n".join(fatal[:20]))
        ctx.close()


# ── Tests ───────────────────────────────────────────────────────────────────
class TestDocsBalChip:
    """docs/index.html — @keyframes docsBal-driven mock WS push simulation."""

    def test_bal_val_enrolled_into_docs_animation(self, docs_server, pw_page: Page):
        pw_page.goto(docs_server, wait_until="domcontentloaded")

        # Wait for chip element
        pw_page.wait_for_selector("#bal-val", timeout=5000)

        # Confirms docs/index.html initBackend IIFE ran: animation includes 'docsBal'
        pw_page.wait_for_function(
            """() => {
                const el = document.querySelector('#bal-val');
                if (!el) return false;
                const cs = getComputedStyle(el);
                return cs.animation && cs.animation.includes('docsBal');
            }""",
            timeout=5000,
        )

        # Pre-filled text 10000/9970 confirms IIFE setTimeout fired
        pw_page.wait_for_function(
            "() => (document.querySelector('#bal-val')?.textContent || '').includes('10000/9970')",
            timeout=5000,
        )

        # BAL chip tooltip should reflect DOCS DEMO source
        tip = pw_page.locator("#bal-chip").get_attribute("data-tip") or ""
        assert "DOCS DEMO" in tip, f"toolbar tooltip should mention DOCS DEMO: got {tip!r}"

        # Snapshot for visual regression debugging
        pw_page.screenshot(
            path=str(ARTIFACTS_DIR / "docs_bal_chip_anim.png"),
            full_page=False,
        )

    def test_docs_animation_metadata(self, docs_server, pw_page: Page):
        """Lock animation params: 12s ease-in-out infinite.  If someone tweaks
        the duration in the docs override, this fires."""
        pw_page.goto(docs_server, wait_until="domcontentloaded")
        pw_page.wait_for_selector("#bal-val", timeout=5000)
        pw_page.wait_for_function(
            """() => {
                const el = document.querySelector('#bal-val');
                if (!el) return false;
                const cs = getComputedStyle(el);
                return cs.animation && cs.animation.includes('docsBal');
            }""",
            timeout=5000,
        )

        anim = pw_page.evaluate(
            """() => {
                const cs = getComputedStyle(document.querySelector('#bal-val'));
                return {
                    name: cs.animationName,
                    duration: cs.animationDuration,
                    timing: cs.animationTimingFunction,
                    iter: cs.animationIterationCount,
                };
            }"""
        )
        assert anim["name"] == "docsBal", f"animation-name should be docsBal: got {anim}"
        assert "12s" in anim["duration"], f"animation-duration should be 12s: got {anim}"
        assert anim["timing"] in {"ease-in-out", "ease"}, f"timing should be ease-*: got {anim}"
        assert anim["iter"] == "infinite", f"iteration should be infinite: got {anim}"

    def test_docs_fetch_overlay_seeded(self, docs_server, pw_page: Page):
        """docs/index.html fetch('./demo-data.json') overlays SEED_SYMBOLS with
        the 17 demo candidates documented in docs/demo-data.json.

        Strict distinction: renderScreenTable() tags every <tr> with
        data-source="${d._src||'seed'}".  fetch() overlay sets d._src='demo-json'
        on each item before pushing into SEED_SYMBOLS.  SEED items have no
        _src → fall back to 'seed'.

        Asserts:
          · ≥17 rows tagged `data-source="demo-json"` proves the fetch
            ENRICHMENT landed (SEED-alone path is 17 `data-source="seed"`,
            which is structurally distinct from ≥17 `data-source="demo-json"`
            even though both have 17 entries).
          · 0 rows tagged `data-source="seed"` proves the overlay REPLACED
            (not appended) SEED_SYMBOLS.
        """
        pw_page.goto(docs_server, wait_until="domcontentloaded")
        # Wait for first render (any row) so wait_for_function on overlay is meaningful.
        pw_page.wait_for_function(
            """() => document.querySelectorAll('table tbody tr').length > 0""",
            timeout=8000,
        )
        # Distinctive: demo rows are tagged `data-source=demo-json` after fetch overlay.
        pw_page.wait_for_function(
            """() => document.querySelectorAll('tr[data-source="demo-json"]').length >= 17""",
            timeout=8000,
        )
        demo_count = pw_page.evaluate(
            """() => document.querySelectorAll('tr[data-source="demo-json"]').length"""
        )
        seed_count = pw_page.evaluate(
            """() => document.querySelectorAll('tr[data-source="seed"]').length"""
        )
        # ≥17 demo rows: fetch overlay landed, and demo candidates > 0.
        assert demo_count >= 17, (
            f"expected ≥17 demo-tagged rows (fetch overlay landed): got {demo_count}"
        )
        # 0 seed rows: SEED_SYMBOLS was REPLACED, not appended.  This catches the
        # classic bug of doing SEED_SYMBOLS.push(...) instead of SEED_SYMBOLS.length=0; push.apply(...).
        assert seed_count == 0, (
            f"expected 0 seed-tagged rows after overlay (replaced): got {seed_count} — "
            "fetch overlay may have appended instead of replaced SEED_SYMBOLS"
        )
        # Sanity: total rows = demo_count, no extras.
        total = pw_page.evaluate(
            """() => document.querySelectorAll('table tbody tr').length"""
        )
        assert total == demo_count, (
            f"table tbody row count ({total}) diverged from demo rows ({demo_count}) — "
            "unexpected rows without data-source"
        )


class TestRealBalChip:
    """static/index.html via tools/run_app_uvicorn.py — WS-driven toggle."""

    def test_first_ws_push_reaches_chip_within_15s(self, uvicorn_server, pw_page: Page):
        pw_page.goto(uvicorn_server, wait_until="domcontentloaded")
        pw_page.wait_for_selector("#bal-val", timeout=5000)

        # First push expected within ~5-10s of WS open.
        pw_page.wait_for_selector("#bal-val.bal-up, #bal-val.bal-dn", timeout=15000)

        cls = pw_page.locator("#bal-val").get_attribute("class") or ""
        assert "mbtn" in cls, f"chip should still carry base 'mbtn' class: got {cls!r}"
        assert ("bal-up" in cls) or ("bal-dn" in cls), \
            f"chip should be 'mbtn bal-up' or 'mbtn bal-dn' after first WS push: got {cls!r}"

        head = cls.replace(" ", "_")
        pw_page.screenshot(path=str(ARTIFACTS_DIR / f"real_bal_first_{head}.png"))

    def test_phase_toggles_up_down_within_60s(self, uvicorn_server, pw_page: Page):
        """Phase UP/DN flips every 2 calls (~10s).  In a 60s window we should
        observe BOTH 'bal-up' and 'bal-dn' chip states."""
        pw_page.goto(uvicorn_server, wait_until="domcontentloaded")
        pw_page.wait_for_selector("#bal-val", timeout=5000)

        # Capture initial push
        pw_page.wait_for_selector("#bal-val.bal-up, #bal-val.bal-dn", timeout=15000)
        initial = pw_page.locator("#bal-val").get_attribute("class") or ""
        saw_up = "bal-up" in initial
        saw_dn = "bal-dn" in initial

        # Wait up to 60s for the inverse class to appear in the chip
        deadline = time.time() + 60
        while time.time() < deadline:
            cls = pw_page.locator("#bal-val").get_attribute("class") or ""
            if "bal-up" in cls and not saw_up:
                saw_up = True
            if "bal-dn" in cls and not saw_dn:
                saw_dn = True
            if saw_up and saw_dn:
                break
            # WS pushes every ~5s; a classname poll every 0.5s is plenty.
            time.sleep(0.5)

        assert saw_up, "chip never entered bal-up state within 60s"
        assert saw_dn, "chip never entered bal-dn state within 60s"

        final = pw_page.locator("#bal-val").get_attribute("class") or ""
        pw_page.screenshot(path=str(ARTIFACTS_DIR / "real_bal_toggled.png"))
        # Final sanity: chip class is one of the two allowed shapes
        assert ("bal-up" in final) ^ ("bal-dn" in final), \
            f"final chip state must be exactly one of bal-up|bal-dn: got {final!r}"

    def test_ws_account_update_frame_shape_and_interval(self, uvicorn_server, pw_page: Page):
        """Capture WebSocket frames via page-side monkey-patch of window.WebSocket.

        Locks the wire-format of `account_update` frames emitted by
        api/routes_ws.py.  Catches regressions in:
          · account_update SHAPE:  data.balance + data.equity + data.leverage are
            numeric (not null / not string).  Matches `_serialize_account` contract.
          · 5s PUSH INTERVAL:  consecutive account_update frames arrive 4.5-6.5s
            apart.  Catches accidental change to push_loop cadence.
          · /api/ws ROUTING:  page opens URL ending in `/api/ws`.

        Why monkey-patch instead of `pw_page.on("websocket", ...)`:
          Playwright Python's `framereceived` event is unreliable in headless
          mode (frames dropped or not delivered to the listener).  Monkey-patching
          window.WebSocket captures frames via the PAGE'S own addEventListener
          call, which always fires for every WS message regardless of Playwright
          dispatch state.
        """
        # ── 1. Inject init script BEFORE goto: wrap window.WebSocket constructor
        # to capture every `message` event into window.__yujin_frames[].
        # WrappedWS preserves original prototype + constants so page code still
        # works (instanceof WebSocket, readyState checks, etc.).
        pw_page.add_init_script("""
            (() => {
                window.__yujin_frames = [];
                const OrigWS = window.WebSocket;
                function WrappedWS(url, protocols) {
                    const ws = protocols ? new OrigWS(url, protocols) : new OrigWS(url);
                    ws.addEventListener('message', (e) => {
                        try {
                            window.__yujin_frames.push({
                                t: Date.now(),
                                url: url,
                                raw: typeof e.data === 'string' ? e.data : ''
                            });
                        } catch (_) { /* swallow */ }
                    });
                    return ws;
                }
                WrappedWS.prototype = OrigWS.prototype;
                WrappedWS.CONNECTING = OrigWS.CONNECTING;
                WrappedWS.OPEN = OrigWS.OPEN;
                WrappedWS.CLOSING = OrigWS.CLOSING;
                WrappedWS.CLOSED = OrigWS.CLOSED;
                window.WebSocket = WrappedWS;
            })();
        """)

        pw_page.goto(uvicorn_server, wait_until="domcontentloaded")

        # ── 2. Defensive: some builds gate WS-open on SOURCE=backend toggle.
        # Click source-btn after 15s if no frames yet, then keep waiting.
        deadline_open = time.time() + 30
        clicked = False
        while time.time() < deadline_open:
            n = pw_page.evaluate("() => (window.__yujin_frames || []).length")
            if n > 0:
                break
            time.sleep(0.5)
            if not clicked and time.time() > deadline_open - 15:
                try:
                    pw_page.locator("#source-btn").click()
                    clicked = True
                except Exception:
                    pass

        # ── 3. Wait until ≥2 account_update frames captured.
        # push_loop cadence is 5s + WS connect ~2s ⇒ first frame ~t≈7s, second
        # ~t≈12s.  Page-side monkey-patch captures deterministically, no need
        # for generous slack here.  30s is plenty (5+ push cycles).
        deadline = time.time() + 30
        while time.time() < deadline:
            n = pw_page.evaluate(
                """() => (window.__yujin_frames || []).filter(f => {
                    try { return JSON.parse(f.raw).type === 'account_update'; }
                    catch (e) { return false; }
                }).length"""
            )
            if n >= 2:
                break
            time.sleep(0.5)

        # ── 4. URL contract: page opened ws at /api/ws
        all_frames = pw_page.evaluate("() => window.__yujin_frames || []")
        assert all_frames, (
            f"no WebSocket frames captured via window.__yujin_frames — "
            f"page may not have opened WS at uvicorn_server={uvicorn_server}"
        )
        api_ws_urls = {f["url"] for f in all_frames if "/api/ws" in (f.get("url") or "")}
        assert api_ws_urls, (
            f"no frame URL contains /api/ws; URLs seen: "
            f"{[f.get('url') for f in all_frames[:5]]!r}"
        )

        # ── 5. Collect account_update events; uses _parse_frame for str|bytes-safe decode.
        acct_events: list[dict] = []
        for f in all_frames:
            parsed = _parse_frame(f.get("raw") or "")
            if parsed and parsed.get("type") == "account_update":
                acct_events.append({"t": f["t"], "data": parsed.get("data") or {}})

        assert len(acct_events) >= 2, (
            f"expected ≥2 account_update frames within 30s window: got {len(acct_events)} "
            f"(total_frames={len(all_frames)})"
        )

        # ── 6. Shape contract: balance + equity + leverage are numeric
        for i, ev in enumerate(acct_events[:3]):
            d = ev["data"]
            for k in ("balance", "equity", "leverage"):
                v = d.get(k)
                assert isinstance(v, (int, float)), (
                    f"account_update[{i}].data.{k} must be number — got "
                    f"{type(v).__name__}={v!r}"
                )

        # ── 7. Timing contract: ~5s cadence (t values are page-side Date.now() in ms)
        for i in range(1, len(acct_events)):
            gap_s = (acct_events[i]["t"] - acct_events[i - 1]["t"]) / 1000.0
            assert 4.5 <= gap_s <= 6.5, (
                f"account_update[{i}] → [{i - 1}] gap must be ~5s "
                f"(push_loop sleeps 5s in routes_ws.py): got {gap_s:.2f}s"
            )

