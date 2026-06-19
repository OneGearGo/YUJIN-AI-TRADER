"""Self-test for tools/check_unicode_escapes.py - Polish #1 (CRITICAL FUTURE WORK).

The lint prevents the 25-iteration corruption cycle that hit
tests/test_visual_regression_baseline.py. Without this self-test,
silent lint regressions (regex tweak, docstring-prefix misconfig, etc.)
would let the corruption cycle return UNDETECTED.

KEY DESIGN CONSTRAINT
---------------------
This file MUST NOT contain backslash-u escape patterns ANYWHERE in
source - not in docstrings, descriptions, comments, or fixtures -
because Python interprets them in string literals and would either
SyntaxError the import or semantically corrupt the byte sequence.

Strategy: the special chars the lint flags (backslash-u + 4 hex,
backslash-x + 2 hex, etc.) are constructed at runtime via
bytes((int_tuples)) tuple literals. The META-TEST SOURCE FILE has
zero backslash-u patterns anywhere; the FIXTURE FILES written to
tmp_path at test time contain the actual 6 ASCII bytes (bksl-u-XXXX)
that the lint then correctly flags on.

Test matrix (15 tests total):
  A.1   clean ASCII only
  A.2   bad backslash-u escape in single-line STRING
  A.3   bad backslash-x byte escape in single-line STRING
  A.4   triple-quoted docstring with backslash-u prose (EXCLUDED)
  A.5   comment with backslash-u prose (EXCLUDED)
  A.6   CRLF line endings + bad STRING (still flagged)
  A.7   single-line r-prefix string with escape (NOT skipped)
  A.8   b-prefix byte literal with escape (flagged: corruption signal)
  A.9   f-string with escape (NOT skipped: not triple-quoted)
  A.10  multi-line triple-quoted STRING with escape (EXCLUDED)
  A.11  multiple matches in ONE STRING token = 1 WARNING (per-token)
  A.12  octal and named escapes (NOT matched: regex scope)
  A.13  var-assigned triple-quote (over-skip; documented limitation)

Known-limitation tests (Polish #2 + #3 tickets):
  B.t  t-string prefix (PEP 750) currently flagged; update when Polish #2 lands
  B.m  missing argv file currently exits 0 silently; update when Polish #3 lands
"""
import subprocess
import sys
from pathlib import Path

import pytest

LINT_SCRIPT = Path(__file__).resolve().parent / "check_unicode_escapes.py"
PYTHON = sys.executable


# Lint-safe byte sequences (zero backslash-u substrings in source).
# Constructed at runtime via tuple-of-bytes; the meta-test source file
# thus has no patterns that the lint could match against itself.
ESC_U_EM  = bytes((0x5c, 0x75, 0x32, 0x30, 0x31, 0x34))  # bksl u 2 0 1 4 (em-dash escape)
ESC_X_B1  = bytes((0x5c, 0x78, 0x62, 0x31))              # bksl x b 1 (Latin-1 byte)
ESC_O_077 = bytes((0x5c, 0x30, 0x37, 0x37))              # bksl 0 7 7 (octal - lint does not match)
ESC_N_OPEN = bytes((0x5c, 0x6e))                         # bksl n (start of named escape - lint does not match)


