# -*- coding: utf-8 -*-
"""Round-28: CHAIN SOL -> FOREX (replace SOL with MT5 forex equivalents).

Replaces ALL remaining SOL/CHAIN/GMGN visible labels in
/f/yujin-mt5/static/index.html + /f/yujin-mt5/docs/index.html
with MT5 forex equivalents.

Each r-triple / regular-triple closes immediately after the last content char
(NO trailing whitespace) -- Round-27 lesson: drift came from trailing-space
inside r-strings; forgetting to remove the space made every anchor mismatch.

Anchors are tuples: (old, new, expected_count_before, label).
expected_count: pre-validation invariant, 1 for single-occurrence.

Logic per file:
    1. pre-validate: content.count(old) == expected_count
    2. replace ALL occurrences: content = content.replace(old, new)
    3. post-validate:
         - content.count(old) == 0
         - content.count(new) == expected_count

SENTINELS list: things that must NOT change (Round-19 demobar, Round-23 tag,
Round-26 I18N + cipher tags, Round-27 cipher tags, APP_VERSION const,
tag-attribute). Drift = ABORT.

One multi-line anchor for chainPill initial load uses regular Python
double-quoted string with explicit CRLF escape so the CR+LF bytes match the
file's CRLF content. All other anchors use plain triple strings.
"""

import sys
import os

# Reconfigure stdout to UTF-8 so debug prints containing high-codepoint
# chars do not crash the Windows GBK codec.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # py3.7+
except Exception:
    pass

FILES = [
    os.path.join(r"F:\yujin-mt5", "static", "index.html"),
    os.path.join(r"F:\yujin-mt5", "docs",   "index.html"),
]

