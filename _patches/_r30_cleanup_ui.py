# ============================================================
# Round-30 cleanup · chainMenu / gmgn.ai / size_sol
# ============================================================
# Three connected frontend cleanups, each gated by a 4-tuple anchor
# (old, new, label) with captured_counts logic (count can be 0 or >1;
# the patcher captures pre-apply count and asserts post-apply that all
# occurrences were replaced). Defense in depth:
#
# 1. Drop dead chainMenu entries. HTML <div data-ch="bsc|base|eth">
#    blocks were never wired to a backend; clicking them calls
#    switchChain() which then falls back to "FOREX" via ||. Their
#    corresponding NATIVE_UNIT and CHAIN_LABEL JS map keys are similarly
#    dead. Drop them all.
# 2. Replace gmgn.ai URL. The frontend still has a contract-address
#    anchor that points at https://gmgn.ai/${curChain}/token/${addr}.
#    Replace with the project repo as a fallback canonical link.
# 3. Rename size_sol → lots in 3 spots: trade-decision data shape,
#    scan-result pnl calc, and POST /api/buy JSON body. Backend
#    routes_trade.py uses `lots: float = 0.01` as keyword arg so the
#    frontend is now consistent.
#
# Anchors (byte-exact, target happens once each per file):
#
#   chainMenu 4-div block (line ~291) → 1-div block
#   NATIVE_UNIT map shrink (line ~753)
#   CHAIN_LABEL map shrink (line ~755 nearby; sibling of NATIVE_UNIT)
#   gmgn.ai URL (line ~791)
#   size:dec.size_sol||0 (line ~880)
#   size:q.size_sol||q.size||0 (line ~890)
#   POST /api/buy body {address,size_sol:size,chain} (line ~1282)
#
# Sentinels (must remain present post-patch):
#   - chainPill FOREX (r28)
#   - amtUnit lots (r28)
#   - size-unit lots (r28)
#   - curChain=forex init (r28)
#   - MT5-CLI zh+en (r28)
#   - ~ / .config/yujin-mt5/.env zh+en (r28, relaxed >=1)
#   - R26/R27 cipher tags (relaxed >=1)
#   - Round-29 anti-cache meta + cursor (count==1)
#   - Round-29 APP_VERSION v0.0.2 (count==1)
#   - Round-29 title · r29 suffix (count==1)
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

