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
    # DOCS-MIRROR (do not land without coordinating HANDOFF.md + meta-test): the
    # t""" / t''' PEP 750 prefix is intentionally NOT in this allowlist because the
    # toolchain here runs Python 3.11 — adding it now would defeat meta-test B.t
    # which asserts t-string-shaped literal source gets flagged. The trigger steps
    # live in HANDOFF.md (repo root, anchor ## [deferred] Polish #2 —
    # TODO(Py3.14) trigger steps at line L241; once-landed commit 1f8aff3), and the
    # mirror regression guard on the OTHER side is meta-test B.t in
    # tools/test_check_unicode_escapes.py. If/when Py3.14 is adopted, land all 4
    # trigger steps atomically and verify meta-test stays 16/16 (with B.t now
    # expecting rc=0 instead of rc=1; B.t is one parameterized row, not a 17th case).
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

    for tok in tokens:
        if tok.type == tokenize.COMMENT:
            continue
        if tok.type != tokenize.STRING:
            continue
        if _is_docstring_start(tok.string):
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
    """Polish-trail drift detection: assert pieces-count stat equals section bullet count.

    Reads HANDOFF.md and verifies:
      - The `## [closed] Phase 8 v8 polish 阶段` H2 section exists and has
        numbered bullets (1./2./3./...) under it.
      - The `**pieces count**: N PIECES` stat line is present in HANDOFF.md
        (anywhere; not section-scoped to be tolerant of formatting drift).
      - The integer N matches the count of numbered bullets in the section.

    Returns:
      0 if N matches bullet count (drift-clean).
      1 if N mismatches (drift detected; commit blocked).
      2 if HANDOFF.md is missing, unreadable, or lacks required structural
        elements (config error; operator should investigate).
    """
    try:
        text = handoff_path.read_text(encoding="utf-8")
    except OSError as e:
        print(
            f"{handoff_path}:1:1: ERROR: cannot read: {e}",
            file=sys.stderr,
        )
        return 2

    section_match = re.search(
        r"^## \[closed\] Phase 8 v8 polish 阶段.*?(?=^## |\Z)",
        text,
        re.MULTILINE | re.DOTALL,
    )
    if not section_match:
        print(
            f"{handoff_path}:1:1: ERROR: ## [closed] Phase 8 v8 polish section not found",
            file=sys.stderr,
        )
        return 2
    section = section_match.group(0)

    # Bullet regex uses an explicit [ \t]* char class instead of [[:space:]]
    # (POSIX class) because Python 3.11's re module emits FutureWarning on
    # [[:space:]] AND silently returns 0 matches (nested-set detection). The
    # explicit class preserves the semantic intent (zero-or-more space/tab
    # before the [1-9]. marker) and matches both column-zero and indented
    # bullets in the [closed] section while remaining Python-version-portable.
    bullets = re.findall(r"^(?:[ \t]*)([1-9])\.", section, re.MULTILINE)
    bullet_count = len(bullets)

    stat_match = re.search(r"\*\*pieces count\*\*:\s*(\d+)", text)
    if not stat_match:
        print(
            f"{handoff_path}:1:1: ERROR: **pieces count**: N stat line not found",
            file=sys.stderr,
        )
        return 2
    stat_count = int(stat_match.group(1))

    if bullet_count != stat_count:
        print(
            f"{handoff_path}:1:1: DRIFT: pieces count stat says {stat_count} PIECES "
            f"but [closed] section has {bullet_count} numbered bullets. "
            f"Sync both before commit.",
            file=sys.stderr,
        )
        return 1
    print(
        f"OK: HANDOFF drift-clean - {stat_count} PIECES stat matches "
        f"{bullet_count} bullets in [closed] section.",
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
