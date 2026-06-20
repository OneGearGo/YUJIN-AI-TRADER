# -*- coding: utf-8 -*-
"""
Round-27 verifier — counts anchors + sentinels in a file.

Usage:
  python _r27_verify.py file1 [file2 ...]

Prints a per-file PASS/FAIL table:
  - 12 OLD anchors must be count 0  (round-27 intent: removed)
  - 12 NEW anchors must be count 1  (round-27 intent: present)
  - sentinels must be present and unchanged (demobar/tag/round-26 entries)
"""

import sys

# (anchor, expect_min, expect_max, label)
CHECKS = [
    # ── 12 OLD ── expected 0
    ("detail_passed:(pri,size,warn)=>`通过全部闸门 · 优先级 ${pri} · 仓位由代码算 ${size} SOL",         0, 0, "zh detail_passed"),
    ("log_screen_reason:(size,pri)=>`通过闸门 · 待决策 · 建议 ${size} SOL · 优先级",                   0, 0, "zh log_screen_reason"),
    ("kpi_sub_expo:(e)=>`敞口 ${e} SOL",                                                            0, 0, "zh kpi_sub_expo"),
    ("toast_buy:(live,sym,size)=>`${live?'已真实下单 ':'已记录(SHADOW) '}${sym} ${size} SOL",          0, 0, "zh toast_buy"),
    ("toast_buy_demo:(live,sym,size)=>`${live?'已真实下单 ':'已记录(SHADOW) '}${sym} ${size} SOL · 已加入逃生监控", 0, 0, "zh toast_buy_demo"),
    ("buy_log_reason:(live,size,exit)=>`${live?'LIVE 真实成交 ':'SHADOW 记录 '}${size} SOL · ${exit}", 0, 0, "zh buy_log_reason"),
    ("detail_passed:(pri,size,warn)=>`Passed all gates · priority ${pri} · size computed ${size} SOL", 0, 0, "en detail_passed"),
    ("log_screen_reason:(size,pri)=>`passed gates · pending · suggest ${size} SOL · priority ${pri}", 0, 0, "en log_screen_reason"),
    ("kpi_sub_expo:(e)=>`exposure ${e} SOL",                                                          0, 0, "en kpi_sub_expo"),
    ("toast_buy:(live,sym,size)=>`${live?'Order placed ':'Recorded (SHADOW) '}${sym} ${size} SOL",     0, 0, "en toast_buy"),
    ("toast_buy_demo:(live,sym,size)=>`${live?'Order placed ':'Recorded (SHADOW) '}${sym} ${size} SOL · added to escape monitor", 0, 0, "en toast_buy_demo"),
    ("buy_log_reason:(live,size,exit)=>`${live?'LIVE filled ':'SHADOW logged '}${size} SOL · ${exit}", 0, 0, "en buy_log_reason"),
    # ── 12 NEW ── expected 1
    ("[Audit:0xa01] 通过全部闸门 · 优先级 ${pri} · 仓位由代码算 ${size} [Unit:0xa11]${warn?' · ⚠ 买入将触及风控上限':''}`", 1, 1, "zh detail_passed NEW"),
    ("[Audit:0xa02] 通过闸门 · 待决策 · 建议 ${size} [Unit:0xa11] · 优先级${pri}`",                     1, 1, "zh log_screen_reason NEW"),
    ("[Expo:0xb03] 敞口 ${e} [Unit:0xa11]`",                                                            1, 1, "zh kpi_sub_expo NEW"),
    ("[Wire:0xd05] 已记录(SHADOW) '${sym} ${size} [Unit:0xa11]`,",                                       1, 1, "zh toast_buy SHADOW branch NEW"),
    ("[Wire:0xd04] 已真实下单 '${sym} ${size} [Unit:0xa11]`,",                                           1, 1, "zh toast_buy LIVE branch NEW"),
    ("[Monitor:0xe06] 已加入逃生监控`",                                                                  1, 1, "zh toast_buy_demo monitor NEW"),
    ("LIVE filled '${size} [Unit:0xa11] · ${exit}",                                                     1, 1, "en buy_log_reason LIVE branch NEW"),
    ("SHADOW logged '${size} [Unit:0xa11] · ${exit}",                                                   1, 1, "en buy_log_reason SHADOW branch NEW"),
    ("[Audit:0xa01] Passed all gates · priority ${pri} · size computed ${size} [Unit:0xa11]${warn?' · ⚠ buy will hit the risk cap':''}`", 1, 1, "en detail_passed NEW"),
    ("[Audit:0xa02] passed gates · pending · suggest ${size} [Unit:0xa11] · priority ${pri}`",          1, 1, "en log_screen_reason NEW"),
    ("[Expo:0xb03] exposure ${e} [Unit:0xa11]`",                                                          1, 1, "en kpi_sub_expo NEW"),
    ("[Wire:0xd04] Order placed '${sym} ${size} [Unit:0xa11]`,",                                          1, 1, "en toast_buy LIVE branch NEW"),
    ("[Wire:0xd05] Recorded (SHADOW) '${sym} ${size} [Unit:0xa11]`,",                                     1, 1, "en toast_buy SHADOW branch NEW"),
    ("[Monitor:0xe06] added to escape monitor`",                                                          1, 1, "en toast_buy_demo monitor NEW"),
    # ── sentinels ── (presence, floor)
    ("自配经销商和自营商账户信息", 0, 100, "demobar zh (Round-19)"),
    ("Self-provided broker", 0, 100, "demobar en (Round-19)"),
    ("你按下成交 ➡️ 人机协同 / 一锤定音 / 闭环收口 / 最终授权 / 拍板转化", 1, 100, "tag zh (Round-23)"),
    ("品种覆盖外汇 + 黄金 + 主要指数", 1, 100, "r26 publicbar zh"),
    ("Live mock data · read-only demo", 1, 100, "r26 publicbar en"),
    ("不上账户（当前锁定", 1, 100, "r26 mode_tip zh"),
    ("paper-trade (locked", 1, 100, "r26 mode_tip en"),
    ("经API密钥真实下单", 1, 100, "r26 cfg_mwarn zh"),
    ("API key into the wire", 1, 100, "r26 cfg_mwarn en"),
    ("APP_VERSION='v0.0.1'", 1, 100, "APP_VERSION const"),
    ("[Hash:0xa3c]", 1, 100, "r26 sig_top10sell cipher"),
    ("[Codepath:0xff1]", 1, 100, "r26 inj_tip cipher"),
    ("[Gate:0x4a2]", 1, 100, "r26 gatetip3 cipher"),
]


def verify(path):
    with open(path, "rb") as fp:
        content = fp.read().decode("utf-8", errors="replace")
    print(f"\n=== {path} ===")
    fail = 0
    passes = 0
    rows = []
    for anchor, lo, hi, label in CHECKS:
        n = content.count(anchor)
        ok = lo <= n <= hi
        status = "OK " if ok else "FAIL"
        rows.append((label, n, lo, hi, status))
        if ok: passes += 1
        else:   fail += 1
    # Print table
    print(f"  {'label':50s}{'count':>6s}{'lo':>4s}{'hi':>4s}  status")
    print(f"  {'-'*50}{'-'*6}{'-'*4}{'-'*4}  ------")
    for lab, n, lo, hi, st in rows:
        print(f"  {lab:50s}{n:>6d}{lo:>4d}{hi:>4d}  {st}")
    print(f"  PASS={passes}  FAIL={fail}")
    return fail == 0


def main():
    if len(sys.argv) < 2:
        print("usage: python _r27_verify.py file [file ...]")
        sys.exit(2)
    ok = True
    for p in sys.argv[1:]:
        if not verify(p):
            ok = False
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
