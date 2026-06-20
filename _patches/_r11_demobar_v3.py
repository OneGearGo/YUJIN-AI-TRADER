# -*- coding: utf-8 -*-
"""Round-11 demobar v3: replace Round-10 paraphrase with user's VERBATIM text.

User's exact text (no <b>, no italics, no translation fantasy):
  "\u26a0 \u6f14\u793a\u6a21\u5f0f \u00b7 \u793a\u4f8b\u6570\u636e\uff0c\u975e GMGN
   \u5b98\u65b9\u4ea4\u6613\u529f\u80fd\uff0c\u4e0d\u6784\u6210\u6295\u8d44\u5efa\u8bae
   \u00b7 \u60f3\u63a5\u771f\u5b9e\u94fe\u4e0a\u6570\u636e\uff0c\u8bf7 clone \u6e90\u7801
   \u672c\u5730\u8fd0\u884c\uff08\u81ea\u914d API Key\uff0c\u4e70\u5356\u4ec5\u5728\u4f60\u672c\u673a
   \u6267\u884c\uff09 \u00b7 \u67e5\u770b\u6e90\u4ee3\u7801 \u2197"

Round-10 text being REPLACED (subtle differences: 'GMGN' missing,
'real\u94fe\u4e0a' over 'real', 'API Key' over '\u7ecf\u9500\u5546\u767b\u5165\u4fe1\u606f'):
  "\u26a0 <b>\u6f14\u793a\u6a21\u5f0f</b> \u00b7 \u793a\u4f8b\u6570\u636e\uff0c\u975e\u5b98\u65b9
   \u4ea4\u6613\u529f\u80fd\uff0c\u4e0d\u6784\u6210\u6295\u8d44\u5efa\u8bae \u00b7 \u60f3\u63a5\u771f\u5b9e
   \u6570\u636e\uff0c\u8bf7 clone \u6e90\u7801\u672c\u5730\u8fd0\u884c\uff08\u81ea\u914d\u7ecf\u9500\u5546
   \u767b\u5165\u4fe1\u606f\uff0c\u4e70\u5356\u4ec5\u5728\u4f60\u672c\u673a\u6267\u884c\uff09
   \u00b7 \u67e5\u770b\u6e90\u4ee3\u7801 \u2197"

Replacement strategy: literal-anchor str.replace (no regex). Each old anchor
must appear EXACTLY ONCE in target file or patch aborts without writes.
"""

import codecs

ROOT = r"F:\yujin-mt5"

# User-verbatim text — 1:1 character match
USER_TEXT = (
    "\u26a0 \u6f14\u793a\u6a21\u5f0f \u00b7 \u793a\u4f8b\u6570\u636e\uff0c"
    "\u975e GMGN \u5b98\u65b9\u4ea4\u6613\u529f\u80fd\uff0c\u4e0d\u6784\u6210\u6295\u8d44\u5efa\u8bae "
    "\u00b7 \u60f3\u63a5\u771f\u5b9e\u94fe\u4e0a\u6570\u636e\uff0c\u8bf7 clone \u6e90\u7801\u672c\u5730\u8fd0\u884c"
    "\uff08\u81ea\u914d API Key\uff0c\u4e70\u5356\u4ec5\u5728\u4f60\u672c\u673a\u6267\u884c\uff09 "
    "\u00b7 \u67e5\u770b\u6e90\u4ee3\u7801 \u2197"
)

# Anchors CURRENTLY IN FILES (Round-10 wording) — each must appear EXACTLY ONCE
ANCHOR_HTML_ELEMENT = (
    '<div class="demobar" id="demoBar" data-i18n="demobar">'
    "\u26a0 <b>\u6f14\u793a\u6a21\u5f0f</b> \u00b7 \u793a\u4f8b\u6570\u636e\uff0c"
    "\u975e\u5b98\u65b9\u4ea4\u6613\u529f\u80fd\uff0c\u4e0d\u6784\u6210\u6295\u8d44\u5efa\u8bae "
    "\u00b7 \u60f3\u63a5\u771f\u5b9e\u6570\u636e\uff0c\u8bf7 clone \u6e90\u7801\u672c\u5730\u8fd0\u884c"
    "\uff08\u81ea\u914d\u7ecf\u9500\u5546\u767b\u5165\u4fe1\u606f\uff0c\u4e70\u5356\u4ec5\u5728\u4f60\u672c\u673a\u6267\u884c\uff09 "
    "\u00b7 \u67e5\u770b\u6e90\u4ee3\u7801 \u2197"
    "</div>"
)
ANCHOR_HTML_NEW = (
    '<div class="demobar" id="demoBar" data-i18n="demobar">'
    + USER_TEXT
    + "</div>"
)