# Test matrix: 13 scenarios A.1-A.13.
MATRIX = [
    (
        "A.1_clean_ascii",
        "ASCII-only module passes lint (no escapes anywhere)",
        b'#!/usr/bin/env python3\n'
        b'"""Module docstring, ASCII-only."""\n'
        b'x = "hello, world!"\n',
        0, 0, None,
    ),
    (
        "A.2_bad_u_in_string",
        "literal backslash-u escape in single-line STRING is flagged",
        b'#!/usr/bin/env python3\n'
        b'"""docstring."""\n'
        b'x = "this string contains a literal ' + ESC_U_EM + b' escape"\n',
        1, 1, None,
    ),
    (
        "A.3_bad_x_in_string",
        "literal backslash-x byte escape in single-line STRING is flagged",
        b'#!/usr/bin/env python3\n'
        b'"""docstring."""\n'
        b'x = "byte escape ' + ESC_X_B1 + b' in source"\n',
        1, 1, None,
    ),
    (
        "A.4_docstring_escape",
        "triple-quoted docstring with escape prose is excluded",
        b'#!/usr/bin/env python3\n'
        b'"""\n'
        b'Documentation mentioning ' + ESC_U_EM + b' as ASCII prose is not flagged.\n'
        b'"""\n',
        0, 0, None,
    ),
    (
        "A.5_comment_escape",
        "comment with backslash-u escape prose is excluded",
        b'#!/usr/bin/env python3\n'
        b'"""docstring."""\n'
        b'# comment about ' + ESC_U_EM + b' corruption pattern - fine.\n',
        0, 0, None,
    ),
    (
        "A.6_crlf_bad_string",
        "CRLF line endings + bad STRING is still flagged",
        b'#!/usr/bin/env python3\r\n'
        b'"""docstring."""\r\n'
        b'x = "bad ' + ESC_U_EM + b' escape"\r\n',
        1, 1, None,
    ),
    (
        "A.7_raw_string_escape",
        "single-line r-prefix string with escape is NOT skipped",
        b'#!/usr/bin/env python3\n'
        b'"""docstring."""\n'
        b"x = r'literal " + ESC_U_EM + b" in raw single-line string'\n",
        1, 1, None,
    ),
    (
        "A.8_byte_literal_escape",
        "b-prefix byte literal with escape is flagged (corruption signal)",
        b'#!/usr/bin/env python3\n'
        b'"""docstring."""\n'
        b"x = b'" + ESC_U_EM + b"'\n",
        1, 1, None,
    ),
    (
        "A.9_fstring_escape",
        "f-string with escape is NOT skipped (not triple-quoted)",
        b'#!/usr/bin/env python3\n'
        b'"""docstring."""\n'
        b'name = "alice"\n'
        b"x = f'hello {name}, escape " + ESC_U_EM + b" here'\n",
        1, 1, None,
    ),
    (
        "A.10_triple_string_escape",
        "multi-line triple-quoted STRING with escape is excluded",
        b'#!/usr/bin/env python3\n'
        b'"""docstring."""\n'
        b'"""\n'
        b'Triple-quote expression with ' + ESC_U_EM + b' as text - excluded.\n'
        b'"""\n',
        0, 0, None,
    ),
    (
        "A.11_multi_match_one_token",
        "multiple matches in ONE STRING token equals exactly 1 WARNING",
        b'#!/usr/bin/env python3\n'
        b'"""docstring."""\n'
        b'x = "first ' + ESC_U_EM + b' and second ' + ESC_U_EM + b'"\n',
        1, 1, "lint counts per-token, not per-match (uses matched[0] only)",
    ),
    (
        "A.12_octal_named_not_matched",
        "octal and named escapes are NOT matched by the lint regex",
        b'#!/usr/bin/env python3\n'
        b'"""docstring."""\n'
        b'x = "octal ' + ESC_O_077 + b' and named ' + ESC_N_OPEN + b'amed{EM DASH}"\n',
        0, 0, "regex scope is unicode-escape OR hex-escape only",
    ),
    (
        "A.13_var_assigned_triple_quote",
        "var-assigned triple-quote is ALSO excluded (over-skip; minor)",
        b'#!/usr/bin/env python3\n'
        b'"""docstring."""\n'
        b'x = """expr with ' + ESC_U_EM + b' in triple-quote form"""\n',
        0, 0, "tokenize inspects source form only; position-blind exemption",
    ),
]


@pytest.mark.parametrize(
    "scenario_id,description,fixture_bytes,expected_exit,expected_warnings,note",
    MATRIX,
    ids=[row[0] for row in MATRIX],
)
def test_lint_matrix(
    tmp_path,
    capsys,
    scenario_id,
    description,
    fixture_bytes,
    expected_exit,
    expected_warnings,
    note,
):
    """Run the lint on a synthetic fixture and verify exit code + WARNING count."""
    f = tmp_path / f"{scenario_id}.py"
    f.write_bytes(fixture_bytes)
    r = subprocess.run(
        [PYTHON, str(LINT_SCRIPT), str(f)],
        capture_output=True,
        text=True,
    )
    out = (r.stdout or "") + "\n" + (r.stderr or "")
    warning_count = out.count("WARNING")
    assert r.returncode == expected_exit, (
        f"{scenario_id}: expected exit {expected_exit}, got {r.returncode}\n"
        f"  stdout: {r.stdout!r}\n  stderr: {r.stderr!r}"
    )
    assert warning_count == expected_warnings, (
        f"{scenario_id}: expected {expected_warnings} WARNING(s), got {warning_count}\n"
        f"  stdout: {r.stdout!r}\n  stderr: {r.stderr!r}"
    )
    if note:
        print(f"NOTE ({scenario_id}): {note}")