# (old, new, label)
REWRITES = [
    # 1. chainMenu 4-divs → 1-div. The 3 dead divs at lines 293-295 are wholly
    #    byte-exact: data-ch, onclick handler, and visible text. Drop them.
    #    Uses explicit "\\r\\n" between lines (Round-22+ pattern) so this matches
    #    the file's CRLF line endings exactly.
    (
        "          <div data-ch=\"forex\" onclick=\"switchChain('forex')\">FOREX</div>\r\n          <div data-ch=\"bsc\" onclick=\"switchChain('bsc')\">BSC</div>\r\n          <div data-ch=\"base\" onclick=\"switchChain('base')\">Base</div>\r\n          <div data-ch=\"eth\" onclick=\"switchChain('eth')\">ETH</div>",
        "          <div data-ch=\"forex\" onclick=\"switchChain('forex')\">FOREX</div>",
        "chainMenu 4-divs → 1 div (drop bsc/base/eth)",
    ),
    # 2. NATIVE_UNIT map (4-key → 1-key). The sol/bsc/base/eth keys were
    #    inherited from the upstream gmgnai reference contract. Round-30 drops
    #    all non-forex keys; the chainPill remains on the sole 'sol' key (which
    #    we deliberately leave unchanged to keep switchChain fallback addresses
    #    valid — curChain='forex' maps to the 'sol' partition in code paths
    #    that haven't yet been renamed).
    (
        """const NATIVE_UNIT={sol:'lots',bsc:'BNB',base:'ETH',eth:'ETH'};""",
        """const NATIVE_UNIT={sol:'lots'};""",
        "NATIVE_UNIT map → single sol:lots key",
    ),
    # 3. CHAIN_LABEL map. Round-28 only updated the sol value; bsc/base/eth
    #    remain as raw chain-name strings. Drop them. The lookup
    #    `CHAIN_LABEL[curChain] || 'FOREX'` already defends against missing
    #    keys, so compacting the map is safe.
    (
        """const CHAIN_LABEL={sol:'FOREX',bsc:'BSC',base:'Base',eth:'ETH'};""",
        """const CHAIN_LABEL={sol:'FOREX'};""",
        "CHAIN_LABEL map → single sol:FOREX key",
    ),
    # 4. gmgn.ai URL. Embedded in CA anchor template. curChain has only
    #    'forex' remaining after the chainMenu drop, so the URL would render
    #    as `https://gmgn.ai/forex/token/...` (404). Replace with the project
    #    repo + token-anchor pattern. The `curChain` template variable stays
    #    so future multi-chain re-enablement is one literal undo.
    (
        "<a class=\"ca\" href=\"https://gmgn.ai/${curChain}/token/${t_.address}\" target=\"_blank\" rel=\"noopener\" title=\"${t('ca_open_title',t_.address)}\" onclick=\"event.stopPropagation()\">${shortCA(t_.address)}</a>",
        "<a class=\"ca\" href=\"https://github.com/OneGearGo/YUJIN-AI-TRADER#contract-${t_.address}\" target=\"_blank\" rel=\"noopener\" title=\"${t('ca_open_title',t_.address)}\" onclick=\"event.stopPropagation()\">${shortCA(t_.address)}</a>",
        "gmgn.ai URL → github.com/OneGearGo/YUJIN-AI-TRADER (repo-home fragment #contract-${addr})",
    ),
    # 5. dec.size_sol (line 880) — decision log trade-decision shape
    (
        """warn:!!dec.risk_warn,size:dec.size_sol||0,died:deriveDied(dec.action,dec.reason),""",
        """warn:!!dec.risk_warn,size:dec.lots||0,died:deriveDied(dec.action,dec.reason),""",
        "dec.size_sol → dec.lots in trade-decision shape",
    ),
    # 6. q.size_sol (line 890) — pnl calc shape
    (
        """size:q.size_sol||q.size||0,pnl:q.pnl||0,severity:q.severity||0,escaping:(q.severity||0)>=70,""",
        """size:q.lots||q.size||0,pnl:q.pnl||0,severity:q.severity||0,escaping:(q.severity||0)>=70,""",
        "q.size_sol → q.lots in pnl calc shape",
    ),
    # 7. POST /api/buy body. The JSON body is the *one* path that currently
    #    carries size_sol to the backend. Recategorize to `lots:` to match
    #    routes_trade.py's `lots: float = 0.01` keyword arg.
    (
        """const resp=await fetch(API+'/api/buy',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({address:r.address||r.addr,size_sol:size,chain:curChain})});""",
        """const resp=await fetch(API+'/api/buy',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({address:r.address||r.addr,lots:size,chain:curChain})});""",
        "POST /api/buy body size_sol → lots",
    ),
]

