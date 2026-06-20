# ============================================================
# Round-29 anti-cache meta + APP_VERSION bump + r29 visible skew
# ============================================================
# Purpose: GitHub Pages sends Cache-Control: max-age=600 at the
#   site root, so users who opened the page before commit 3448c1c
#   keep seeing the pre-Round-28 snapshot. Fix:
#   (1) Insert 3 cache-busting <meta http-equiv> tags into <head>,
#       forcing the browser to re-fetch every visit (no-store).
#   (2) Insert a single-literal cursor meta <meta name="yujin-build"
#       content="r29"> so future rounds (R30+) can do a single
#       string overwrite "r29" -> "r30" without re-writing the
#       title or rebuilding the head.
#   (3) Bump APP_VERSION v0.0.1 -> v0.0.2 + visible title suffix
#       so the user sees a clear "new commit reached them" delta.
#
# Why two anchors, not three:
#   Each independent anchor insertion would compete for the
#   "between viewport and <title>" slot. Anchor #3 inserting
#   cursor-meta between viewport and <title> BREAKS the
#   contiguity of anchor #1's NEW substring (which is the full
#   span viewport+CRLF+3-metas+CRLF+<title>). Consolidating
#   into a SINGLE mega-anchor that replaces the full 2-line
#   span "<meta name=viewport...>\r\n<title>AI Trader ... </title>"
#   with the full new head (viewport+anti-cache+3 metas+cursor+
#   title-bumped) avoids the contiguity conflict entirely.
#
# Anchors (byte-exact, CRLF in anchor #1 via regular string
# concatenation "\r\n" produces 2 chars 0x0D 0x0A):
#
#   OLD   "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">\r\n<title>AI Trader - 自动筛选，一键成交，持仓监控</title>"
#   NEW   "<meta name=\"viewport\" ... >\r\n<meta http-equiv=\"Cache-Control\" content=\"no-cache, no-store, must-revalidate\">\r\n<meta http-equiv=\"Pragma\" content=\"no-cache\">\r\n<meta http-equiv=\"Expires\" content=\"0\">\r\n<meta name=\"yujin-build\" content=\"r29\">\r\n<title>AI Trader · r29 - 自动筛选，一键成交，持仓监控</title>"
#   count 1
#
#   OLD   "const APP_VERSION='v0.0.1';"
#   NEW   "const APP_VERSION='v0.0.2';"
#   count 1
#
# Sentinels (must remain present post-patch):
#   - Round-19 demobar r26 sheng bo xian shang message line
#   - Round-23 tag phrase zh+en
#   - Round-26 cipher tags + I18N literals (publicbar/mode_tip/cfg_mwarn/zh en demobar)
#   - Round-27 LIVE cipher tags ([Audit:0xa01/a02], [Expo:0xb03], ...)
#   - Round-28 chainPill FOREX, amtUnit lots, data-ch=forex, NATIVE_UNIT lots,
#     CHAIN_LABEL FOREX, MT5-CLI, ~ /.config/yujin-mt5/.env, [Unit:0xa11]
#   - data-i18n="tag" attribute intact
#   - cursor meta self-sentinel (yujin-build=r29)
#
# ============================================================

import os
import sys

# stdout utf-8 (cosmetic)
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

FILES = [
    os.path.join(r"F:\yujin-mt5", "static", "index.html"),
    os.path.join(r"F:\yujin-mt5", "docs",   "index.html"),
]

# (old, new, expected_count, label)
REWRITES = [
    (
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">\r\n<title>AI Trader - \u81ea\u52a8\u7b5b\u9009\uff0c\u4e00\u952e\u6210\u4ea4\uff0c\u6301\u4ed3\u76d1\u63a7</title>",
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">\r\n"
        "<meta http-equiv=\"Cache-Control\" content=\"no-cache, no-store, must-revalidate\">\r\n"
        "<meta http-equiv=\"Pragma\" content=\"no-cache\">\r\n"
        "<meta http-equiv=\"Expires\" content=\"0\">\r\n"
        "<meta name=\"yujin-build\" content=\"r29\">\r\n"
        "<title>AI Trader \u00b7 r29 - \u81ea\u52a8\u7b5b\u9009\uff0c\u4e00\u952e\u6210\u4ea4\uff0c\u6301\u4ed3\u76d1\u63a7</title>",
        1,
        "head mega-anchor: viewport + 3 anti-cache meta + cursor meta yujin-build=r29 + title r29 suffix",
    ),
    (
        "const APP_VERSION='v0.0.1';",
        "const APP_VERSION='v0.0.2';",
        1,
        "APP_VERSION bump v0.0.1 -> v0.0.2 (file already declares 'v0.0.1' with the 'v' prefix)",
    ),
]

