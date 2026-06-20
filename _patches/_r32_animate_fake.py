#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Round-32 animate · MT5 假数据 in motion on https://onegeargo.github.io/YUJIN-AI-TRADER/
========================================================================================

Visual Unity:  https://gmgnai.github.io/skillmarket-demos/aitrader/

The user wants the live demo to LOOK like the gmgnai reference: data is moving.
Round-32 injects a simTick() that runs on a 2.5-second interval and mutates
visible UI bits so the page appears to be streaming market data.

Five motion lanes (chosen because they are salient in the gmgnai reference):

  1. P50 LAT pill       — `[data-lat]` / `[class*="lat" i]` / `[id*="lat" i]` cycles 105-220ms
  2. KPI bank-balance   — first KPI value drifts by +/- $40 per tick
  3. KPI pnl-percent    — second KPI drifts by +/- 0.05% per tick
  4. KPI block-hole-fill — third KPI cycles 1..9
  5. decision-log       — appends fake rows to `<ol#decLog>` or `#log` if present

All moves touch only DOM text. Existing sentinel and structural pieces
(R28 chainPill, R31 chainMenu, R31 NATIVE_UNIT, R31 CHAIN_LABEL,
R31 savedChain default, R31 gmgn URL, R26/R27 cipher tags) are preserved.
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

# Anchor #1 wraps the canonical tail pattern `autoConnect();\r\n</script>` so
# OLD is NOT a substring of NEW (NEW intermixes SIMTICK_BLOCK between
# autoConnect() and </script>, breaking any prefix overlap).
SIMTICK_BLOCK = (
    "/* === Round-32 animate fake MT5 data on live site (visual unity with"
    " gmgnai ref) === */\r\n"
    "var __SIM_T0__=Date.now(),__SIM_N__=0;\r\n"
    "function simTick(){\r\n"
    "  __SIM_N__++;\r\n"
    "  try{\r\n"
    "    /* (1) latency pill [P50 LAT] */\r\n"
    "    var lat=document.querySelector('[data-lat],[class*=\"lat\" i],[id*=\"lat\" i]');\r\n"
    "    if(lat){var v=Math.floor(105+Math.random()*115);lat.textContent='\\u00a0'+v+'ms\\u00a0';}\r\n"
    "    /* (2) KPI drift on .kpi .v / .kpi-v / .k .v cells */\r\n"
    "    var kpi1=document.querySelectorAll('.kpi .v,.kpi-v,.k .v');\r\n"
    "    if(kpi1.length>=3){\r\n"
    "      var b=kpi1[0];if(/\\$/.test(b.textContent)){\r\n"
    "        var n=parseFloat(b.textContent.replace(/[^0-9.\\-]/g,''))||0;\r\n"
    "        n=n+(Math.random()*80-40);b.textContent='$'+n.toFixed(2);}\r\n"
    "      var p=kpi1[1];if(/%/.test(p.textContent)){\r\n"
    "        var n=parseFloat(p.textContent.replace(/[^0-9.\\-]/g,''))||0;\r\n"
    "        n=n+(Math.random()*0.10-0.05);p.textContent=(n>=0?'+':'')+n.toFixed(2)+'%';}\r\n"
    "      var c=kpi1[2];c.textContent=String(1+(__SIM_N__%9));}\r\n"
    "    /* (3) append a fake decision-log entry every 5 ticks (12.5s) */\r\n"
    "    if(__SIM_N__%5===0){\r\n"
    "      var log=document.getElementById('decLog')||document.querySelector('[id*=\"log\" i],[id*=\"decision\" i]');\r\n"
    "      if(log&&log.tagName==='OL'){\r\n"
    "        var syms=['XAUUSD','EURUSD','GBPUSD','USDJPY','NAS100','US500','BTCUSD','ETHUSD'];\r\n"
    "        var acts=['REJECT','HOLD','BUY','WAIT','SELL'];\r\n"
    "        var sym=syms[__SIM_N__%syms.length],act=acts[__SIM_N__%acts.length];\r\n"
    "        var li=document.createElement('li');\r\n"
    "        li.textContent='['+new Date().toLocaleTimeString()+'] '+sym+' '+act+' (sim)';\r\n"
    "        if(log.firstChild)log.insertBefore(li,log.firstChild);\r\n"
    "          else log.appendChild(li);\r\n"
    "        while(log.children.length>8)log.removeChild(log.lastChild);}\r\n"
    "    }\r\n"
    "  }catch(_e){/* element absent on this layout — skip */}\r\n"
    "}\r\n"
    "try{simTick();}catch(_e){}\r\n"
    "setInterval(simTick,2500);\r\n"
)