ANCHOR_I18N_ZH_DEMOBAR = (
    "demobar:'\u26a0 <b>\u6f14\u793a\u6a21\u5f0f</b> \u00b7 \u793a\u4f8b\u6570\u636e\uff0c"
    "\u975e\u5b98\u65b9\u4ea4\u6613\u529f\u80fd\uff0c\u4e0d\u6784\u6210\u6295\u8d44\u5efa\u8bae "
    "\u00b7 \u60f3\u63a5\u771f\u5b9e\u6570\u636e\uff0c\u8bf7 clone \u6e90\u7801\u672c\u5730\u8fd0\u884c"
    "\uff08\u81ea\u914d\u7ecf\u9500\u5546\u767b\u5165\u4fe1\u606f\uff0c\u4e70\u5356\u4ec5\u5728\u4f60\u672c\u673a\u6267\u884c\uff09 "
    "\u00b7 \u67e5\u770b\u6e90\u4ee3\u7801 \u2197,"
)
ANCHOR_I18N_ZH_DEMOBAR_NEW = "demobar:'" + USER_TEXT + ",'"

ANCHOR_I18N_EN_DEMOBAR = (
    "demobar:'\u26a0 <b>Demo mode</b> \u00b7 Sample data \u2014 not an official "
    "trading function, not investment advice \u00b7 To use real data, clone the "
    "source locally and run (configure your broker login yourself; trades "
    "execute only on your machine) \u00b7 View source \u2197,"
)
ANCHOR_I18N_EN_DEMOBAR_NEW = "demobar:'" + USER_TEXT + ",'"

REPLACEMENTS = {
    r"F:\yujin-mt5\static\index.html": [
        (ANCHOR_HTML_ELEMENT, ANCHOR_HTML_NEW),
        (ANCHOR_I18N_ZH_DEMOBAR, ANCHOR_I18N_ZH_DEMOBAR_NEW),
        (ANCHOR_I18N_EN_DEMOBAR, ANCHOR_I18N_EN_DEMOBAR_NEW),
    ],
    r"F:\yujin-mt5\docs\index.html": [
        # docs #demoBar HTML element is empty; do not touch.
        (ANCHOR_I18N_ZH_DEMOBAR, ANCHOR_I18N_ZH_DEMOBAR_NEW),
        (ANCHOR_I18N_EN_DEMOBAR, ANCHOR_I18N_EN_DEMOBAR_NEW),
    ],
}


def main():
    for path, repls in REPLACEMENTS.items():
        text = codecs.open(path, "r", encoding="utf-8").read()
        for old, new in repls:
            cnt = text.count(old)
            if cnt != 1:
                print(
                    f"  [ABORT] {path}: anchor hit {cnt}x (expected 1\n"
                    f"           anchor head: {old[:80]!r}",
                    flush=True,
                )
                return 2
            text = text.replace(old, new)
        codecs.open(path, "w", encoding="utf-8").write(text)
        # post-write verify
        n_user = text.count(USER_TEXT)
        n_old_b = text.count("<b>\u6f14\u793a\u6a21\u5f0f</b>")
        n_old_en = text.count("<b>Demo mode</b>")
        print(
            f"[ok] {path}: rewrote {len(repls)} anchors;"
            f" USER_TEXT_in_file={n_user};"
            f" leftover_old_zh={n_old_b};"
            f" leftover_old_en={n_old_en}",
            flush=True,
        )
    print("[done] Round-11 demobar v3 applied (user verbatim)", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
