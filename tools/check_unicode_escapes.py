#!/usr/bin/env python3
'''check_unicode_escapes.py -- Pre-commit / CI lint for tests/*.py.

Fails (exit 1) if literal Unicode escapes (4-hex-digit form) or single-byte
hex escapes (2-hex-digit form) appear inside STRING tokens of any tests/*.py
file. Excludes comments and docstrings.

This is the guardrail against a 12-iteration corruption cycle that hit
tests/test_visual_regression_baseline.py:

  * UTF-8 source files, when edited via str_replace / Python byte-literal
    scripts that contain literal backslash-u escape sequences (e.g.
    u00b7 / u2500 / u2014 / u2194 / u2192 / u00d7 / u2248) as 6-char ASCII
    escapes, get those literals burned into the file as poison expansions
    are interpreted.

  * AST-based linters (e.g. ruff's default rule set) DO NOT catch this
    because Python evaluates the escape during AST parsing. The literal
    backslash-u-zero-zero-b-seven does not appear anywhere in the resolved
    AST.

  * The tokenize module preserves raw source bytes (with escapes intact),
    so a regex over tokenize.STRING output reliably detects the literals.

Scope:
  * Argument list = explicit file paths from pre-commit / CI runner.
  * Pre-commit hook uses files filter to limit scope to regex ^tests/.
  * CI step enumerates tests/*.py via either GNU find (Linux) or
    pathlib.rglob (Windows-portable).

Exit codes:
  * 0 = all scanned files are clean (no literal escapes found).
  * 1 = at least one match was detected; offending locations printed.

False positive prevention:
  * Skips tokenize.COMMENT tokens (text after hash).
  * Skips STRING tokens whose source starts with triple-single-quote /
    triple-double-quote, including r-, R-, b-, B-, f-, F-, rb-, RB-,
    br-, BR-, fr-, FR- variants (any docstring form).

Pattern (regex over raw token STRING value):
  two \\\\ characters followed by either:
    - u and exactly 4 hex digits (4-hex-digit Unicode escapes), OR
    - x and exactly 2 hex digits (2-hex Latin-1 byte escapes;
      required because earlier repair scripts burned bare xB1 Latin-1
      bytes into UTF-8 source).

The audit comment lines above intentionally describe backslash-u escapes
as ASCII prose (e.g. u00b7), not as Python string literals, so this very
script does not flag itself when run locally.
'''

import io
import re
import sys
import tokenize
from pathlib import Path

BAD_PATTERN = re.compile(r"\\u[0-9a-fA-F]{4}|\\x[0-9a-fA-F]{2}")

# Docstring prefix forms that should NOT be flagged even if they contain
# literal backslash-u escapes (the docstring is describing the corruption,
# not actually using it). Matches triple-quoted strings with any of:
#   bare  and  /  and triple-singles, plus r/R/b/B/f/F/rb/RB/br/BR/fr/FR
# prefix on either quote style.
_DOCSTRING_PREFIXES = (
    '"""', "'''",
    'r"""', "r'''", 'R"""', "R'''",
    'b"""', "b'''", 'B"""', "B'''",
    'f"""', "f'''", 'F"""', "F'''",
    'rb"""', "rb'''", 'Rb"""', "Rb'''",
    'rB"""', "rB'''", 'RB"""', "RB'''",
    'br"""', "br'''", 'Br"""', "Br'''",
    'bR"""', "bR'''", 'BR"""', "BR'''",
    'fr"""', "fr'''", 'Fr"""', "Fr'''",
    'fR"""', "fR'''", 'FR"""', "FR'''",
    't"""', "t'''",
    # PEP 750 (Python 3.14+) t-prefix exempts triple-quoted t-strings the same
    # way r-/b-/f-prefix exempt their siblings (Polish #7.2 LANDED).
)


def _is_docstring_start(raw: str) -> bool:
    """True if `raw` (token.string source representation) opens a docstring.

    Detects triple-quoted string sources with any of the standard string
    prefixes (bare, r, R, b, B, f, F, and their combinations) so that
    descriptive docstrings (which may contain backslash-u escapes as
    prose) are not flagged.
    """
    stripped = raw.lstrip()
    return any(stripped.startswith(p) for p in _DOCSTRING_PREFIXES)