# (old, new, label)
REWRITES = [
    # 1. slot simTick BEFORE </script>, AFTER autoConnect() call.
    #    Wrapping both `autoConnect();\r\n</script>` ensures OLD is NOT a
    #    substring of NEW (NEW inserts SIMTICK_BLOCK in the middle).
    (
        "autoConnect();\r\n</script>",
        "autoConnect();\r\n" + SIMTICK_BLOCK + "</script>",
        "inject simTick() + setInterval(2.5s) after autoConnect() and before </script> (data motion layer)",
    ),
    # 2. title suffix r31 → r32
    (
        "<title>AI Trader \u00b7 r31 - \u81ea\u52a8\u7b5b\u9009\uff0c\u4e00\u952e\u6210\u4ea4\uff0c\u6301\u4ed3\u76d1\u63a7</title>",
        "<title>AI Trader \u00b7 r32 - \u81ea\u52a8\u7b5b\u9009\uff0c\u4e00\u952e\u6210\u4ea4\uff0c\u6301\u4ed3\u76d1\u63a7</title>",
        "title suffix r31 → r32 (anti-cache + round bump)",
    ),
    # 3. yujin-build meta r31 → r32
    (
        "<meta name=\"yujin-build\" content=\"r31\">",
        "<meta name=\"yujin-build\" content=\"r32\">",
        "meta yujin-build r31 → r32",
    ),
    # 4. APP_VERSION v0.0.3 → v0.0.4
    (
        "const APP_VERSION='v0.0.3';",
        "const APP_VERSION='v0.0.4';",
        "APP_VERSION v0.0.3 → v0.0.4",
    ),
]

SENTINELS = [
    # R28+ preserved (==1)
    ("<span class=\"v\" id=\"chainPill\">FOREX</span>", 1, "R28 chainPill FOREX"),
    ("<span class=\"amt-lbl\" id=\"amtUnit\">lots</span>", 1, "R28 amtUnit lots"),
    ("<span class=\"unit\">lots</span>", 1, "R28 size-unit lots"),
    ("localStorage.getItem('aitrader_chain')||'sol'", 1, "R31 savedChain default sol"),
    ("https://gmgn.ai/${curChain}/token/${t_.address}", 1, "R31 gmgn URL"),
    ("data-ch=\"bsc\" onclick=\"switchChain('bsc')\"", 1, "R31 chainMenu bsc"),
    ("data-ch=\"base\" onclick=\"switchChain('base')\"", 1, "R31 chainMenu base"),
    ("data-ch=\"eth\" onclick=\"switchChain('eth')\"", 1, "R31 chainMenu eth"),
    ("{sol:'lots',bsc:'BNB',base:'ETH',eth:'ETH'}", 1, "R31 NATIVE_UNIT 4-key"),
    ("{sol:'FOREX',bsc:'BSC',base:'Base',eth:'ETH'}", 1, "R31 CHAIN_LABEL 4-key"),
    ("MT5-CLI \u5e02\u573a\u547d\u4ee4", 1, "R28 MT5-CLI zh"),
    # R32 NEW preserved (>=1)
    ("function simTick(){", 1, "R32 simTick fn"),
    ("__SIM_N__", -1, "R32 simTick counter (>=1)"),
    ("simTick();", 1, "R32 simTick initial call"),
    ("setInterval(simTick,2500);", 1, "R32 simTick interval(2.5s)"),
    ("Querying '[data-lat]", 0, "R32 latency selector absent-of-typo"),
    # R32 bumped (==1)
    ("<meta name=\"yujin-build\" content=\"r32\">", 1, "R32 meta version"),
    ("AI Trader \u00b7 r32", 1, "R32 title suffix"),
    ("APP_VERSION='v0.0.4'", 1, "R32 APP_VERSION v0.0.4"),
    # R26/R27 cipher tags (>=1, relaxed)
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
    # R30/R31 stale markers (==0). Their absence confirms the bump.
    ("<meta name=\"yujin-build\" content=\"r31\">", 0, "R31 old meta gone"),
    ("APP_VERSION='v0.0.3'", 0, "R31 old APP_VERSION gone"),
    ("AI Trader \u00b7 r31", 0, "R31 old title gone"),
    ("NATIVE_UNIT={sol:'lots'};", 0, "R30 compact NATIVE absent"),
    ("CHAIN_LABEL={sol:'FOREX'};", 0, "R30 compact CHAIN_LABEL absent"),
    ("https://github.com/OneGearGo/YUJIN-AI-TRADER#contract-", 0, "R30 github URL gone"),
    ("size:dec.size_sol", 0, "R30 dec.size_sol absent"),
    ("size:q.size_sol", 0, "R30 q.size_sol absent"),
    ("size_sol:size", 0, "R30 /api/buy size_sol absent"),
]


def patch_file(path):
    with open(path, "rb") as f:
        b = f.read()
    s = b.decode("utf-8")

    print(f"\n=== {path} ===")
    print(f"  bytes={len(b)}")

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

    for (old, new, label), expected in zip(REWRITES, captured):
        s = s.replace(old, new)
        print(f"  applied: {label} (replaced {expected})")

    for (old, new, label), expected in zip(REWRITES, captured):
        cn_old_after = s.count(old)
        cn_new_after = s.count(new)
        if cn_old_after != 0:
            print(f"  ABORT post-check: '{label}' old_remaining={cn_old_after}")
            return False
        if cn_new_after != expected:
            print(f"  ABORT post-check: '{label}' new_count={cn_new_after} != expected {expected}")
            return False

    for needle, want, label in SENTINELS:
        cn = s.count(needle)
        ok = (cn == want) if want != -1 else (cn >= 1)
        if not ok:
            print(f"  SENTINEL DRIFT: '{label}' count={cn} want={want}")
            return False
    print(f"  sentinels OK ({len(SENTINELS)} entries)")

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
        print("ROUND-32 OK")
        sys.exit(0)
    else:
        print("ROUND-32 ABORT")
        sys.exit(1)


if __name__ == "__main__":
    main()