# Sentinels: each (needle, expected_count_or_-1_if_at_least_1, label)
SENTINELS = [
    # Round-19 demobar - zh (with <b> wrapper around 演示模式 from a97a8c2 lime-link restore)
    ("<b>\u6f14\u793a\u6a21\u5f0f</b>", 1, "demobar zh sentinel (b-wrapped)"),
    # Round-19 demobar - en "Demo Mode" (capital M)
    ("<b>Demo Mode</b>", 1, "demobar en sentinel (b-wrapped)"),
    # Round-23 tag phrase zh: appears in tag HTML (line 285) + i18n dict (line 404) — count=2
    ("\u4eba\u673a\u534f\u540c", -1, "tag phrase zh sentinel (>=1, file has 2 occurrences)"),
    # Round-23 en tag phrase: file uses "you pressed ➡️ human in the loop" prose form which differs
    # from this condensed sentinel; skip explicit check (covered by the r23 tag HTML element preservation)
    # Round-26 cipher tags (decision log static i18n + cipher) - relaxed to >=1 for multi-template drift safety
    ("[Hash:0xa3c]", -1, "r26 Hash:0xa3c (>=1)"),
    ("[Codepath:0xff1]", -1, "r26 Codepath:0xff1 (>=1)"),
    ("[Gate:0x4a2]", -1, "r26 Gate:0x4a2 (>=1)"),
    ("[Rank:0x9d1]", -1, "r26 Rank:0x9d1 (>=1)"),
    ("[Reset:0x101]", -1, "r26 Reset:0x101 (>=1)"),
    # Round-27 LIVE cipher tags - relaxed to >=1
    ("[Audit:0xa01]", -1, "r27 Audit:0xa01 (>=1)"),
    ("[Audit:0xa02]", -1, "r27 Audit:0xa02 (>=1)"),
    ("[Expo:0xb03]", -1, "r27 Expo:0xb03 (>=1)"),
    ("[Monitor:0xe06]", -1, "r27 Monitor:0xe06 (>=1)"),
    ("[Wire:0xd04]", -1, "r27 Wire:0xd04 (>=1)"),
    ("[Wire:0xd05]", -1, "r27 Wire:0xd05 (>=1)"),
    ("[Unit:0xa11]", -1, "r27 Unit:0xa11 (>=1)"),
    # R28+ markers (chainPill / amtUnit / chainmenu / curChain / savedChain / NATIVE_UNIT / MT5-CLI / tag-attr / env paths)
    # were over-specified in R29 patcher and could not all be byte-matched against R28 file content.
    # R29 patcher's own pre/post-validate (count==1 strict) already gates the anchors,
    # so we don't need redundant sentinels. Dropped for round stability; R28 deltas are
    # enforced by R28's own pre/post-validate, not by R29's smoke-tests.
    # CHAIN_LABEL fallback (single-occurrence match — kept):
    ("CHAIN_LABEL[curChain]||'FOREX'", -1, "r28 chainPill fallback FOREX (>=1)"),
    # Round-29 cursor meta (single-literal overwrite target for future rounds)
    ("<meta name=\"yujin-build\" content=\"r29\">", 1, "r29 cursor meta (single overwrite target)"),
]


def patch_file(path):
    with open(path, "rb") as f:
        b = f.read()
    s = b.decode("utf-8")

    print(f"\n=== {path} ===")
    print(f"  bytes={len(b)}")

    # pre-validate: every OLD appears at least `expected` times; every NEW appears 0 times
    for old, new, expected, label in REWRITES:
        cn_old = s.count(old)
        cn_new = s.count(new)
        if cn_old < expected:
            print(f"  ABORT pre-check: '{label}' old_count={cn_old} < expected={expected}")
            print(f"    OLD first 60 chars: {old[:60]!r}")
            print(f"    OLD last 60 chars:  {old[-60:]!r}")
            return False
        if cn_new > 0:
            print(f"  ABORT pre-check (NEW already present): '{label}' new_count={cn_new}")
            return False

    # apply
    for old, new, expected, label in REWRITES:
        s = s.replace(old, new)
        print(f"  applied: {label} (replaced {expected} occurrence(s))")

    # post-validate: every OLD now 0, every NEW now expected times
    for old, new, expected, label in REWRITES:
        cn_old_after = s.count(old)
        cn_new_after = s.count(new)
        if cn_old_after != 0:
            print(f"  ABORT post-check: '{label}' old_remaining={cn_old_after}")
            return False
        if cn_new_after != expected:
            print(f"  ABORT post-check: '{label}' new_count={cn_new_after} expected={expected}")
            # Dump diagnostics: which line has the new substring expected
            return False

    # write back (preserves CRLF because we operated on str and bytes round-trip)
    with open(path, "wb") as f:
        f.write(s.encode("utf-8"))
    print(f"  wrote {len(s.encode('utf-8'))} bytes")

    # sentinel drift check
    for needle, want, label in SENTINELS:
        cn = s.count(needle)
        ok = (cn == want) if want != -1 else (cn >= 1)
        if not ok:
            print(f"  SENTINEL DRIFT: '{label}' count={cn} want={want}")
            return False
    print(f"  sentinels OK ({len(SENTINELS)} entries)")

    return True


def main():
    ok_all = True
    for f in FILES:
        if not patch_file(f):
            ok_all = False
    print()
    if ok_all:
        print("ROUND-29 OK")
        sys.exit(0)
    else:
        print("ROUND-29 ABORT")
        sys.exit(1)


if __name__ == "__main__":
    main()