# 23 anchors. each tuple: (old, new, expected_count_before, label)
REWRITES = [
    # ---- Phase 1: visible SOL/CHAIN labels (display + runtime templates) ----
    # 1. CHAIN pill display (line 286)
    (
        """<span class="v" id="chainPill">SOL</span>""",
        """<span class="v" id="chainPill">FOREX</span>""",
        1, "CHAIN pill display",
    ),
    # 2. chainmenu SOL entry (line 288)
    (
        """<div data-ch="sol" onclick="switchChain('sol')">SOL</div>""",
        """<div data-ch="forex" onclick="switchChain('forex')">FOREX</div>""",
        1, "chainmenu SOL to forex menu entry",
    ),
    # 3. status panel amtUnit (line 307)
    (
        """<span class="amt-lbl" id="amtUnit">SOL</span>""",
        """<span class="amt-lbl" id="amtUnit">lots</span>""",
        1, "status panel amtUnit",
    ),
    # 4. buy size unit span (line 370)
    (
        """<span class="unit">SOL</span>""",
        """<span class="unit">lots</span>""",
        1, "buy size unit span",
    ),
    # 5. sell_msg zh runtime template (line 534)
    (
        """sell_msg:(sym,size,esc)=>`平仓 <b>${sym}</b>（${size} SOL）？`+(esc?'""",
        """sell_msg:(sym,size,esc)=>`平仓 <b>${sym}</b>（${size} lots）？`+(esc?'""",
        1, "sell_msg zh",
    ),
    # 6. sell_msg en runtime template (line 682)
    (
        """sell_msg:(sym,size,esc)=>`Close <b>${sym}</b> (${size} SOL)?`+(esc?'""",
        """sell_msg:(sym,size,esc)=>`Close <b>${sym}</b> (${size} lots)?`+(esc?'""",
        1, "sell_msg en",
    ),
    # 7. NATIVE_UNIT constant map (line 749)
    (
        """const NATIVE_UNIT={sol:'SOL',bsc:'BNB',base:'ETH',eth:'ETH'};""",
        """const NATIVE_UNIT={sol:'lots',bsc:'BNB',base:'ETH',eth:'ETH'};""",
        1, "NATIVE_UNIT map",
    ),
    # 8. CHAIN_LABEL constant map (line 750)
    (
        """const CHAIN_LABEL={sol:'SOL',bsc:'BSC',base:'Base',eth:'ETH'};""",
        """const CHAIN_LABEL={sol:'FOREX',bsc:'BSC',base:'Base',eth:'ETH'};""",
        1, "CHAIN_LABEL map",
    ),
    # 9. updateAmtUnit fallback (line 753)
    (
        """u.textContent=NATIVE_UNIT[curChain]||'SOL';""",
        """u.textContent=NATIVE_UNIT[curChain]||'lots';""",
        1, "updateAmtUnit fallback",
    ),
    # 10. risk expos bar (line 1037 occurrence 1)
    (
        """,RISK.expoMax,' SOL'""",
        """,RISK.expoMax,' lots'""",
        1, "risk expos bar",
    ),
    # 11. risk loss bar (line 1037 occurrence 2)
    (
        """,RISK.lossMax,' SOL'""",
        """,RISK.lossMax,' lots'""",
        1, "risk loss bar",
    ),
    # 12. savedChain default fallback (line 1401)
    (
        """localStorage.getItem('aitrader_chain')||'sol'""",
        """localStorage.getItem('aitrader_chain')||'forex'""",
        1, "savedChain default",
    ),
    # 13. chainPill initial load (multi-line: 1402 -> 1403)
    (
        "curChain=savedChain;\r\n  document.getElementById('chainPill').textContent=CHAIN_LABEL[curChain]||'SOL'",
        "curChain=savedChain;\r\n  document.getElementById('chainPill').textContent=CHAIN_LABEL[curChain]||'FOREX'",
        1, "chainPill initial load",
    ),
    # 14. chainPill live update (line 1414)
    (
        """d.chain;document.getElementById('chainPill').textContent=CHAIN_LABEL[curChain]||'SOL'""",
        """d.chain;document.getElementById('chainPill').textContent=CHAIN_LABEL[curChain]||'FOREX'""",
        1, "chainPill live update",
    ),
    # 15. curChain initial value (line 730)
    (
        """let pollMs=5600, pollTimer=null, defaultTrendCmd="", curChain="sol", beReady=false, buyAmount=0.01;""",
        """let pollMs=5600, pollTimer=null, defaultTrendCmd="", curChain="forex", beReady=false, buyAmount=0.01;""",
        1, "curChain init",
    ),
    # ---- Phase 2: CLI labels (gmgn -> yujin-mt5) ----
    # 16. GMGN-CLI label (zh line 356)
    (
        """>GMGN-CLI 热榜命令</label>""",
        """>MT5-CLI 市场命令</label>""",
        1, "GMGN-CLI zh label",
    ),
    # 17. gmgn-cli placeholder (zh line 356)
    (
        """placeholder="gmgn-cli market trending ..." """,
        """placeholder="mt5-cli market trending ..." """,
        1, "gmgn-cli placeholder zh",
    ),
    # 18. pipe_cmd_hint zh (line 428)
    (
        """须以 <code>gmgn-cli market trending</code> 开头""",
        """须以 <code>mt5-cli market trending</code> 开头""",
        1, "pipe_cmd_hint zh cli",
    ),
    # 19. pipe_cmd_hint en (line 576)
    (
        """must start with <code>gmgn-cli market trending</code>""",
        """must start with <code>mt5-cli market trending</code>""",
        1, "pipe_cmd_hint en cli",
    ),
    # 20. cfg_apikey_ph zh (line 417)
    (
        """cfg_apikey_ph:'留空 = 沿用 ~/.config/gmgn/.env 已有 key'""",
        """cfg_apikey_ph:'留空 = 沿用 ~/.config/yujin-mt5/.env 已有 key'""",
        1, "cfg_apikey_ph zh",
    ),
    # 21. cfg_apikey_ph en (line 565)
    (
        """cfg_apikey_ph:'Leave empty = reuse existing key in ~/.config/gmgn/.env'""",
        """cfg_apikey_ph:'Leave empty = reuse existing key in ~/.config/yujin-mt5/.env'""",
        1, "cfg_apikey_ph en",
    ),
    # 22. cfg_saved zh (line 522)
    (
        """cfg_saved:'✓ 已写入 ~/.config/gmgn/.env'""",
        """cfg_saved:'✓ 已写入 ~/.config/yujin-mt5/.env'""",
        1, "cfg_saved zh",
    ),
    # 23. cfg_saved en (line 670)
    (
        """cfg_saved:'✓ Written to ~/.config/gmgn/.env'""",
        """cfg_saved:'✓ Written to ~/.config/yujin-mt5/.env'""",
        1, "cfg_saved en",
    ),
]

