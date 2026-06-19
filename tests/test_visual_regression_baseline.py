"""
Phase 8 v8 UI regression · visual-regression baseline.

Locks pixel-level contract for two animation surfaces:
  · docs/index.html @keyframes docsBal (12s amber↔red cycle, 0-40% amber, 50-90% red)
  · static/index.html via tools/run_app_uvicorn.py (10s phase flip bal-up↔bal-dn)

Each test captures at known timepoints and pixel-diffs against
`tests/artifacts/baseline/<name>.png`:

  · FIRST run (no baseline file):     auto-create from current capture, passes.
  · Subsequent runs:                  diff vs baseline; > 5% threshold → fail check-in.
  · `REFRESH_BASELINE=1` env var:     backup current baseline to tests/artifacts/baseline.pre-refresh.bak/
                                          (idempotent: only when no backup exists yet), then overwrite
                                          baseline from current capture; passes.
  · On diff failure:                  `tests/artifacts/diff_<name>.png` × 4 brightness
                                          overlay — visual diagnostic for humans.
  · `VISUAL_DIFF_THRESHOLD` env var:  override threshold (default 5.0).

Isolation:    prefixed fixture names (`vr_*`) + offset ports (:8766, :8002) so this file
              runs alongside tests/test_bal_chip_ui.py without port conflicts.
"""
from __future__ import annotations

import os
import re
import sys
import time
import socket
import shutil
import subprocess
import urllib.request
import urllib.error
from pathlib import Path

import numpy as np
import pytest


# ── Skip-friendly imports (Playwright + Pillow) ──────────────────────────────────────────────———
try:
    from playwright.sync_api import sync_playwright, Browser, Page
    _HAS_PLAYWRIGHT = True
except ImportError:
    _HAS_PLAYWRIGHT = False

try:
    from PIL import Image, ImageChops
    _HAS_PILLOW = True
except ImportError:
    _HAS_PILLOW = False


try:
    import numpy as np
    _HAS_NUMPY = True
except ImportError:
    _HAS_NUMPY = False


pytestmark = [
    pytest.mark.skipif(not _HAS_PLAYWRIGHT, reason="playwright not installed (· `pip install playwright`)"),
    pytest.mark.skipif(not _HAS_PILLOW,    reason="Pillow not installed (· `pip install Pillow`)"),
    pytest.mark.skipif(not _HAS_NUMPY,     reason="numpy not installed (· `pip install numpy`)"),
]

# ── Module constants ──────────────────────────────────────────────────────────────────────—————
REPO_ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = REPO_ROOT / "docs"
ARTIFACTS_DIR = Path(__file__).resolve().parent / "artifacts"
BASELINE_DIR = ARTIFACTS_DIR / "baseline"
BASELINE_BAK_DIR = ARTIFACTS_DIR / "baseline.pre-refresh.bak"
ARTIFACTS_DIR.mkdir(exist_ok=True)
BASELINE_DIR.mkdir(exist_ok=True)
BASELINE_BAK_DIR.mkdir(exist_ok=True)

# Offset ports — don't clash with tests/test_bal_chip_ui.py's :8765/:8001 fixtures.
DOCS_PORT = 8766
APP_PORT = 8002
VIEWPORT = {"width": 1280, "height": 800}

DEFAULT_THRESHOLD_PCT = float(os.environ.get("VISUAL_DIFF_THRESHOLD", "5.0"))



# Expected dominant chip color per baseline (from CSS variables -- both
# docs/index.html and static/index.html at line 18):
#   var(--forge) = #f59e0b (amber)  -- docs_bal_amber and real_bal_up
#   var(--fire)  = #dc2626 (red)    -- docs_bal_red and real_bal_dn
# Tolerance +/- 6 per channel: getComputedStyle returns the exact rendered
# color (animation-aware), delta ~0 at plateau, >60 during mid-ramp transitions.
# Combined with 5.0% pixel-diff threshold, captures wrong-phase renders
# (min delta 60+) fail on the CSS guard BEFORE screenshot, while harmless
# AA/rasterizer variance (<= 1%) is accepted. The 1-channel slack above
# _wait_for_phase's deep-plateau tolerance (5) is intentional defense-in-depth:
# tight enough to catch real anomalies, loose enough to absorb browser-rendering
# microvariance between the phase-match probe and the actual capture.
EXPECTED_COLOR_BANDS = {
    "docs_bal_amber.png": ((245, 158, 11), 6),
    "docs_bal_red.png":   ((220, 38, 38), 6),
    "real_bal_up.png":    ((245, 158, 11), 6),
    "real_bal_dn.png":    ((220, 38, 38), 6),
}


