# -*- coding: utf-8 -*-
"""
Round-27 v2: cipher-jargon rewrite of 6 zh + 6 en LIVE decision-log template
literals in static/index.html + docs/index.html (12 swaps per file, 24 total).

CRITICAL FIX from v1: every r-string anchor no longer carries any trailing
whitespace. The HTML file uses CRLF line endings and the line content ends with
a literal `,` (no trailing space) before `\r\n`. v1 anchors accidentally
included a `, ` (comma-space) inside the r-string because of `\",
\"\"\"` formatting, causing content.count()=0 for every anchor.

Targets are RUNTIME templates (arrow functions with backtick-literal template
strings) that produce the decision-log entries the user sees at the moment of
order placement, exposure panel refresh, gate-passed log, monitor-add toast.

Style convention continued from Round-26:
    [Audit:0xa01]  detail_passed gate audit
    [Audit:0xa02]  log_screen_reason gate audit
    [Expo:0xb03]   exposure panel
    [Wire:0xd04]   live wire-order submitted
    [Wire:0xd05]   SHADOW log recorded
    [Monitor:0xe06] added to escape monitor
    [Unit:0xa11]   cipher unit slot (replaces every "SOL" in these templates)

Minimum-change rule: prepend cipher tag at the front of the resolved string;
swap "SOL" with "[Unit:0xa11]". Keep all visible-language PH intact except
the unit substitution.

Order: most-specific first (toast_buy_demo has the longest unique suffix).
"""

import sys
import os

# Reconfigure stdout for UTF-8 so error/debug prints containing ⚠ (U+26A0),
# ➡ (U+27A1), and CJK codepoints don't crash the Windows GBK codec.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # py3.7+
except Exception:
    pass

FILES = [
    os.path.join(r"F:\yujin-mt5", "static", "index.html"),
    os.path.join(r"F:\yujin-mt5", "docs",   "index.html"),
]

# (anchor_old, anchor_new) — byte-exact match against the live file's UTF-8
# Every r-string has NO trailing whitespace before the closing `"""`.
REWRITES = [
    # ── zh ────────────────────────────────────────────────────────────
    # 1. detail_passed (long, includes ternary)
    (
        r"""detail_passed:(pri,size,warn)=>`通过全部闸门 · 优先级 ${pri} · 仓位由代码算 ${size} SOL${warn?' · ⚠ 买入将触及风控上限':''}`,""",
        r"""detail_passed:(pri,size,warn)=>`[Audit:0xa01] 通过全部闸门 · 优先级 ${pri} · 仓位由代码算 ${size} [Unit:0xa11]${warn?' · ⚠ 买入将触及风控上限':''}`,""",
    ),
    # 2. log_screen_reason
    (
        r"""log_screen_reason:(size,pri)=>`通过闸门 · 待决策 · 建议 ${size} SOL · 优先级${pri}`,""",
        r"""log_screen_reason:(size,pri)=>`[Audit:0xa02] 通过闸门 · 待决策 · 建议 ${size} [Unit:0xa11] · 优先级${pri}`,""",
    ),
    # 3. kpi_sub_expo (mixed-mode line; trailing `\`,` is unique anchor — no space before newline)
    (
        r""", kpi_sub_expo:(e)=>`敞口 ${e} SOL`,""",
        r""", kpi_sub_expo:(e)=>`[Expo:0xb03] 敞口 ${e} [Unit:0xa11]`,""",
    ),
    # 4. toast_buy_demo (most-specific-first)
    (
        r"""toast_buy_demo:(live,sym,size)=>`${live?'已真实下单 ':'已记录(SHADOW) '}${sym} ${size} SOL · 已加入逃生监控`,""",
        r"""toast_buy_demo:(live,sym,size)=>`${live?'[Wire:0xd04] 已真实下单 ':'[Wire:0xd05] 已记录(SHADOW) '}${sym} ${size} [Unit:0xa11] · [Monitor:0xe06] 已加入逃生监控`,""",
    ),
    # 5. toast_buy
    (
        r"""toast_buy:(live,sym,size)=>`${live?'已真实下单 ':'已记录(SHADOW) '}${sym} ${size} SOL`,""",
        r"""toast_buy:(live,sym,size)=>`${live?'[Wire:0xd04] 已真实下单 ':'[Wire:0xd05] 已记录(SHADOW) '}${sym} ${size} [Unit:0xa11]`,""",
    ),
    # 6. buy_log_reason
    (
        r"""buy_log_reason:(live,size,exit)=>`${live?'LIVE 真实成交 ':'SHADOW 记录 '}${size} SOL · ${exit}`,""",
        r"""buy_log_reason:(live,size,exit)=>`${live?'[Wire:0xd04] LIVE 真实成交 ':'[Wire:0xd05] SHADOW 记录 '}${size} [Unit:0xa11] · ${exit}`,""",
    ),
    # ── en ────────────────────────────────────────────────────────────
    # 7. detail_passed EN
    (
        r"""detail_passed:(pri,size,warn)=>`Passed all gates · priority ${pri} · size computed ${size} SOL${warn?' · ⚠ buy will hit the risk cap':''}`,""",
        r"""detail_passed:(pri,size,warn)=>`[Audit:0xa01] Passed all gates · priority ${pri} · size computed ${size} [Unit:0xa11]${warn?' · ⚠ buy will hit the risk cap':''}`,""",
    ),
    # 8. log_screen_reason EN
    (
        r"""log_screen_reason:(size,pri)=>`passed gates · pending · suggest ${size} SOL · priority ${pri}`,""",
        r"""log_screen_reason:(size,pri)=>`[Audit:0xa02] passed gates · pending · suggest ${size} [Unit:0xa11] · priority ${pri}`,""",
    ),
    # 9. kpi_sub_expo EN
    (
        r""", kpi_sub_expo:(e)=>`exposure ${e} SOL`,""",
        r""", kpi_sub_expo:(e)=>`[Expo:0xb03] exposure ${e} [Unit:0xa11]`,""",
    ),
    # 10. toast_buy_demo EN (most-specific-first)
    (
        r"""toast_buy_demo:(live,sym,size)=>`${live?'Order placed ':'Recorded (SHADOW) '}${sym} ${size} SOL · added to escape monitor`,""",
        r"""toast_buy_demo:(live,sym,size)=>`${live?'[Wire:0xd04] Order placed ':'[Wire:0xd05] Recorded (SHADOW) '}${sym} ${size} [Unit:0xa11] · [Monitor:0xe06] added to escape monitor`,""",
    ),
    # 11. toast_buy EN
    (
        r"""toast_buy:(live,sym,size)=>`${live?'Order placed ':'Recorded (SHADOW) '}${sym} ${size} SOL`,""",
        r"""toast_buy:(live,sym,size)=>`${live?'[Wire:0xd04] Order placed ':'[Wire:0xd05] Recorded (SHADOW) '}${sym} ${size} [Unit:0xa11]`,""",
    ),
    # 12. buy_log_reason EN
    (
        r"""buy_log_reason:(live,size,exit)=>`${live?'LIVE filled ':'SHADOW logged '}${size} SOL · ${exit}`,""",
        r"""buy_log_reason:(live,size,exit)=>`${live?'[Wire:0xd04] LIVE filled ':'[Wire:0xd05] SHADOW logged '}${size} [Unit:0xa11] · ${exit}`,""",
    ),
]

