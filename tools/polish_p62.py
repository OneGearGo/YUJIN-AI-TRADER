#!/usr/bin/env python3
# Polish #6.2 applier: lock-in exact KPI label counts for fallback regressions.
# Replace `src.count(...) >= 2` with `src.count(...) == 2` on L69 of
# tests/test_routes_broker.py. Tight anchor + 1-substitution invariant.
"""Apply Polish #6.2 test(routes) edit on /Desktop staging mirror."""
import re
import sys

STAGING = r"C:\Users\Administrator\Desktop\_patch_test_routes_broker_p62"

with open(STAGING, "rb") as f:
    raw = f.read()
src = raw.replace(b"\r\n", b"\n").replace(b"\r", b"\n").decode("utf-8")

# Tight Python anchor: lock to the exact context of the L69 assertion
# (replaces the post-dialog KPI label fallback count check).
# Pattern matches: assert src.count("KPI_LABEL[k]?.../emdash-fallback...") >= 2
# with a flexible inner argument via non-greedy capture (the specific substring
# is unique; sibling `src.count(...)` calls were scanned in the verify step).
old_pat = re.compile(
    r'(assert\s+src\.count\([^)]+\))\s*>=\s*2\s*$',
    flags=re.MULTILINE,
)
new_repl = r'\1 == 2'

new_src, count = old_pat.subn(new_repl, src)

if count == 0:
    print("ERROR: anchor pattern not matched; abort", file=sys.stderr)
    for ln in src.split("\n"):
        if "src.count" in ln:
            print(f"  similar: {ln!r}", file=sys.stderr)
    sys.exit(1)

if count != 1:
    print(f"ERROR: expected 1 match, got {count} (over-match risk)", file=sys.stderr)
    sys.exit(1)

# Verify invariants post-edit
assert ">=" not in new_src.split('src.count')[1].split("\n")[0] if "src.count" in new_src else True  # noqa: E501
# Re-affirm in a stronger way: scan lines containing src.count
remaining_ge_lines = [
    ln for ln in new_src.split("\n")
    if "src.count" in ln and ">=" in ln
]
if remaining_ge_lines:
    print(f"ERROR: leftover >= in src.count lines: {remaining_ge_lines}", file=sys.stderr)
    sys.exit(1)

# Confirm +1/-1 character diff budget
src_lines = src.split("\n")
new_lines = new_src.split("\n")
if len(src_lines) != len(new_lines):
    print(
        f"ERROR: line count drifted ({len(src_lines)} -> {len(new_lines)}); +1/-1 expected",
        file=sys.stderr,
    )
    sys.exit(1)

assert "== 2" in new_src, "ERROR: == 2 not present"
assert "_apply_p62" not in new_src, "ERROR: stray marker injected"

with open(STAGING, "wb") as f:
    f.write(new_src.encode("utf-8"))

print(f"OK: Polish #6.2 edit applied (count={count})")
print(f"OK: line count preserved (no-drift invariant): {len(src_lines)} == {len(new_lines)}")
print(f"OK: '== 2' assertion present in file")
