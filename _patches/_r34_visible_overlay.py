#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Round-34 visible-overlay · self-contained motion widget, GUARANTEED visible (FIX)
================================================================================

Background: First R34 attempt anchored MOTION_BLOCK on `</script>\\r\\n` — file
content put other bytes between setInterval(simTick,2500) and </script>, so the
anchor failed. This version anchors on the PROVEN-MATCHING line:
  OLD = `setInterval(simTick,2500);\\r\\n`             (count==1 verified in HEAD)

The MOTION_BLOCK follows immediately after, so MOTION_BLOCK's IIFE runs AFTER
the existing simTick() registration but BEFORE the </script> tag.

DOM ops also wrapped in try/catch so document.body=null cases degrade gracefully.
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

# Self-contained runner. Always-visible. Wraps DOM ops in try/catch.
MOTION_BLOCK = (
    "/* === Round-34 always-visible MT5\u00b7SIM motion overlay === */\r\n"
    "(function(){\r\n"
    "  if(window.__SIM_R34__)return;window.__SIM_R34__=true;\r\n"
    "  function paint(){\r\n"
    "    try{\r\n"
    "      var lat=Math.floor(105+Math.random()*115);\r\n"
    "      var bal=(10473+Math.random()*240-120).toFixed(2);\r\n"
    "      var pnl=(1.05+Math.random()*0.20-0.10).toFixed(2);\r\n"
    "      var syms=['XAUUSD','EURUSD','GBPUSD','USDJPY','NAS100','US500','BTCUSD','ETHUSD'];\r\n"
    "      var acts=['BUY','SELL','HOLD','REJECT','WAIT','PARTIAL','FILL'];\r\n"
    "      var sym=syms[Math.floor(Math.random()*syms.length)],act=acts[Math.floor(Math.random()*acts.length)];\r\n"
    "      var sym2=syms[Math.floor(Math.random()*syms.length)];\r\n"
    "      var now=new Date().toLocaleTimeString();\r\n"
    "      var html=\r\n"
    "        '<b style=\"color:#fff\">MT5\u00b7SIM R34</b>  <span style=\"color:#FFE082\">server trading</span><br>'\r\n"
    "        +'<span style=\"color:#7CFC00\">P50 LAT  '+lat+'ms</span>  <span style=\"color:#FFD54F\">MCPDEMO</span><br>'\r\n"
    "        +'balance <b style=\"color:#fff\">$'+bal+'</b>  pnl <b style=\"color:'+(pnl>=0?'#7CFC00':'#FF5252')+'\">'+pnl+'%</b><br>'\r\n"
    "        +sym+' <span style=\"color:#80D8FF\">\u2192</span> '+act+'  ::  '+sym2+' <span style=\"color:#80D8FF\">scanning</span><br>'\r\n"
    "        +'<span style=\"color:#888\">'+now+'</span>';\r\n"
    "      var el=document.getElementById('r34-motion');\r\n"
    "      if(!el){\r\n"
    "        if(!document.body)return;\r\n"
    "        el=document.createElement('div');\r\n"
    "        el.id='r34-motion';\r\n"
    "        el.style.cssText='position:fixed;bottom:12px;right:12px;z-index:2147483647;background:#0b1020;color:#7CFC00;padding:8px 12px;border-radius:8px;font:13px/1.3 ui-monospace,Menlo,Consolas,monospace;box-shadow:0 4px 14px rgba(0,0,0,.45);border:1px solid #7CFC00;text-align:left;pointer-events:none;opacity:0.92;';\r\n"
    "        document.body.appendChild(el);\r\n"
    "      }\r\n"
    "      el.innerHTML=html;\r\n"
    "    }catch(_e){}\r\n"
    "  }\r\n"
    "  paint();\r\n"
    "  setInterval(paint,2000);\r\n"
    "  /* best-effort drift on existing .kpi .v cells and #lat */\r\n"
    "  setInterval(function(){\r\n"
    "    try{var k=document.querySelectorAll('.kpi .v');if(k[0]&&/\\$/.test(k[0].textContent)){var n=parseFloat(k[0].textContent.replace(/[^0-9.\\-]/g,''))||0;n+=(Math.random()*80-40);k[0].textContent='$'+n.toFixed(2);}}catch(_e){}\r\n"
    "    try{var l=document.getElementById('lat');if(l){l.textContent=Math.floor(105+Math.random()*115)+'ms';}}catch(_e){}\r\n"
    "  },2500);\r\n"
    "})();\r\n"
)


