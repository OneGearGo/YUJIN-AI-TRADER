#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Round-31 revert · restore 4-chain menu + gmgn URL + savedChain=sol default
==========================================================================

Visual Unity:  https://gmgnai.github.io/skillmarket-demos/aitrader/

Round-30 cleanup (commit a1f40c2) dropped bsc/base/eth chain entries,
shrank NATIVE_UNIT/CHAIN_LABEL maps, and replaced gmgn.ai URLs with
github.com fallbacks. The user has clarified the gmgnai upstream is
the visual template — so we restore those cosmetic pieces.

NOT REVERTED (kept from R30):
  - size_sol → lots rename (the lot-unit contract is upstream-clean)
  - gmgn URL fragment `#contract-${addr}` is replaced with the upstream
    `${curChain}/token/${addr}` form (curChain is included so reference
    station visual is identical)

Sentinels:
  - R26/R27 cipher tags (>=1, relaxed for drift across templates)
  - R28 chainPill='FOREX' (==1)
  - R28 amtUnit='lots' (==1)
  - R28 size-unit 'lots' (==1)
  - R30 size_sol absent (==0 across all 3 sites)
  - R31 NEW restored (bsc/base/eth clickable entries, gmgn URL,
    savedChain default 'sol')
  - R31 NEW bumped meta + title + APP_VERSION
  - R30 OLD bumped markers (r29, v0.0.2, AI Trader · r29) all (==0)
