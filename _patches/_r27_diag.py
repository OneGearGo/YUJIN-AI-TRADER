# -*- coding: utf-8 -*-
"""
Round-27 drift diagnostic: count occurrences of each OLD anchor substring
in the given file. Run as:
    python _r27_diag.py file1 [file2 ...]
"""

import sys

# These mirror the patcher's REWRITES list, OLD side only.
# If count == 0: anchor absent (drift!)
# If count > 1: multiple match (collision or missing uniqueness)
# If count == 1: exact 1-in-1-out replace possible
ANCHORS = [
    # zh
    ("zh detail_passed",
     r"""detail_passed:(pri,size,warn)=>`通过全部闸门 · 优先级 ${pri} · 仓位由代码算 ${size} SOL${warn?' · ⚠ 买入将触及风控上限':''}`, """),
    ("zh log_screen_reason",
     r"""log_screen_reason:(size,pri)=>`通过闸门 · 待决策 · 建议 ${size} SOL · 优先级${pri}`, """),
    ("zh kpi_sub_expo",
     r""", kpi_sub_expo:(e)=>`敞口 ${e} SOL`, """),
    ("zh toast_buy",
     r"""toast_buy:(live,sym,size)=>`${live?'已真实下单 ':'已记录(SHADOW) '}${sym} ${size} SOL`, """),
    ("zh toast_buy_demo",
     r"""toast_buy_demo:(live,sym,size)=>`${live?'已真实下单 ':'已记录(SHADOW) '}${sym} ${size} SOL · 已加入逃生监控`, """),
    ("zh buy_log_reason",
     r"""buy_log_reason:(live,size,exit)=>`${live?'LIVE 真实成交 ':'SHADOW 记录 '}${size} SOL · ${exit}`, """),
    # en
    ("en detail_passed",
     r"""detail_passed:(pri,size,warn)=>`Passed all gates · priority ${pri} · size computed ${size} SOL${warn?' · ⚠ buy will hit the risk cap':''}`, """),
    ("en log_screen_reason",
     r"""log_screen_reason:(size,pri)=>`passed gates · pending · suggest ${size} SOL · priority ${pri}`, """),
    ("en kpi_sub_expo",
     r""", kpi_sub_expo:(e)=>`exposure ${e} SOL`, """),
    ("en toast_buy",
     r"""toast_buy:(live,sym,size)=>`${live?'Order placed ':'Recorded (SHADOW) '}${sym} ${size} SOL`, """),
    ("en toast_buy_demo",
     r"""toast_buy_demo:(live,sym,size)=>`${live?'Order placed ':'Recorded (SHADOW) '}${sym} ${size} SOL · added to escape monitor`, """),
    ("en buy_log_reason",
     r"""buy_log_reason:(live,size,exit)=>`${live?'LIVE filled ':'SHADOW logged '}${size} SOL · ${exit}`, """),
]


def diag_file(path):
    with open(path, "rb") as fp:
        content = fp.read().decode("utf-8", errors="replace")
    print(f"\n=== {path} ===")
    for label, anchor in ANCHORS:
        n = content.count(anchor)
        flag = " MATCH" if n == 1 else (" ABSENT" if n == 0 else f" DUPLICATE×{n}")
        print(f"  [{n:>3d}]{flag}  {label}")


def main():
    if len(sys.argv) < 2:
        print("usage: python _r27_diag.py file [file ...]")
        sys.exit(2)
    for p in sys.argv[1:]:
        diag_file(p)


if __name__ == "__main__":
    main()