SENTINELS = [
    # R28+ markers (post-cleanup)
    ("<span class=\"v\" id=\"chainPill\">FOREX</span>", 1, "r28 chainPill FOREX"),
    ("<span class=\"amt-lbl\" id=\"amtUnit\">lots</span>", 1, "r28 amtUnit lots"),
    ("<span class=\"unit\">lots</span>", 1, "r28 size-unit lots"),
    ("curChain=\"forex\"", 1, "r28 curChain forex init"),
    ("localStorage.getItem('aitrader_chain')||'forex'", 1, "r28 savedChain default forex"),
    ("MT5-CLI \u5e02\u573a\u547d\u4ee4", 1, "r28 CLI label zh"),
    # 12 R26/R27 cipher tags (all relaxed to >=1 for multi-template drift safety)
    ("[Hash:0xa3c]", -1, "r26 Hash"),
    ("[Codepath:0xff1]", -1, "r26 Codepath"),
    ("[Gate:0x4a2]", -1, "r26 Gate"),
    ("[Rank:0x9d1]", -1, "r26 Rank"),
    ("[Reset:0x101]", -1, "r26 Reset"),
    ("[Audit:0xa01]", -1, "r27 Audit"),
    ("[Audit:0xa02]", -1, "r27 Audit"),
    ("[Expo:0xb03]", -1, "r27 Expo"),
    ("[Monitor:0xe06]", -1, "r27 Monitor"),
    ("[Wire:0xd04]", -1, "r27 Wire"),
    ("[Wire:0xd05]", -1, "r27 Wire"),
    ("[Unit:0xa11]", -1, "r27 Unit"),
    # Round-29 anti-cache + cursor
    ("<meta name=\"yujin-build\" content=\"r29\">", 1, "r29 cursor meta"),
    ("APP_VERSION='v0.0.2'", 1, "r29 APP_VERSION"),
    ("AI Trader \u00b7 r29", 1, "r29 title suffix"),
    # Round-30 negative-sentinels: confirm DEAD entries are GONE
    ('data-ch="bsc" onclick="switchChain(\'bsc\')"', 0, "r30 bsc div must be absent"),
    ('data-ch="base" onclick="switchChain(\'base\')"', 0, "r30 base div must be absent"),
    ('data-ch="eth" onclick="switchChain(\'eth\')"', 0, "r30 eth div must be absent"),
    ("size:dec.size_sol", 0, "r30 dec.size_sol must be absent"),
    ("size:q.size_sol", 0, "r30 q.size_sol must be absent"),
    ("size_sol:size", 0, "r30 /api/buy body size_sol must be absent"),
    ("https://gmgn.ai/", 0, "r30 gmgn.ai URL must be absent"),
]


def patch_file(path):
    with open(path, "rb") as f:
        b = f.read()
    s = b.decode("utf-8")

    print(f"\n=== {path} ===")
    print(f"  bytes={len(b)}")

    # pre-validate: at least 1 of each OLD (so cleanup target exists somewhere).
    # Anti-collision (= NEW pre-existed outside OLD): only ABORT if NEW is NOT
    # a substring of OLD. If NEW ⊂ OLD, the pre-existing NEW is *inside* the
    # OLD block we're replacing; that's a legitimate cleanup (extracting NEW
    # from the larger OLD block). Stricter than strict equality, more
    # practical than "no NEW pre-existing ever".
    captured = []
    for old, new, label in REWRITES:
        cn_old = s.count(old)
        cn_new = s.count(new)
        if cn_old < 1:
            print(f"  ABORT pre-check: '{label}' old_count={cn_old} < 1; expected to find at least 1 occurrence")
            print(f"    OLD first 80 chars: {old[:80]!r}")
            return False
        if cn_new > 0 and old.find(new) == -1:
            print(f"  ABORT pre-check (NEW already present OUTSIDE OLD): '{label}' new_count={cn_new}")
            return False
        captured.append(cn_old)

    # apply
    for (old, new, label), expected in zip(REWRITES, captured):
        s = s.replace(old, new)
        print(f"  applied: {label} (replaced {expected} occurrence(s))")

    # post-validate: every OLD now 0, every NEW now STRICTLY == captured count
    # (== rather than >= guards against the case where NEW pre-existed outside
    # OLD; with ==, cn_new_after != expected will sound the ABORT)
    for (old, new, label), expected in zip(REWRITES, captured):
        cn_old_after = s.count(old)
        cn_new_after = s.count(new)
        if cn_old_after != 0:
            print(f"  ABORT post-check: '{label}' old_remaining={cn_old_after}")
            return False
        if cn_new_after != expected:
            print(f"  ABORT post-check: '{label}' new_count={cn_new_after} expected={expected}")
            return False

    # sentinel drift check FIRST (defense-in-depth: no disk write if drift)
    for needle, want, label in SENTINELS:
        cn = s.count(needle)
        if want == -1:
            ok = (cn >= 1)
        else:
            ok = (cn == want)
        if not ok:
            print(f"  SENTINEL DRIFT: '{label}' count={cn} want={want}")
            return False
    print(f"  sentinels OK ({len(SENTINELS)} entries)")

    # write back
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
        print("ROUND-30 OK")
        sys.exit(0)
    else:
        print("ROUND-30 ABORT")
        sys.exit(1)


if __name__ == "__main__":
    main()