"""

import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

FILES = [
    os.path.join(r"F:\yujin-mt5", "static", "index.html"),
    os.path.join(r"F:\yujin-mt5", "docs",   "index.html"),
]

# Anchors (old, new, label)
REWRITES = [
    # 1. chainMenu 1-div + wrapper close → 4-divs + wrapper close.
    #    MUST include trailing </div> in BOTH OLD and NEW: the OLD string is a
    #    prefix of the NEW string (FOREX line is the first of the 4 lines).
    #    Without the wrapper close, the post-check `s.count(old)` would still
    #    find the OLD substring as a prefix of NEW and ABORT strictly.
    (
        "          <div data-ch=\"forex\" onclick=\"switchChain('forex')\">FOREX</div>\r\n        </div>",
        "          <div data-ch=\"forex\" onclick=\"switchChain('forex')\">FOREX</div>\r\n          <div data-ch=\"bsc\" onclick=\"switchChain('bsc')\">BSC</div>\r\n          <div data-ch=\"base\" onclick=\"switchChain('base')\">Base</div>\r\n          <div data-ch=\"eth\" onclick=\"switchChain('eth')\">ETH</div>\r\n        </div>",
        "chainMenu 1-div+close → 4-divs+close (restore bsc/base/eth; OLD/NEW include wrapper close to avoid substring-prefix post-check loop)",
    ),
    # 2. NATIVE_UNIT map re-expand. Original pre-R30 4-key form.
    (
        "const NATIVE_UNIT={sol:'lots'};",
        "const NATIVE_UNIT={sol:'lots',bsc:'BNB',base:'ETH',eth:'ETH'};",
        "NATIVE_UNIT re-expand with bsc/base/eth native keys",
    ),
    # 3. CHAIN_LABEL map re-expand. Original pre-R30 4-key form.
    (
        "const CHAIN_LABEL={sol:'FOREX'};",
        "const CHAIN_LABEL={sol:'FOREX',bsc:'BSC',base:'Base',eth:'ETH'};",
        "CHAIN_LABEL re-expand with bsc/base/eth labels",
    ),
    # 4. gmgn URL restore. Post-R30 github fallback → upstream gmgn.ai.
    (
        "<a class=\"ca\" href=\"https://github.com/OneGearGo/YUJIN-AI-TRADER#contract-${t_.address}\" target=\"_blank\" rel=\"noopener\" title=\"${t('ca_open_title',t_.address)}\" onclick=\"event.stopPropagation()\">${shortCA(t_.address)}</a>",
        "<a class=\"ca\" href=\"https://gmgn.ai/${curChain}/token/${t_.address}\" target=\"_blank\" rel=\"noopener\" title=\"${t('ca_open_title',t_.address)}\" onclick=\"event.stopPropagation()\">${shortCA(t_.address)}</a>",
        "gmgn.ai URL restored (R30 github fallback undone)",
    ),
    # 5. savedChain default 'forex' → 'sol'. Match gmgnai ref selected chain.
    (
        "localStorage.getItem('aitrader_chain')||'forex'",
        "localStorage.getItem('aitrader_chain')||'sol'",
        "savedChain default 'forex' → 'sol' (R28 round-trip reset)",
    ),
    # 6-8. R29 → R31 marker bump (anti-cache + version visibility).
    (
        "<meta name=\"yujin-build\" content=\"r29\">",
        "<meta name=\"yujin-build\" content=\"r31\">",
        "yujin-build meta r29 → r31",
    ),
    (
        "<title>AI Trader · r29 - \u81ea\u52a8\u7b5b\u9009\uff0c\u4e00\u952e\u6210\u4ea4\uff0c\u6301\u4ed3\u76d1\u63a7</title>",
        "<title>AI Trader · r31 - \u81ea\u52a8\u7b5b\u9009\uff0c\u4e00\u952e\u6210\u4ea4\uff0c\u6301\u4ed3\u76d1\u63a7</title>",
        "title suffix r29 → r31",
    ),
    (
        "const APP_VERSION='v0.0.2';",
        "const APP_VERSION='v0.0.3';",
        "APP_VERSION v0.0.2 → v0.0.3",
    ),
]

# Sentinels (must remain present after patch with the expected count)
SENTINELS = [
    # R28+ preserved labels (==1)
    ("<span class=\"v\" id=\"chainPill\">FOREX</span>", 1, "R28 chainPill FOREX"),
    ("<span class=\"amt-lbl\" id=\"amtUnit\">lots</span>", 1, "R28 amtUnit lots"),
    ("<span class=\"unit\">lots</span>", 1, "R28 size-unit lots"),
    ("MT5-CLI \u5e02\u573a\u547d\u4ee4", 1, "R28 CLI zh label"),
    # R31 NEW restored (==1, was ==0 in R30)
    ("data-ch=\"bsc\" onclick=\"switchChain('bsc')\"", 1, "R31 chainMenu bsc restored"),
    ("data-ch=\"base\" onclick=\"switchChain('base')\"", 1, "R31 chainMenu base restored"),
    ("data-ch=\"eth\" onclick=\"switchChain('eth')\"", 1, "R31 chainMenu eth restored"),
    ("localStorage.getItem('aitrader_chain')||'sol'", 1, "R31 savedChain default sol"),
    ("{sol:'lots',bsc:'BNB',base:'ETH',eth:'ETH'}", 1, "R31 NATIVE_UNIT 4-key re-expanded"),
    ("{sol:'FOREX',bsc:'BSC',base:'Base',eth:'ETH'}", 1, "R31 CHAIN_LABEL 4-key re-expanded"),
    ("https://gmgn.ai/${curChain}/token/${t_.address}", 1, "R31 gmgn URL restored"),
    # R31 NEW bumped (==1)
    ("<meta name=\"yujin-build\" content=\"r31\">", 1, "R31 meta version"),
    ("APP_VERSION='v0.0.3'", 1, "R31 APP_VERSION v0.0.3"),
    ("AI Trader \u00b7 r31", 1, "R31 title suffix"),
    # 12 R26/R27 cipher tags (>=1, relaxed for drift safety)
    ("[Hash:0xa3c]", -1, "R26 Hash"),
    ("[Codepath:0xff1]", -1, "R26 Codepath"),
    ("[Gate:0x4a2]", -1, "R26 Gate"),
    ("[Rank:0x9d1]", -1, "R26 Rank"),
    ("[Reset:0x101]", -1, "R26 Reset"),
    ("[Audit:0xa01]", -1, "R27 Audit"),
    ("[Audit:0xa02]", -1, "R27 Audit"),
    ("[Expo:0xb03]", -1, "R27 Expo"),
    ("[Monitor:0xe06]", -1, "R27 Monitor"),
    ("[Wire:0xd04]", -1, "R27 Wire"),
    ("[Wire:0xd05]", -1, "R27 Wire"),
    ("[Unit:0xa11]", -1, "R27 Unit"),
    # R30/R29 stale markers (==0). Their absence confirms the bump.
    ("<meta name=\"yujin-build\" content=\"r29\">", 0, "R30 old meta gone"),
    ("APP_VERSION='v0.0.2'", 0, "R30 old APP_VERSION gone"),
    ("AI Trader \u00b7 r29", 0, "R30 old title gone"),
    ("NATIVE_UNIT={sol:'lots'};", 0, "R30 compact NATIVE absent"),
    ("CHAIN_LABEL={sol:'FOREX'};", 0, "R30 compact CHAIN_LABEL absent"),
    ("https://github.com/OneGearGo/YUJIN-AI-TRADER#contract-", 0, "R30 github URL gone"),
    ("localStorage.getItem('aitrader_chain')||'forex'", 0, "R30 savedChain default forex gone"),
    # R30 size_sol stays removed (==0 across 3 sites)
    ("size:dec.size_sol", 0, "R30 dec.size_sol absent"),
    ("size:q.size_sol", 0, "R30 q.size_sol absent"),
    ("size_sol:size", 0, "R30 /api/buy body size_sol absent"),
]


def patch_file(path):
    with open(path, "rb") as f:
        b = f.read()
    s = b.decode("utf-8")

    print(f"\n=== {path} ===")
    print(f"  bytes={len(b)}")

    # pre-validate + captured count
    captured = []
    for old, new, label in REWRITES:
        cn_old = s.count(old)
        cn_new = s.count(new)
        if cn_old < 1:
            print(f"  ABORT pre-check: '{label}' old_count={cn_old} < 1")
            print(f"    OLD first 80: {old[:80]!r}")
            return False
        if cn_new > 0 and old.find(new) == -1:
            print(f"  ABORT pre-check (NEW pre-existed): '{label}' new_count={cn_new}")
            return False
        captured.append(cn_old)

    # apply
    for (old, new, label), expected in zip(REWRITES, captured):
        s = s.replace(old, new)
        print(f"  applied: {label} (replaced {expected})")

    # post-validate strict-equality
    for (old, new, label), expected in zip(REWRITES, captured):
        cn_old_after = s.count(old)
        cn_new_after = s.count(new)
        if cn_old_after != 0:
            print(f"  ABORT post-check: '{label}' old_remaining={cn_old_after}")
            return False
        if cn_new_after != expected:
            print(f"  ABORT post-check: '{label}' new_count={cn_new_after} != expected {expected}")
            return False

    # sentinel drift FIRST (no write if drift)
    for needle, want, label in SENTINELS:
        cn = s.count(needle)
        ok = (cn == want) if want != -1 else (cn >= 1)
        if not ok:
            print(f"  SENTINEL DRIFT: '{label}' count={cn} want={want}")
            return False
    print(f"  sentinels OK ({len(SENTINELS)} entries)")

    # write
    with open(path, "wb") as f:
        f.write(s.encode("utf-8"))
    print(f"  wrote {len(s.encode('utf-8'))} bytes")
    return True


def main():
    ok_all = True
    for f in FILES:
        if not patch_file(f):
            ok_all = False
    print()
    if ok_all:
        print("ROUND-31 OK")
        sys.exit(0)
    else:
        print("ROUND-31 ABORT")
        sys.exit(1)


if __name__ == "__main__":
    main()