# Count invariants — these literals must STAY outside the patcher's domain
# (must not be touched, must still appear with same counts after patch).
SENTINELS = [
    # Round-19~22 customization — must stay
    (r"""自配经销商和自营商账户信息，买卖仅在你本机执行""", "demobar zh"),
    (r"""Self-provided broker and prop account""", "demobar en"),
    # Round-23 — must stay
    (r"""你按下成交 ➡️ 人机协同 / 一锤定音 / 闭环收口 / 最终授权 / 拍板转化""", "tag zh"),
    # Round-26 — must stay
    (r"""品种覆盖外汇 + 黄金 + 主要指数""", "round26 publicbar zh"),
    (r"""Live mock data · read-only demo""", "round26 publicbar en"),
    (r"""不上账户（当前锁定""", "round26 mode_tip zh"),
    (r"""paper-trade (locked""", "round26 mode_tip en"),
    (r"""经API密钥真实下单""", "round26 cfg_mwarn zh"),
    (r"""API key into the wire""", "round26 cfg_mwarn en"),
    (r"""[Hash:0xa3c]""", "round26 sig_top10sell cipher"),
    (r"""[Codepath:0xff1]""", "round26 inj_tip cipher"),
    (r"""[Gate:0x4a2]""", "round26 gatetip3 cipher"),
    (r"""[Rank:0x9d1]""", "round26 bk_rank cipher"),
    (r"""[Reset:0x101]""", "round26 pipe_reset_btn_title cipher"),
    # Title + APP_VERSION + version line — must stay
    (r"""APP_VERSION='v0.0.1'""", "APP_VERSION const"),
    (r'''data-i18n="tag"''', "tag attribute"),
]


def patch_file(path):
    with open(path, "rb") as fp:
        raw = fp.read()
    content = raw.decode("utf-8")
    orig = content

    # Pre-validate every OLD anchor is present exactly once (no drift)
    for old, _new in REWRITES:
        n = content.count(old)
        if n != 1:
            print(f"ABORT: anchor missing/wrong count in {os.path.basename(path)}")
            print(f"  count={n}  old_first20={old[:20]!r}  old_last40={old[-40:]!r}")
            return False

    # Apply all 12 swaps in declared order (most-specific first)
    for old, new in REWRITES:
        content = content.replace(old, new, 1)

    # Post-validate: every OLD now == 0, every NEW == 1
    for old, _new in REWRITES:
        if content.count(old) != 0:
            print(f"ABORT: OLD anchor still present after replace in {os.path.basename(path)}")
            print(f"  old_first20={old[:20]!r}")
            return False
    for _old, new in REWRITES:
        if content.count(new) != 1:
            print(f"ABORT: NEW anchor missing/wrong count in {os.path.basename(path)}")
            print(f"  count={content.count(new)}  new_first20={new[:20]!r}  new_last40={new[-40:]!r}")
            return False

    # Sentinel check — must NOT have changed counts vs original
    for sentinel, label in SENTINELS:
        o = orig.count(sentinel)
        n = content.count(sentinel)
        if o != n:
            print(f"ABORT: sentinel drift in {os.path.basename(path)}: {label}")
            print(f"  orig={o}  now={n}")
            return False

    # Write back byte-identical except for the swaps
    with open(path, "wb") as fp:
        fp.write(content.encode("utf-8"))

    print(f"OK [{os.path.basename(path)}] 12 swaps applied, sentinels preserved")
    return True


def main():
    ok = True
    for f in FILES:
        if not patch_file(f):
            ok = False
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