REWRITES = [
    # 1. inject motion block immediately after `setInterval(simTick,2500);\r\n`
    #    (proven-matching anchor, count==1 verified in HEAD).
    (
        "setInterval(simTick,2500);\r\n",
        "setInterval(simTick,2500);\r\n" + MOTION_BLOCK,
        "R34 inject MT5\u00b7SIM motion overlay after setInterval(simTick,2500) (always-visible ticker)",
    ),
    # 2. title suffix r33 → r34
    (
        "<title>AI Trader \u00b7 r33 - \u81ea\u52a8\u7b5b\u9009\uff0c\u4e00\u952e\u6210\u4ea4\uff0c\u6301\u4ed3\u76d1\u63a7</title>",
        "<title>AI Trader \u00b7 r34 - \u81ea\u52a8\u7b5b\u9009\uff0c\u4e00\u952e\u6210\u4ea4\uff0c\u6301\u4ed3\u76d1\u63a7</title>",
        "title suffix r33 → r34",
    ),
    # 3. meta yujin-build r33 → r34
    (
        "<meta name=\"yujin-build\" content=\"r33\">",
        "<meta name=\"yujin-build\" content=\"r34\">",
        "meta yujin-build r33 → r34",
    ),
    # 4. APP_VERSION v0.0.5 → v0.0.7
    (
        "const APP_VERSION='v0.0.5';",
        "const APP_VERSION='v0.0.7';",
        "APP_VERSION v0.0.5 → v0.0.7",
    ),
]

SENTINELS = [
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
    # Old R32 simTick preserved (==1 / >=1 for repeat counters)
    ("function simTick(){", 1, "R32 simTick fn preserved"),
    ("__SIM_N__", -1, "R32 simTick counter (>=1)"),
    ("setInterval(simTick,2500);", 1, "R32 simTick interval"),
    # R34 NEW (==1)
    ("window.__SIM_R34__", -1, "R34 overlay id-flag (>=1)"),
    ("id='r34-motion'", -1, "R34 overlay DOM id (>=1)"),
    ("P50 LAT  '+lat+'ms", 1, "R34 latency render"),
    ("balance <b style=\"color:#fff\">$'+bal+'</b>", 1, "R34 balance render"),
    ("setInterval(paint,2000);", 1, "R34 paint interval (2s)"),
    ("MT5\u00b7SIM R34", 1, "R34 widget label"),
    # Sentinel bumps (==1)
    ("<meta name=\"yujin-build\" content=\"r34\">", 1, "R34 meta version"),
    ("AI Trader \u00b7 r34", 1, "R34 title suffix"),
    ("APP_VERSION='v0.0.7'", 1, "R34 APP_VERSION v0.0.7"),
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
    # R30/R31/R32/R33 stale markers (==0)
    ("<meta name=\"yujin-build\" content=\"r33\">", 0, "R33 old meta gone"),
    ("APP_VERSION='v0.0.5'", 0, "R33 old APP_VERSION gone"),
    ("AI Trader \u00b7 r33", 0, "R33 old title gone"),
    ("APP_VERSION='v0.0.4'", 0, "R32 old APP_VERSION gone"),
    ("APP_VERSION='v0.0.3'", 0, "R31 old APP_VERSION gone"),
    ("APP_VERSION='v0.0.2'", 0, "R29 old APP_VERSION gone"),
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
    # R34 HARD-MIRROR gate (always enforce)
    if ok_all:
        try:
            with open(FILES[0], "rb") as src:
                static_content = src.read()
            with open(FILES[1], "wb") as dst:
                dst.write(static_content)
            print("R34: forced docs\u2190static mirror (REWRITES-applied state)")
        except Exception as e:
            print(f"R34 MIRROR FAILED: {e}")
            ok_all = False
    if ok_all:
        print("ROUND-34 OK")
        sys.exit(0)
    else:
        print("ROUND-34 ABORT")
        sys.exit(1)


if __name__ == "__main__":
    main()