def check_file(filepath: Path) -> int:
    """Count offending escape literals in `filepath`.

    Prints each hit as `path:line:col: WARNING: ...` (CI grep-friendly
    format). Reads in bytes mode so tokenize yields the raw source.
    """
    count = 0
    try:
        src_bytes = filepath.read_bytes()
    except OSError as e:
        print(f"{filepath}:1:1: ERROR: cannot read: {e}", file=sys.stderr)
        return 0

    try:
        tokens = list(
            tokenize.tokenize(io.BytesIO(src_bytes).readline)
        )
    except tokenize.TokenError as e:
        print(f"{filepath}:1:1: ERROR: tokenize failed: {e}", file=sys.stderr)
        return 0

    # Python 3.12+ tokenizes f-strings as FSTRING_START/FSTRING_MIDDLE/FSTRING_END
    # instead of STRING. FSTRING_MIDDLE holds the text portions that may contain
    # literal escape sequences. We check both STRING and FSTRING_MIDDLE tokens.
    FSTRING_MIDDLE = getattr(tokenize, 'FSTRING_MIDDLE', None)
    _STRING_TYPES = {tokenize.STRING}
    if FSTRING_MIDDLE is not None:
        _STRING_TYPES.add(FSTRING_MIDDLE)

    for tok in tokens:
        if tok.type == tokenize.COMMENT:
            continue
        if tok.type not in _STRING_TYPES:
            continue
        # Triple-quoted docstrings are exempt (only applies to STRING tokens;
        # FSTRING_MIDDLE tokens are always content portions of f-strings).
        if tok.type == tokenize.STRING and _is_docstring_start(tok.string):
            continue
        if BAD_PATTERN.search(tok.string):
            line, col = tok.start
            matched = BAD_PATTERN.findall(tok.string)
            preview = tok.string.strip()[:80]
            print(
                f"{filepath}:{line}:{col}: WARNING: literal Unicode/hex escape "
                f"{matched[0]!r} in {preview!r} "
                f"(use actual UTF-8 bytes instead)"
            )
            count += 1
    return count


def _check_handoff_drift(handoff_path: Path) -> int:
    r"""Polish-trail drift detection: aggregate-aware across multi-[closed] sections.

    Polish #7.11 (chore(trail) — make `_check_handoff_drift` aggregate-aware
    of multi-[closed] sections) replaces the previous first-section-only
    implementation. The pre-#7.11 hook counted bullets only inside the
    FIRST `## [closed]` H2 section. The post-#7.11 hook splits HANDOFF.md
    at every `## [closed]` marker, counts bullets (^[1-9]\.) inside each
    section's body up to the FIRST `#`-level heading (any depth),
    sums the per-section bullet counts, and compares the SUM against
    the doc-wide `**pieces count**: N PIECES` stat line.

    Reads HANDOFF.md and verifies:
      - The doc-wide `**pieces count**: N PIECES` stat line is present
        in HANDOFF.md (anywhere; not section-scoped to be tolerant of
        formatting drift).
      - The integer N matches the SUM of numbered bullets across ALL
        `## [closed]` H2 sections.

    H3 sub-ladders like `### Polish #7.x ladder` (and any deeper
    sub-ladder inside a [closed] body) are EXCLUDED from the count by
    stopping each section's scope at the FIRST 1-3-`#`-level heading
    (Polish #7.11a regex tightening: `\\n#{1,3}\\s`) inside its body.

    Returns:
      0 if N matches aggregated bullet count (drift-clean).
      1 if N mismatches (drift detected; commit blocked).
      2 if HANDOFF.md is missing, unreadable, lacks the doc-wide
        pieces-count stat line, OR lacks any `## [closed]` H2 sections
        (config error; operator should reconcile Polish #7.11b's missing-
        section rule).
    """
    try:
        text = handoff_path.read_text(encoding="utf-8")
    except OSError as e:
        print(
            f"{handoff_path}:1:1: ERROR: cannot read: {e}",
            file=sys.stderr,
        )
        return 2

    stat_match = re.search(r"\*\*pieces count\*\*:\s*(\d+)", text)
    if not stat_match:
        print(
            f"{handoff_path}:1:1: ERROR: **pieces count**: N stat line not found",
            file=sys.stderr,
        )
        return 2
    stat_count = int(stat_match.group(1))

    # Split HANDOFF.md at every `## [closed]` marker. Skip the preamble
    # (sections[0] is the title + intro before the first [closed] section).
    sections = re.split(r"^## \[closed\]", text, flags=re.MULTILINE)
    total_bullets = 0
    section_count = 0
    for section_text in sections[1:]:
        section_count += 1
        # Restrict each section's scope to the body BEFORE any nested
        # heading (any `#` level). Splits on the FIRST literal "\n#"
        # substring inside the section body. This excludes H3 ladders
        # such as `### Polish #7.x ladder` placed after bullets inside
        # the same [closed] block.
        body = re.split(r"\n#{1,3}\s", section_text)[0]
        # Bullet regex uses an explicit [ \t]* char class instead of
        # [[:space:]] (POSIX class) because Python 3.11's re module
        # emits FutureWarning on [[:space:]] AND silently returns 0
        # matches (nested-set detection). The explicit class preserves
        # the semantic intent (zero-or-more space/tab before the
        # [1-9]. marker).
        bullets = re.findall(r"^(?:[ \t]*)([1-9])\.", body, re.MULTILINE)
        total_bullets += len(bullets)

    # Polish #7.11b v3 (chore(trail) — restore missing-`## [closed]`-section
    # rc=2 config-error path lost in Polish #7.11's aggregate rewrite).
    # When the doc-wide **pieces count** stat line exists in HANDOFF.md but
    # ZERO `## [closed]` H2 sections are present, the document is in
    # inconsistent config state: an operator declared a tally but did not
    # lay out the payload. The pre-#7.11 hook treated this as a config
    # error (rc=2) so the operator's pre-commit / CI step blocks the
    # commit; Polish #7.11's aggregate rewrite lost that path. This guard
    # restores it — operator should reconcile (add a [closed] section or
    # remove the tally).
    if section_count == 0:
        print(
            f"{handoff_path}:1:1: ERROR: doc-wide **pieces count**: N stat "
            f"line found but no `## [closed]` H2 sections present in "
            f"HANDOFF.md (config mismatch; operator should reconcile)",
            file=sys.stderr,
        )
        return 2

    if total_bullets != stat_count:
        if section_count == 1:
            # Backward-compat: pre-#7.11 message format. SCENARIOS fixtures
            # assert against "but [closed] section has {M} numbered bullets."
            print(
                f"{handoff_path}:1:1: DRIFT: pieces count stat says {stat_count} "
                f"PIECES but [closed] section has {total_bullets} "
                f"numbered bullets. Sync both before commit.",
                file=sys.stderr,
            )
        else:
            # Aggregate-aware: Polish #8.x forward compat. Names per-section
            # count and section count for operator clarity.
            print(
                f"{handoff_path}:1:1: DRIFT: pieces count stat says {stat_count} "
                f"PIECES but [closed] sections aggregate to {total_bullets} "
                f"numbered bullets across {section_count} sections. "
                f"Sync both before commit.",
                file=sys.stderr,
            )
        return 1

    if section_count == 1:
        # Backward-compat clean-case: matches legacy
        # "OK: HANDOFF drift-clean - {N} PIECES stat matches {M} numbered bullets.".
        print(
            f"OK: HANDOFF drift-clean - {stat_count} PIECES stat matches "
            f"{total_bullets} numbered bullets.",
            file=sys.stderr,
        )
    else:
        # Aggregate-aware clean-case.
        print(
            f"OK: HANDOFF drift-clean - {stat_count} PIECES stat matches "
            f"{total_bullets} numbered bullets across {section_count} "
            f"[closed] sections.",
            file=sys.stderr,
        )
    return 0


