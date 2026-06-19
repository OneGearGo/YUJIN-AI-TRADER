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


def test_tstring_passes_validation(tmp_path, capsys):
    """Polish #2 LANDED (Polish #7.3 follows): t-TDQ (Triple-Double-Quote)
    and t-TSQ (Triple-Single-Quote) prefixes are now in _DOCSTRING_PREFIXES
    (PEP 750; Py3.14+). T-strings are treated like other template-string
    prefixes (skipped) and the lint exits 0 even when the t-string content
    contains a backslash-u escape. This test pins the GREEN state so future
    regressions (e.g. accidental removal of the t-prefix entries from
    _DOCSTRING_PREFIXES) are detected immediately.

    The fixture uses t-TDQ specifically (triple-double-quote) so the new
    exemption applies cleanly. Polish #7.4 (deferred) will add C-block
    parameterized coverage for the t-TSQ sibling form.
    """
    fixture = (
        b'#!/usr/bin/env python3\n'
        b'"""docstring."""\n'
        b'x = t"""this is a t-string with ' + ESC_U_EM + b' inside"""\n'
    )
    f = tmp_path / "tstr.py"
    f.write_bytes(fixture)
    r = subprocess.run(
        [PYTHON, str(LINT_SCRIPT), str(f)],
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0, (
        "Polish #7.2 regression: t-TDQ / t-TSQ prefixes not in "
        "_DOCSTRING_PREFIXES. The fixture (t-TDQ with backslash-u inside) "
        "should pass cleanly (exit 0); a non-zero exit means the PEP 750 "
        "t-prefix was accidentally removed from the allowlist."
        f"\n  stdout: {r.stdout!r}\n  stderr: {r.stderr!r}"
    )


@pytest.mark.parametrize(
    "prefix_marker, opener, closer, content_label, content_bytes",
    [
        ("t-TDQ-with",   b't"""', b'"""', "with_u2014", b"text " + ESC_U_EM + b" middle"),
        ("t-TSQ-with",   b"t'''", b"'''", "with_u2014", b"text " + ESC_U_EM + b" middle"),
        ("t-TDQ-clean",  b't"""', b'"""', "clean",       b"plain t-string content"),
        ("t-TSQ-clean",  b"t'''", b"'''", "clean",       b"plain t-string content"),
    ],
    ids=["t-TDQ-with_u2014", "t-TSQ-with_u2014", "t-TDQ-clean", "t-TSQ-clean"],
)
def test_c_t_prefix_exempts_escape(
    tmp_path, capsys, prefix_marker, opener, closer, content_label, content_bytes
):
    """Polish #7.4 (C-block): PEP 750 t-prefix exemptions for t-strings.

    Parameterized to PIN BOTH t-TDQ AND t-TSQ entries of _DOCSTRING_PREFIXES
    (Polish #7.2 atomically added both; Polish #7.3 B-block only pinned t-TDQ).
    Closes the code-reviewer 🟡-MEDIUM gap flagged after the Polish #7.2/#7.3
    ship: accidental removal of EITHER t-TDQ OR t-TSQ from the tuple would now
    be detected by 2 of the 4 C-block sub-cases + the B-block meta-test.

    Each sub-case asserts rc=0 (the lint exits cleanly because the t-prefix
    in _DOCSTRING_PREFIXES exempts triple-quoted t-strings from the corpus
    scan, regardless of whether the t-string content contains a backslash-u
    escape or not).

    Polish-trail convention: this is item **#7.4** in the Polish #7.x ladder.
    HANDOFF.md untouched mid-ladder; pieces count + regex invariant remain
    untouched at 6 PIECES / 8 COMMITS until Polish #7.10 close-out.
    """
    fixture = (
        b'#!/usr/bin/env python3\n'
        b'"""docstring."""\n'
        b"x = " + opener + content_bytes + closer + b"\n"
    )
    f = tmp_path / (prefix_marker + "_" + content_label + ".py")
    f.write_bytes(fixture)
    r = subprocess.run(
        [PYTHON, str(LINT_SCRIPT), str(f)],
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0, (
        f"Polish #7.4 C-block regression ({prefix_marker}, {content_label}): "
        f"t-prefix {_DOCSTRING_PREFIXES_repr()} exemption broken. The fixture "
        f"(defined with opener={opener!r}, content={content_label}) should pass "
        f"cleanly (exit 0); a non-zero exit means the PEP 750 t-prefix was "
        f"accidentally removed from the _DOCSTRING_PREFIXES allowlist."
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


_DRIFT_FIXTURES = [
    (
        "drift_match_4_pieces",
        (
            "# HANDOFF doc\n"
            "\n"
            "## Meta\n"
            "\n"
            "## [closed] Phase 8 v8 polish 阶段\n"
            "1. piece one\n"
            "2. piece two\n"
            "3. piece three\n"
            "4. piece four\n"
            "\n"
            "**pieces count**: 4 PIECES\n"
        ),
        0,
        "drift-clean",
    ),
    (
        "drift_mismatch_3_stat_4_bullets",
        (
            "# HANDOFF doc\n"
            "\n"
            "## [closed] Phase 8 v8 polish 阶段\n"
            "1. piece one\n"
            "2. piece two\n"
            "3. piece three\n"
            "4. piece four\n"
            "\n"
            "**pieces count**: 3 PIECES\n"
        ),
        1,
        "DRIFT",
    ),
    (
        "drift_missing_stat_line",
        (
            "# HANDOFF doc\n"
            "\n"
            "## [closed] Phase 8 v8 polish 阶段\n"
            "1. piece one\n"
            "2. piece two\n"
            "\n"
        ),
        2,
        "ERROR",
    ),
    (
        "drift_missing_closed_section",
        (
            "# HANDOFF doc\n"
            "\n"
            "## Some other section\n"
            "\n"
            "**pieces count**: 2 PIECES\n"
        ),
        2,
        "ERROR",
    ),
    (
        "drift_match_indented_4_bullets",
        (
            "# HANDOFF doc\n"
            "\n"
            "## [closed] Phase 8 v8 polish 阶段\n"
            "   1. piece one\n"
            "   2. piece two\n"
            "   3. piece three\n"
            "   4. piece four\n"
            "\n"
            "**pieces count**: 4 PIECES\n"
        ),
        0,
        "drift-clean",
    ),
    (
        "drift_match_column_zero_4_bullets",
        (
            "# HANDOFF doc\n"
            "\n"
            "## [closed] Phase 8 v8 polish 阶段\n"
            "1. piece one\n"
            "2. piece two\n"
            "3. piece three\n"
            "4. piece four\n"
            "\n"
            "**pieces count**: 4 PIECES\n"
        ),
        0,
        "drift-clean",
    ),
    (
        "drift_match_nested_5_bullets",
        (
            "# HANDOFF doc\n"
            "\n"
            "## [closed] Phase 8 v8 polish 阶段\n"
            "1. piece one\n"
            "2. piece two\n"
            "3. piece three\n"
            "4. piece four\n"
            "   1.1. nested sub-piece\n"
            "\n"
            "**pieces count**: 5 PIECES\n"
        ),
        0,
        "drift-clean",
    ),
]


@pytest.mark.parametrize(
    "scenario_id,fixture_text,expected_rc,expected_marker",
    _DRIFT_FIXTURES,
    ids=[row[0] for row in _DRIFT_FIXTURES],
)
def test_polish_trail_drift_detection(
    tmp_path,
    scenario_id,
    fixture_text,
    expected_rc,
    expected_marker,
):
    """Polish-trail drift hook (--check-handoff): synthesize 4 HANDOFF.md fixtures
    covering (a) drift-clean, (b) drift detected, (c) missing stat line,
    (d) missing [closed] H2 section. Verify rc 0/1/2 and that stderr carries
    the matching diagnostic marker."""
    handoff_path = tmp_path / "HANDOFF.md"
    handoff_path.write_text(fixture_text, encoding="utf-8")
    r = subprocess.run(
        [PYTHON, str(LINT_SCRIPT), "--check-handoff", str(handoff_path)],
        capture_output=True,
        text=True,
    )
    combined = (r.stdout or "") + "\n" + (r.stderr or "")
    assert r.returncode == expected_rc, (
        f"{scenario_id}: expected exit {expected_rc}, got {r.returncode}\n"
        f"  stdout: {r.stdout!r}\n  stderr: {r.stderr!r}"
    )
    assert expected_marker in combined, (
        f"{scenario_id}: expected output to contain {expected_marker!r}\n"
        f"  combined: {combined!r}"
    )