def test_tstring_currently_flagged(tmp_path, capsys):
    """KNOWN LIMITATION (Polish #2 ticket): t-string prefix is currently flagged
    by the lint. After the ticket lands, t-prefix should be treated like other
    template-string prefixes (skipped). Update this test to expect exit 0."""
    fixture = (
        b'#!/usr/bin/env python3\n'
        b'"""docstring."""\n'
        b"x = t'this is a t-string with " + ESC_U_EM + b" inside'\n"
    )
    f = tmp_path / "tstr.py"
    f.write_bytes(fixture)
    r = subprocess.run(
        [PYTHON, str(LINT_SCRIPT), str(f)],
        capture_output=True,
        text=True,
    )
    assert r.returncode == 1, (
        "t-string currently expected to be flagged (exit 1). If this returns 0, "
        "Polish #2 has likely landed. Update this test to expect exit 0."
        f"\n  stdout: {r.stdout!r}\n  stderr: {r.stderr!r}"
    )


def test_mixed_missing_plus_offence_keeps_both_errors(tmp_path):
    """Polish #3 visibility contract: a run with BOTH a missing argv AND an offence-
    yielding valid file must report BOTH errors on stderr (not silently suppress the
    FAIL summary). rc=2 (Polish #3 hard-fail) wins over offences (rc=1).

    Regression guard: this pins the post-commit-425d0f2 followup that swaps the
    print order so the offender summary is not swallowed by the rc=2 short-circuit.
    """
    # Build a fixture .py whose SOURCE contains an 8-byte em-dash escape (the 6
    # chars backslash-u-2-0-1-4 inside single quotes) — the lint's tokenize+
    # BAD_PATTERN catches this. Construct fixture bytes at runtime so this test's
    # OWN source code does not get lint-self-flagged.
    EM_DASH_ESC_BYTES = bytes([0x5C, 0x75, 0x32, 0x30, 0x31, 0x34])  # 6 source chars
    SOURCE_BYTES = b"x = 'hi " + EM_DASH_ESC_BYTES + b" there'\n"
    good = tmp_path / "good_with_offence.py"
    good.write_bytes(SOURCE_BYTES)
    missing = tmp_path / "does-not-exist.py"

    r = subprocess.run(
        [PYTHON, str(LINT_SCRIPT), str(good), str(missing)],
        capture_output=True,
        text=True,
    )
    assert r.returncode == 2, (
        "Polish #3 mixed case: missing argv must still hard-fail rc=2 when other "
        "argv files contain offences, AND rc must NOT be 1 (that would conflate "
        "missing-argv with offences)."
        f"\n  stdout: {r.stdout!r}\n  stderr: {r.stderr!r}"
    )
    err = r.stderr or ""
    assert "ERROR" in err and "not found" in err, (
        "Polish #3 mixed case: stderr must identify the missing argv path with "
        f"ERROR ... not found.\n  stderr: {err!r}"
    )
    assert "FAIL" in err and "literal Unicode/hex escape" in err, (
        "Polish #3 visibility: stderr must STILL print the aggregated FAIL summary "
        "even when rc=2 is on. If missing, the visibility contract regressed."
        f"\n  stderr: {err!r}"
    )


def test_missing_argv_hardfails(tmp_path, capsys):
    """Polish #3 LANDED: a missing argv file MUST hard-fail with rc=2 (HARD-FAIL),
    distinct from clean rc=0 and offences rc=1. Note the lint also continues scanning
    subsequent argv entries (Polish #3 accumulator pattern), so stderr still names
    the missing file even when more argv follow."""
    nonexistent = tmp_path / "does-not-exist.py"
    r = subprocess.run(
        [PYTHON, str(LINT_SCRIPT), str(nonexistent)],
        capture_output=True,
        text=True,
    )
    assert r.returncode == 2, (
        "Polish #3: missing argv must return rc=2. If rc=0 the hard-fail regressed; "
        "if rc=1 the loop is conflating missing-argv with offences. Both are bugs."
        f"\n  stdout: {r.stdout!r}\n  stderr: {r.stderr!r}"
    )
    # Lint must also surface the missing file as ERROR on stderr so reporters see
    # which argv was rejected (Polish #3: stderr ERROR persists across the
    # accumulator continue pattern).
    assert "ERROR" in (r.stderr or "") or "not found" in (r.stderr or ""), (
        f"expected an ERROR line on stderr acknowledging the missing file, "
        f"got: {r.stderr!r}"
    )
