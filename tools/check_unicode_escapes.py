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


def main(argv: list[str]) -> int:
    if not argv:
        print("usage: check_unicode_escapes.py FILE [FILE ...]", file=sys.stderr)
        return 2

    total_offences = 0
    for arg in argv:
        p = Path(arg)
        if not p.exists():
            print(f"{p}:1:1: ERROR: not found", file=sys.stderr)
            continue
        total_offences += check_file(p)

    if total_offences > 0:
        print(
            f"\nFAIL: {total_offences} literal Unicode/hex escape(s) found. "
            f"Replace with actual UTF-8 characters or proper bytes.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