def main(argv: list[str]) -> int:
    if not argv:
        print(
            "usage: check_unicode_escapes.py [--check-handoff HANDOFF.md] [FILE ...]",
            file=sys.stderr,
        )
        return 2
    if argv[0] == "--check-handoff":
        if len(argv) < 2:
            print(
                "ERROR: --check-handoff requires HANDOFF.md path",
                file=sys.stderr,
            )
            return 2
        handoff_path = Path(argv[1])
        if not handoff_path.exists():
            print(
                f"{handoff_path}:1:1: ERROR: not found",
                file=sys.stderr,
            )
            return 2
        return _check_handoff_drift(handoff_path)

    total_offences = 0
    missing_count = 0  # Polish #3: track missing argv WITHOUT aborting iteration
    for arg in argv:
        p = Path(arg)
        if not p.exists():
            print(f"{p}:1:1: ERROR: not found", file=sys.stderr)
            # Continue (Polish #3): missing argv must NOT abort so CI keeps visibility
            # into subsequent offence counts. Final rc=2 still wins over offences rc=1.
            missing_count += 1
            continue
        total_offences += check_file(p)

    # Polish #3 visibility contract: surface the aggregated FAIL summary BEFORE the
    # exit-code decision so callers see offence counts even when argv also had a
    # missing file (otherwise rc=2 short-circuits and the summary is swallowed).
    if total_offences > 0:
        print(
            f"\nFAIL: {total_offences} literal Unicode/hex escape(s) found. "
            f"Replace with actual UTF-8 characters or proper bytes.",
            file=sys.stderr,
        )

    # Polish #3 rc ladder: missing argv (rc=2) > offences (rc=1) > clean (rc=0).
    if missing_count > 0:
        return 2
    if total_offences > 0:
        return 1
    return 0
    # DOCS-MIRROR (do not reorder without updating HANDOFF.md (repo root)): the rc
    # ladder MUST stay as missing=2 > offences=1 > clean=0. Polish #3 visibility
    # hardening (commits 425d0f2 + a303fe7) added the FAIL-summary print BEFORE this
    # block so 1 missing + N offences still surfaces offender counts. The regression
    # guard lives in tools/test_check_unicode_escapes.py::
    # test_mixed_missing_plus_offence_keeps_both_errors. If this ladder ever
    # changes, update HANDOFF.md (repo root, anchor ## [closed] Phase 8 v8 polish
    # 阶段 at line L207; once-landed commit d0eb8f5) -> Polish #3 visibility bullet
    # AND re-run that guard.


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