SENTINELS = [
    # Round-19 demobar -- must stay untouched
    (r"""自配经销商和自营商账户信息，买卖仅在你本机执行""", "demobar zh (round-19)"),
    (r"""Self-provided broker and prop account""", "demobar en (round-19)"),
    # Round-23 tag phrase -- must stay
    (r"""你按下成交 ➡️ 人机协同 / 一锤定音 / 闭环收口 / 最终授权 / 拍板转化""", "tag zh (round-23)"),
    # Round-26 I18N entries -- must stay
    (r"""品种覆盖外汇 + 黄金 + 主要指数""", "round-26 publicbar zh"),
    (r"""Live mock data · read-only demo""", "round-26 publicbar en"),
    (r"""不上账户（当前锁定""", "round-26 mode_tip zh"),
    (r"""paper-trade (locked""", "round-26 mode_tip en"),
    (r"""经API密钥真实下单""", "round-26 cfg_mwarn zh"),
    (r"""API key into the wire""", "round-26 cfg_mwarn en"),
    # Round-26 cipher tags
    (r"""[Hash:0xa3c]""", "round-26 sig_top10sell"),
    (r"""[Codepath:0xff1]""", "round-26 inj_tip"),
    (r"""[Gate:0x4a2]""", "round-26 gatetip3"),
    (r"""[Rank:0x9d1]""", "round-26 bk_rank"),
    (r"""[Reset:0x101]""", "round-26 pipe_reset_btn_title"),
    # Round-27 cipher tags
    (r"""[Audit:0xa01]""", "round-27 detail_passed prefix"),
    (r"""[Audit:0xa02]""", "round-27 log_screen_reason prefix"),
    (r"""[Expo:0xb03]""", "round-27 kpi_sub_expo prefix"),
    (r"""[Wire:0xd04]""", "round-27 live wire-order prefix"),
    (r"""[Wire:0xd05]""", "round-27 SHADOW log prefix"),
    (r"""[Monitor:0xe06]""", "round-27 monitor prefix"),
    (r"""[Unit:0xa11]""", "round-27 cipher unit slot"),
    # Title + APP_VERSION + version line + tag attribute -- must stay
    (r"""APP_VERSION='v0.0.1'""", "APP_VERSION const"),
    (r'''data-i18n="tag"''', "tag attribute"),
]


def patch_file(path):
    with open(path, "rb") as fp:
        raw = fp.read()
    content = raw.decode("utf-8")
    orig = content

    # Pre-validate: each OLD must appear >= 1 (handles duplicate anchors
    # like the 2x <code>gmgn-cli zh hint), and each NEW must NOT be already
    # present (anti-collision vs. round status). Per-anchor old count is
    # captured for post-validation parity check.
    captured_counts = []
    for old, _new, _exp, label in REWRITES:
        n = content.count(old)
        if n < 1:
            print(f"ABORT: anchor missing in {os.path.basename(path)}")
            print(f"  label={label}  count=0")
            print(f"  old_first40={old[:40]!r}")
            return False
        if content.count(_new) != 0:
            print(f"ABORT: NEW anchor already present (collision) in {os.path.basename(path)}")
            print(f"  label={label}  new_count={content.count(_new)}")
            print(f"  new_first40={_new[:40]!r}")
            return False
        captured_counts.append(n)

    # Apply all swaps (replace ALL occurrences per anchor).
    for old, new, _exp, _label in REWRITES:
        content = content.replace(old, new)

    # Post-validate: each OLD now == 0; each NEW count matches captured old count.
    for i, (old, new, _exp, label) in enumerate(REWRITES):
        if content.count(old) != 0:
            print(f"ABORT: OLD anchor still present after replace in {os.path.basename(path)}")
            print(f"  label={label}  old_first40={old[:40]!r}")
            return False
        if content.count(new) != captured_counts[i]:
            print(f"ABORT: NEW anchor missing/wrong count in {os.path.basename(path)}")
            print(f"  label={label}  expected={captured_counts[i]}  got={content.count(new)}")
            print(f"  new_first40={new[:40]!r}  new_last40={new[-40:]!r}")
            return False

    # Sentinel drift check.
    for sentinel, label in SENTINELS:
        o = orig.count(sentinel)
        n = content.count(sentinel)
        if o != n:
            print(f"ABORT: sentinel drift in {os.path.basename(path)}: {label}")
            print(f"  orig={o}  now={n}")
            return False

    # Write back.
    with open(path, "wb") as fp:
        fp.write(content.encode("utf-8"))

    print(f"OK [{os.path.basename(path)}] {len(REWRITES)} swaps applied, sentinels preserved")
    return True


def main():
    ok = True
    for f in FILES:
        if not patch_file(f):
            ok = False
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
