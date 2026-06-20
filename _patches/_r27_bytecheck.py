# -*- coding: utf-8 -*-
"""Round-27 bytecheck: probe namespace anchor regions in static/index.html
AND _r27_diag.py AND _r27_livelog_cipher.py. Dump 200 bytes of context per region.

Run as: python _r27_bytecheck.py
Output: ASCII table at /c/Users/Administrator/Desktop/_r27_bytecheck.txt
"""
import os, re, sys

PROBE_REGIONS = [
    ('zh detail_passed',    b'detail_passed:(pri,size,warn)=>`'),
    ('zh log_screen_reason',b'log_screen_reason:(size,pri)=>`'),
    ('zh kpi_sub_expo',     b'kpi_sub_expo:(e)=>`'),
    ('zh toast_buy_demo',   b'toast_buy_demo:(live,sym,size)=>`'),
    ('zh toast_buy',        b'toast_buy:(live,sym,size)=>`'),
    ('zh buy_log_reason',   b'buy_log_reason:(live,size,exit)=>`'),
    ('en detail_passed',    b'detail_passed:(pri,size,warn)=>`Passed'),
    ('en log_screen_reason',b'log_screen_reason:(size,pri)=>`passed'),
    ('en kpi_sub_expo',     b'kpi_sub_expo:(e)=>`exposure'),
    ('en toast_buy_demo',   b'toast_buy_demo:(live,sym,size)=>`'),
    ('en toast_buy',        b'toast_buy:(live,sym,size)=>`'),
    ('en buy_log_reason',   b'buy_log_reason:(live,size,exit)=>`'),
]

FILES = [
    '/f/yujin-mt5/static/index.html',
    '/f/yujin-mt5/docs/index.html',
    '/c/Users/Administrator/Desktop/_r27_diag.py',
    '/c/Users/Administrator/Desktop/_r27_livelog_cipher.py',
]

OUT_PATH = 'C:\\Users\\Administrator\\Desktop\\_r27_bytecheck.txt'

def main():
    out_lines = []
    out_lines.append("=" * 80)
    out_lines.append("Round-27 bytecheck — find anchor namespaces in 4 files, dump raw bytes")
    out_lines.append("=" * 80)

    for f in FILES:
        if not os.path.exists(f):
            out_lines.append(f"\n[NOT FOUND] {f}")
            continue
        with open(f, 'rb') as fp:
            data = fp.read()
        out_lines.append(f"\n=== {f}  size={len(data)} ===")
        for label, probe in PROBE_REGIONS:
            idx = data.find(probe)
            if idx == -1:
                out_lines.append(f"  [MISS] {label}  probe={probe!r}")
                continue
            chunk = data[idx:idx+220]
            out_lines.append(f"  [HIT  ] {label} @ byte {idx}")
            out_lines.append(f"    bytes_repr: {chunk!r}")
            safe = ''.join((chr(b) if (32 <= b < 127 and b not in (10, 13)) else
                            (f'\\r' if b == 13 else (f'\\n' if b == 10 else f'\\x{b:02x}')))
                           for b in chunk)
            out_lines.append(f"    ascii_safe: {safe}")
            out_lines.append("    " + "-" * 60)

    out_lines.append("=" * 80)
    out_lines.append("PYTHON LITERAL ANCHOR SPECIMENS (from _r27_diag.py source)")
    out_lines.append("=" * 80)
    try:
        with open('C:\\Users\\Administrator\\Desktop\\_r27_diag.py', 'rb') as fp:
            src = fp.read()
        # Look for `r"""` and end with `"""`
        for m in re.finditer(rb'r"""([^"\\]{0,400})', src):
            content = m.group(1)
            if any(kw in content for kw in (b'detail_passed', b'log_screen_reason',
                                            b'kpi_sub_expo', b'toast_buy',
                                            b'buy_log_reason')):
                out_lines.append(f"  specimen bytes_repr: {content!r}")
                safe = ''.join(chr(b) if 32 <= b < 127 else f'\\x{b:02x}' for b in content)
                out_lines.append(f"  specimen ascii_safe: {safe}")
                out_lines.append("  " + "-" * 60)
    except Exception as e:
        out_lines.append(f"  [ERR reading python source]: {e!r}")

    out = '\n'.join(out_lines)
    with open(OUT_PATH, 'w', encoding='utf-8') as fp:
        fp.write(out)
    print(f"WROTE {OUT_PATH}  bytes={len(out)}")
    print(out[:3000])


if __name__ == "__main__":
    main()
