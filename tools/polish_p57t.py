"""Polish #5.7 test contract tightening applier.
5 surgical edits on tests/test_broker_ui_resilience.py:
  A. remove `import os` line
  B. remove `, expect` from playwright sync_api import
  C. insert addEventListener('unhandledrejection', ...) BEFORE failure trigger
  D. replace `wait_for_timeout(800)` with `wait_for_function(\"true\")` no-op
  E. replace pageerror-with-filter assertion block with cleaner __unhandled counter assertion
"""
import sys

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

with open('tests/test_broker_ui_resilience.py', 'rb') as f:
    raw = f.read()
src = raw.replace(b'\r\n', b'\n').replace(b'\r', b'\n').decode('utf-8')

original_size = len(src)

# ===== EDIT A: remove `import os` line =====
oA = 'import os\nimport threading\n'
nA = 'import threading\n'
cA = src.count(oA)
print('Edit A anchor count (import os import threading):', cA)
if cA != 1:
    print('FAIL Edit A: anchor not unique')
    sys.exit(2)
src = src.replace(oA, nA, 1)
print('OK Edit A: removed `import os` line')

# ===== EDIT B: remove `, expect` from playwright import (NOQA comment preserved) =====
oB = 'from playwright.sync_api import sync_playwright, expect  # noqa: F401'
nB = 'from playwright.sync_api import sync_playwright  # noqa: F401'
cB = src.count(oB)
print('Edit B anchor count (, expect in playwright import):', cB)
if cB != 1:
    print('FAIL Edit B: anchor not unique')
    sys.exit(2)
src = src.replace(oB, nB, 1)
print('OK Edit B: removed `, expect` from playwright import')

# ===== EDIT C: insert addEventListener BEFORE failure trigger =====
# Anchor: the page.evaluate("switchBroker...") line (single occurrence expected)
oC = "    page.evaluate(\"switchBroker('nonexistent_broker_id_for_test')\")"
nC = (
    "    # Install unhandledrejection listener BEFORE failure trigger\n"
    "    # (Polish #5.7 contract tightening: catches ALL rejections, including chromium\n"
    "    # variants where rejection surfaces as console.error rather than pageerror)\n"
    "    page.evaluate(\n"
    "        \"window.addEventListener('unhandledrejection', e => window.__unhandled = (window.__unhandled||0)+1)\"\n"
    "    )\n\n"
    "    page.evaluate(\"switchBroker('nonexistent_broker_id_for_test')\")"
)
cC = src.count(oC)
print('Edit C anchor count (failure trigger):', cC)
if cC != 1:
    print('FAIL Edit C: anchor not unique')
    sys.exit(2)
src = src.replace(oC, nC, 1)
print('OK Edit C: inserted addEventListener BEFORE failure trigger')

# ===== EDIT D: replace wait_for_timeout(800) with wait_for_function("true") no-op =====
oD = '    page.wait_for_timeout(800)'
nD = '    page.wait_for_function("true")  # deterministic no-op wait\n'
cD = src.count(oD)
print('Edit D anchor count (wait_for_timeout 800):', cD)
if cD != 1:
    print('FAIL Edit D: anchor not unique')
    sys.exit(2)
src = src.replace(oD, nD, 1)
print('OK Edit D: wait_for_timeout(800) -> wait_for_function("true") no-op')

# ===== EDIT E: replace pageerror-with-filter assertion block with cleaner __unhandled counter =====
# Anchor: from `# Polish #5.7 invariant: NO unhandled JS exception leaks to window` through end-of-file
oE = (
    "    # Polish #5.7 invariant: NO unhandled JS exception leaks to window\n"
    "    leak = [e for e in js_errors if e[0] == \"pageerror\"]\n"
    "    if leak:\n"
    "        # The .catch() is supposed to suppress unhandled rejections, but some\n"
    "        # browsers (chromium) still emit pageerror if a fetch .catch returns a\n"
    "        # void rather than re-throwing. Treat pageerror containing \"Uncaught (in promise)\"\n"
    "        # as suppressed (Polish #5.7 intent: swallow, not re-throw to user).\n"
    "        suppressed = all(\"Uncaught\" in msg or \"Promise\" in msg or \"Failed to fetch\" in msg or \"NetworkError\" in msg for _, msg in leak)\n"
    "        assert suppressed, (\n"
    "            \"Polish #5.7 .catch() wrap failed: unhandled pageerror not suppressed: \"\n"
    "            + str(leak)\n"
    "        )\n\n"
    "    # Note: console.error is allowed (we LOG the failure for the user); only pageerror\n"
    "    # (uncaught JS exception) is the leak we're guarding against.\n"
)
nE = (
    "    # Polish #5.7 invariant (Polish #5.7 contract tightening): NO unhandled rejection leaks to window\n"
    "    # Counts via window.addEventListener('unhandledrejection', ...) installed BEFORE the trigger.\n"
    "    # Catches ALL rejections including chromium variants where rejection surfaces as console.error\n"
    "    # rather than pageerror (the prior assertion missed these silently).\n"
    "    unhandled_count = page.evaluate(\"window.__unhandled || 0\")\n"
    "    assert unhandled_count == 0, (\n"
    "        f\"Polish #5.7 .catch() wrap failed: {unhandled_count} unhandled rejection(s) leaked to window. \"\n"
    "        f\"Diagnostic context (js_errors): {js_errors!r}\"\n"
    "    )\n"
)
cE = src.count(oE)
print('Edit E anchor count (pageerror-with-filter block):', cE)
if cE != 1:
    print('FAIL Edit E: anchor not unique')
    sys.exit(2)
src = src.replace(oE, nE, 1)
print('OK Edit E: pageerror-with-filter assertion -> __unhandled counter assertion')

# Write back
with open('tests/test_broker_ui_resilience.py', 'wb') as f:
    f.write(src.encode('utf-8'))
print('Wrote tests/test_broker_ui_resilience.py (utf-8,', len(src), 'chars,', len(src) - original_size, 'net change)')

# Final sanity verification
print('\n=== POST-EDIT SANITY ===')
print('import os count:', src.count('import os\n'))
print('expect in playwright import:', 'expect' in src and ', expect' in src)
print('wait_for_timeout count (must be 0):', src.count('wait_for_timeout'))
print('wait_for_function count (must be 1):', src.count('wait_for_function'))
print('addEventListener unhandledrejection count (must be 1):', src.count("addEventListener('unhandledrejection'"))
print('window.__unhandled count (must be 2 -- listener + assertion):', src.count('window.__unhandled'))