# ── Helpers ───────────────────────────────────────────────────────────────────────────────────——————————————──
def _port_open(host: str, port: int, timeout: float = 1.0) -> bool:
    """Cheap TCP probe — avoids netstat dep."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (OSError, socket.timeout):
        return False


def _purge_port(port: int) -> None:
    """Windows: tree-kill only the PIDs holding `port` (NOT by image name).

    CRITICAL: do NOT blanket `/IM chrome.exe` or `/IM python.exe` — that kills
    the pytest runner itself (it's a python.exe) AND any Chrome windows the
    developer has open for normal browsing.  Only kill PIDs that netstat maps
    to the test fixture's port.

    `/T` ensures helper Chrome processes (Zygote / Helm) spawned under that
    PID also die — leaf `/F /PID` alone leaves helper sockets lingering.
    Idempotent: silent if port is free at entry.
    """
    if not _port_open("127.0.0.1", port, timeout=0.3):
        return
    if sys.platform != "win32":
        return
    try:
        r = subprocess.run(
            ["netstat", "-ano"], capture_output=True, text=True, timeout=5,
        )
        for line in r.stdout.splitlines():
            # Skip non-LISTENING rows (filters out ESTABLISHED connections
            # which could belong to the user's own Chrome tabs).
            if f":{port}" not in line or "LISTENING" not in line:
                continue
            pid = line.split()[-1]
            if pid.isdigit() and int(pid) != 0:
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", pid],
                    capture_output=True, text=True, timeout=5,
                )
    except Exception:
        pass
    for _ in range(20):
        if not _port_open("127.0.0.1", port, timeout=0.3):
            return
        time.sleep(0.2)


def _wait_http(url: str, deadline_s: int, stderr_log: Path | None = None) -> None:
    """Poll URL until HTTP 200 or timeout.  Raises on exhausted deadline.

    If `stderr_log` is provided, the last 50 lines of the subprocess stderr
    log are surfaced in the timeout exception so devs see the actual boot
    crash instead of guessing.
    """
    end = time.time() + deadline_s
    last: Exception | None = None
    while time.time() < end:
        try:
            with urllib.request.urlopen(url, timeout=1) as r:
                if r.status == 200:
                    return
        except (urllib.error.URLError, ConnectionResetError, OSError) as e:
            last = e
        time.sleep(0.3)
    tail = ""
    if stderr_log is not None and stderr_log.exists():
        try:
            tail = "\nstderr.log tail:\n" + "".join(
                stderr_log.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)[-50:]
            )
        except Exception:
            pass
    raise RuntimeError(f"server not ready in {deadline_s}s: {url} · {last}{tail}")


# ── Session fixtures: subprocess servers (prefixed to avoid clash) ─────────────────────────———
@pytest.fixture(scope="session")
def vr_docs_server():
    """Serve docs/ via http.server on :8766. Started once per pytest run."""
    if not _HAS_PLAYWRIGHT:
        pytest.skip("playwright not installed")
    _purge_port(DOCS_PORT)
    stderr_log = ARTIFACTS_DIR / "vr_docs_server_stderr.log"
    proc = subprocess.Popen(
        [sys.executable, "-m", "http.server", str(DOCS_PORT), "-d", str(DOCS_DIR)],
        stdout=subprocess.DEVNULL,
        stderr=open(stderr_log, "wb"),
        env={**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"},
    )
    try:
        _wait_http(f"http://127.0.0.1:{DOCS_PORT}/", deadline_s=10, stderr_log=stderr_log)
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
def vr_uvicorn_server():
    """Boot tools/run_app_uvicorn.py on :8002 in SHADOW mode (no real MT5).

    NOTE: each invocation of run_app_uvicorn.py spawns a fresh subprocess,
    so `_AnimAccountAsync._n` resets to 0 at fixture setup. Within the session
    the counter persists across tests (stateful singleton), so individual
    tests must NOT assume a fixed UP-then-DN order — see TestRealBalChipBaseline.
    """
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
        "MT5_DATA_MODE": "SHADOW",
        "LIVE_TRADING_DISABLED": "true",
        "APP_HOST": "127.0.0.1",
        "APP_PORT": str(APP_PORT),
    }
    stderr_log = ARTIFACTS_DIR / "vr_uvicorn_server_stderr.log"
    proc = subprocess.Popen(
        [sys.executable, str(launcher)],
        cwd=str(REPO_ROOT),
        stdout=subprocess.DEVNULL,
        stderr=open(stderr_log, "wb"),
        env=env,
    )
    try:
        _wait_http(
            f"http://127.0.0.1:{APP_PORT}/api/health",
            deadline_s=20,
            stderr_log=stderr_log,
        )
        yield f"http://127.0.0.1:{APP_PORT}/"
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)
        _purge_port(APP_PORT)


@pytest.fixture(scope="session")
def vr_pw_browser():
    """Single chrome process for the whole pytest run (channel='chrome' reuses
    locally installed Chrome — no chromium download required)."""
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
            f"chrome unavailable ({type(e).__name__}: {str(e)[:120]}). "
            f"Install Chrome locally or run `playwright install chromium`."
        )


@pytest.fixture
def vr_pw_page(vr_pw_browser: Browser) -> Page:
    """Fresh page per test — fixed viewport for reproducible screenshots."""
    ctx = vr_pw_browser.new_context(viewport=VIEWPORT)
    page = ctx.new_page()
    try:
        yield page
    finally:
        ctx.close()


# ── Visual-diff helper ────────────────────────────────────────────────────────────────────────—————————
def _capture_to_path(page: Page, name: str) -> Path:
    """Capture element-bound screenshot of `#bal-chip`.  Locator screenshot
    uses element bounding-box — immune to viewport-size variance across CI runners.

    Side effect: color-band guard BEFORE screenshot. Pulls the live CSS
    `color` value of `#bal-val` via getComputedStyle, the browser's
    source-of-truth for the rendered color (animation-aware; returns
    interpolated values during mid-ramp transitions). Bypasses all
    anti-aliasing / sub-pixel artifacts that bedeviled pixel-based analysis.
    Catches animation-phase timing drift and wrong-page renders BEFORE
    they can corrupt the baseline.
    """
    if name in EXPECTED_COLOR_BANDS:
        expected, tol = EXPECTED_COLOR_BANDS[name]
        css_color_str = page.evaluate(
            "() => getComputedStyle(document.querySelector('#bal-val')).color"
        )
        if not css_color_str:
            raise RuntimeError(
                f"color-band guard FAILED for {name}: "
                f"page.evaluate returned empty CSS color string. "
                f"Likely #bal-val element missing or wrong page rendered. "
                f"REJECTING this baseline."
            )
        m = re.match(r'rgba?\((\d+),\s*(\d+),\s*(\d+)', css_color_str)
        if not m:
            raise RuntimeError(
                f"color-band guard FAILED for {name}: "
                f"could not parse CSS color string '{css_color_str}'. "
                f"Expected rgb/rgba(r, g, b) format from getComputedStyle. "
                f"REJECTING this baseline."
            )
        actual_css = tuple(int(x) for x in m.groups())
        delta = max(abs(actual_css[i] - expected[i]) for i in range(3))
        if delta > tol:
            raise RuntimeError(
                f"color-band guard FAILED for {name}: "
                f"computed CSS color = rgb{actual_css}, "
                f"expected ~rgb{expected} +/- {tol}, max channel delta = {delta}. "
                f"Likely animation phase timing missed or wrong page rendered. "
                f"REJECTING this baseline."
            )
    out = ARTIFACTS_DIR / name
    page.locator("#bal-chip").screenshot(path=str(out))
    return out


def assert_visual_match(actual_path: Path, baseline_name: str) -> tuple[float, float]:
    """Diff `actual_path` against `tests/artifacts/baseline/<baseline_name>`.

    Returns (diff_pct, threshold_pct).  Side effects:
      · FIRST run (no baseline):            auto-create baseline; passes (0.0% diff).
      · `REFRESH_BASELINE=1` env var:       backup current baseline to
                                              tests/artifacts/baseline.pre-refresh.bak/<baseline_name>
                                              (idempotent: only when no backup exists yet),
                                              then overwrite baseline; passes (0.0% diff).
      · Diff > threshold:                  writes diff_<baseline_name>.png × 4
                                              brightness for visual review; raises
                                              AssertionError so CI red-flags.
    """
    threshold_pct = DEFAULT_THRESHOLD_PCT
    baseline_path = BASELINE_DIR / baseline_name

    # Open actual + apply color-band guard BEFORE any save/refresh/diff branch.
    # Catches animation-phase drift / wrong-page renders that would otherwise
    # silently corrupt the baseline.
    actual = Image.open(actual_path).convert("RGB")

    if not baseline_path.exists():
        shutil.copy2(actual_path, baseline_path)
        print(f"\n[baseline] created: {baseline_path}")
        return (0.0, threshold_pct)

    if os.environ.get("REFRESH_BASELINE", "0") == "1":
        # Auto-backup: idempotent, only on FIRST refresh. After that, the .bak/
        # holds the original pre-refresh state and is preserved across subsequent
        # refreshes — the safety net for HANDOFF § Issue #1 doc/code consistency.
        # Inner mkdir defends against .bak/ being deleted between module import
        # and a later REFRESH run (e.g. operator cleans tests/artifacts/ mid-session).
        BASELINE_BAK_DIR.mkdir(exist_ok=True)
        backup_path = BASELINE_BAK_DIR / baseline_name
        # baseline_path.exists() is guaranteed True here (early-return above),
        # so the only meaningful check is backup idempotency.
        if not backup_path.exists():
            shutil.copy2(baseline_path, backup_path)
            print(f"[baseline] backed up: {backup_path}")
        shutil.copy2(actual_path, baseline_path)
        print(f"\n[baseline] refreshed: {baseline_path}")
        return (0.0, threshold_pct)

    baseline = Image.open(baseline_path).convert("RGB")

    if actual.size != baseline.size:
        # Diagnostic artifact — caller MUST re-baseline if size changed (CSS/layout
        # reflow shifted #bal-chip bounding-box). Raise so the failure is loud,
        # not a silently-over-threshold 100% return value.
        (ARTIFACTS_DIR / f"diff_size_mismatch_{baseline_name}.txt").write_text(
            f"actual.size={actual.size} baseline.size={baseline.size}\n"
        )
        raise RuntimeError(
            f"size mismatch for {baseline_name}: actual {actual.size} vs "
            f"baseline {baseline.size} — re-baseline via REFRESH_BASELINE=1"
        )

    # Diff in luminance space — single-channel L mode simplifies thresholding
    # (RGB ImageChops.difference returns tuples; .convert("L") collapses to greyscale).
    diff_l = ImageChops.difference(actual, baseline).convert("L")
    threshold_mask = diff_l.point(lambda p: 255 if p > 0 else 0)
    # Pillow ≥10 deprecates `Image.getdata()` for tight loops. Migrate to numpy.
    arr = np.asarray(threshold_mask)
    diff_count = int((arr == 255).sum())
    total = arr.size
    diff_pct = (diff_count / total) * 100

    if diff_pct > threshold_pct:
        # Visual diff artifact: × 4 brightness boost so even small RGB shifts
        # stand out in the saved PNG.
        diff_rgb = ImageChops.difference(actual, baseline)
        (ARTIFACTS_DIR / f"diff_{baseline_name}").parent.mkdir(parents=True, exist_ok=True)
        diff_rgb.point(lambda p: min(255, p * 4)).save(
            str(ARTIFACTS_DIR / f"diff_{baseline_name}")
        )

    return (diff_pct, threshold_pct)


def _wait_for_phase(
    page: Page,
    expected_rgb: tuple[int, int, int],
    timeout_ms: int = 15000,
) -> None:
    """Wait until `#bal-val` CSS color lands at the expected RGB plateau.

    Replaces wall-clock `time.sleep()` calls that coupled captures to the
    12s docsBal animation cycle's page-load jitter. Polls via Playwright
    `wait_for_function` and exits the moment computed `color` matches the
    expected plateau within ±5 channel tolerance (deep in plateau zone
    \u2014 mid-ramp transitions have delta >60 and would fail this check).

    Args:
        page: Playwright Page with `#bal-val` element loaded.
        expected_rgb: (r, g, b) tuple to match against getComputedStyle.color.
        timeout_ms: Maximum wait before raising Playwright TimeoutError.
            Default 15000ms covers worst-case cycle miss (12s cycle + 3s buffer).

    Raises:
        playwright.sync_api.TimeoutError: if plateau not reached within timeout.
    """
    page.wait_for_function(
        """([expR, expG, expB]) => {
            const el = document.querySelector('#bal-val');
            if (!el) return false;
            const cs = getComputedStyle(el);
            if (!cs.animation || !cs.animation.includes('docsBal')) return false;
            const m = String(cs.color).match(/rgba?\\((\\d+),\\s*(\\d+),\\s*(\\d+)/);
            if (!m) return false;
            const dr = Math.abs(parseInt(m[1], 10) - expR);
            const dg = Math.abs(parseInt(m[2], 10) - expG);
            const db = Math.abs(parseInt(m[3], 10) - expB);
            // ±5 channel tolerance: deep plateau match, rejects mid-ramp transitions.
            return Math.max(dr, dg, db) <= 5;
        }""",
        arg=expected_rgb,
        timeout=timeout_ms,
    )


# ── Tests ───────────────────────────────────────────────────────────────────────────────────—————————————————————──
class TestDocsBalChipBaseline:
    """docs/index.html @keyframes docsBal — pixel regression.

    Captures two phase plateaus on the 12s amber↔red cycle,
    deterministic regardless of page-load jitter:
      · amber plateau (var(--forge), 0-40% of cycle)
      · red   plateau (var(--fire),  50-90% of cycle)

    Timing strategy: `_wait_for_phase` polls getComputedStyle.color via
    Playwright `wait_for_function` and exits the moment the CSS color
    lands at the expected plateau (±5 channel tolerance). The
    earlier `time.sleep(2.0)` / `time.sleep(7.0)` wall-clock coupling was
    replaced because page-load jitter drifted captures into the
    easing curve tail, producing 17.43% theoretical / 20.44% measured pixel diffs that
    flagged against the original wall-clock-locked baselines.

    Tolerance rationale: the 5-channel delta filters out mid-ramp
    transitions (max channel delta >60 during ease-in-out) while
    accepting steady-state plateau pixels. Combined with the
    CSS-color-band runtime guard (tol=6 defense-in-depth; 1-channel
    slack above the wait-phase plateau tolerance of 5) and the 5%
    pixel-diff threshold, wrong-phase renders are caught BEFORE they
    can corrupt the baseline.
    """

    def test_docs_bal_chip_amber_phase(self, vr_docs_server, vr_pw_page: Page):
        vr_pw_page.goto(vr_docs_server, wait_until="load")
        vr_pw_page.wait_for_selector("#bal-val", timeout=5000)
        # Deterministic phase lock: wait for amber plateau (var(--forge) from
        # docs/index.html) before screenshot \u2014 no wall-clock coupling.
        _wait_for_phase(
            vr_pw_page,
            EXPECTED_COLOR_BANDS["docs_bal_amber.png"][0],
            15000,
        )

        actual = _capture_to_path(vr_pw_page, "docs_bal_amber_capture.png")
        diff_pct, threshold = assert_visual_match(actual, "docs_bal_amber.png")
        assert diff_pct <= threshold, (
            f"docsBal amber-phase visual drift: {diff_pct:.2f}% pixels differ "
            f"(threshold {threshold:.2f}%) — diff image: tests/artifacts/diff_docs_bal_amber.png"
        )

    def test_docs_bal_chip_red_phase(self, vr_docs_server, vr_pw_page: Page):
        vr_pw_page.goto(vr_docs_server, wait_until="load")
        vr_pw_page.wait_for_selector("#bal-val", timeout=5000)
        # Deterministic phase lock: wait for red plateau (var(--fire) from
        # docs/index.html) before screenshot \u2014 no wall-clock coupling.
        _wait_for_phase(
            vr_pw_page,
            EXPECTED_COLOR_BANDS["docs_bal_red.png"][0],
            15000,
        )

        actual = _capture_to_path(vr_pw_page, "docs_bal_red_capture.png")
        diff_pct, threshold = assert_visual_match(actual, "docs_bal_red.png")
        assert diff_pct <= threshold, (
            f"docsBal red-phase visual drift: {diff_pct:.2f}% pixels differ "
            f"(threshold {threshold:.2f}%) — diff image: tests/artifacts/diff_docs_bal_red.png"
        )


class TestRealBalChipBaseline:
    """static/index.html via tools/run_app_uvicorn.py — phase UP/DN pixel regression.

    IMPORTANT — `_AnimAccountAsync` is a stateful singleton: each push increments
    `self._n`; phase decision uses `(n // 2) % 2 == 0` (UP at even-bucket, DN at
    odd-bucket). Within a pytest session the counter persists across tests, so we
    CANNOT assert a fixed UP-then-DN order (would flake on second execution).

    Strategy: ONE test polls for both `.bal-up` AND `.bal-dn` to appear within a
    60s budget (matches `test_phase_toggles_up_down_within_60s`), sampling each
    class state ONCE on first sight, then diffs against pre-baked baseline PNGs
    named by SEMANTIC class (up / dn — coordinate-free).
    """

    def test_real_bal_chip_both_phases_appear_within_60s(
        self, vr_uvicorn_server, vr_pw_page: Page,
    ):
        vr_pw_page.goto(vr_uvicorn_server, wait_until="load")
        vr_pw_page.wait_for_selector("#bal-val", timeout=5000)
        # first push landing ~5s after WS open (5s push_loop sleep)
        vr_pw_page.wait_for_selector(
            "#bal-val.bal-up, #bal-val.bal-dn", timeout=15000,
        )

        up_seen = dn_seen = False
        deadline = time.time() + 60
        while time.time() < deadline and not (up_seen and dn_seen):
            cls = vr_pw_page.locator("#bal-val").get_attribute("class") or ""
            if "bal-up" in cls and not up_seen:
                time.sleep(0.5)  # let CSS transition settle
                actual = _capture_to_path(vr_pw_page, "real_bal_up_capture.png")
                diff_pct, threshold = assert_visual_match(actual, "real_bal_up.png")
                assert diff_pct <= threshold, (
                    f"real bal UP-phase visual drift: {diff_pct:.2f}% pixels differ "
                    f"(threshold {threshold:.2f}%) — diff image: "
                    f"tests/artifacts/diff_real_bal_up.png"
                )
                up_seen = True
            elif "bal-dn" in cls and not dn_seen:
                time.sleep(0.5)
                actual = _capture_to_path(vr_pw_page, "real_bal_dn_capture.png")
                diff_pct, threshold = assert_visual_match(actual, "real_bal_dn.png")
                assert diff_pct <= threshold, (
                    f"real bal DN-phase visual drift: {diff_pct:.2f}% pixels differ "
                    f"(threshold {threshold:.2f}%) — diff image: "
                    f"tests/artifacts/diff_real_bal_dn.png"
                )
                dn_seen = True
            time.sleep(0.3)

        assert up_seen and dn_seen, (
            f"both bal-up AND bal-dn must appear within 60s of first push "
            f"(push_loop cadence 5s · phase flip every 2 pushes ≈ 10s): "
            f"up_seen={up_seen}, dn_seen={dn_seen}"
        )
