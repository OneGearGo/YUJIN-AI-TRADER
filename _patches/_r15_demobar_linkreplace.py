# -*- coding: utf-8 -*-
"""Round-15: replace #demoBar zh+en I18N literals verbatim per user's spec.
User's literal text (no <b>, no extra formatting):
  \u26a0 \u6f14\u793a\u6a21\u5f0f \u00b7 \u793a\u4f8b\u6570\u636e\uff0c\u975e\u5b98\u65b9\u4ea4\u6613\u529f\u80fd\uff0c\u4e0d\u6784\u6210\u6295\u8d44\u5efa\u8bae \u00b7 \u60f3\u63a5\u771f\u5b9e\u6570\u636e\uff0c\u8bf7 clone \u6e90\u7801\u672c\u5730\u8fd0\u884c\uff08\u81ea\u914d\u7ecf\u9500\u5546\u6216\u81ea\u8425\u4e0a\u8d26\u6237\u4fe1\u606f\uff0c\u4e70\u5356\u4ec5\u5728\u4f60\u672c\u673a\u6267\u884c\uff09 \u00b7 \u67e5\u770b\u6e90\u4ee3\u7801 \u2197

\u201c\u67e5\u770b\u6e90\u4ee3\u7801 \u2197\u201d wraps in <a href="https://github.com/OneGearGo/YUJIN-AI-TRADER" target="_blank" rel="noopener">.

No <b> tags. No style attributes. Plain literal with link wrap.

Literal-anchor find/replace (no regex); each anchor hits 1x or aborts.
"""

import codecs

ROOT = r"F:\yujin-mt5"

# ---- Anchors CURRENTLY in source (from basher diag) ----

OLD_ZH_LITERAL = (
    "demobar:'\u26a0 <b>\u6f14\u793a\u6a21\u5f0f</b> \u00b7 \u793a\u4f8b\u6570\u636e\uff0c"
    "<b>\u975e GMGN \u5b98\u65b9\u4ea4\u6613\u529f\u80fd\uff0c\u4e0d\u6784\u6210\u6295\u8d44\u5efa\u8bae</b> "
    "\u00b7 \u60f3\u63a5\u771f\u5b9e\u94fe\u4e0a\u6570\u636e\uff0c\u8bf7 clone \u6e90\u7801\u672c\u5730\u8fd0\u884c"
    "\uff08\u81ea\u914d API Key\uff0c\u4e70\u5356\u4ec5\u5728\u4f60\u672c\u673a\u6267\u884c\uff09 "
    "\u00b7 "
    '<a href="https://github.com/GMGNAI/skillmarket-demos/tree/main/aitrader" '
    'target="_blank" rel="noopener" style="color:var(--lime);font-weight:600">'
    "\u67e5\u770b\u6e90\u4ee3\u7801 \u2197</a>',"
)
NEW_ZH_LITERAL = (
    "demobar:'\u26a0 \u6f14\u793a\u6a21\u5f0f \u00b7 \u793a\u4f8b\u6570\u636e\uff0c"
    "\u975e\u5b98\u65b9\u4ea4\u6613\u529f\u80fd\uff0c\u4e0d\u6784\u6210\u6295\u8d44\u5efa\u8bae "
    "\u00b7 \u60f3\u63a5\u771f\u5b9e\u6570\u636e\uff0c\u8bf7 clone \u6e90\u7801\u672c\u5730\u8fd0\u884c"
    "\uff08\u81ea\u914d\u7ecf\u9500\u5546\u6216\u81ea\u8425\u4e0a\u8d26\u6237\u4fe1\u606f\uff0c\u4e70\u5356\u4ec5\u5728\u4f60\u672c\u673a\u6267\u884c\uff09 "
    "\u00b7 "
    '<a href="https://github.com/OneGearGo/YUJIN-AI-TRADER" '
    'target="_blank" rel="noopener">'
    "\u67e5\u770b\u6e90\u4ee3\u7801 \u2197</a>',"
)

OLD_EN_LITERAL = (
    "demobar:'\u26a0 <b>Demo Mode</b> \u00b7 sample data, "
    "<b>not an official GMGN trading feature, not investment advice</b> "
    "\u00b7 for real on-chain data, clone the source and run locally "
    "(your own API key; trades execute only on your machine) "
    "\u00b7 "
    '<a href="https://github.com/GMGNAI/skillmarket-demos/blob/main/aitrader/README.en.md" '
    'target="_blank" rel="noopener" style="color:var(--lime);font-weight:600">'
    "View source \u2197</a>',"
)
NEW_EN_LITERAL = (
    "demobar:'\u26a0 Demo Mode \u00b7 sample data, "
    "not an official trading function, not investment advice "
    "\u00b7 for real data, clone the source and run locally "
    "(your broker or own-up account info; trades execute only on your machine) "
    "\u00b7 "
    '<a href="https://github.com/OneGearGo/YUJIN-AI-TRADER" '
    'target="_blank" rel="noopener">'
    "View source \u2197</a>',"
)

REPLACEMENTS = {
    r"F:\yujin-mt5\static\index.html": [
        (OLD_ZH_LITERAL, NEW_ZH_LITERAL),
        (OLD_EN_LITERAL, NEW_EN_LITERAL),
    ],
    r"F:\yujin-mt5\docs\index.html": [
        (OLD_ZH_LITERAL, NEW_ZH_LITERAL),
        (OLD_EN_LITERAL, NEW_EN_LITERAL),
    ],
}


def main():
    for path, repls in REPLACEMENTS.items():
        text = codecs.open(path, "r", encoding="utf-8").read()
        for old, new in repls:
            cnt = text.count(old)
            if cnt != 1:
                print(
                    f"[ABORT] {path}: anchor hit {cnt}x (expected 1); "
                    f"anchor head: {old[:60]!r}",
                    flush=True,
                )
                return 2
            text = text.replace(old, new)
        codecs.open(path, "w", encoding="utf-8").write(text)
        n_zh = text.count(NEW_ZH_LITERAL)
        n_en = text.count(NEW_EN_LITERAL)
        n_old = (
            text.count("GMGN \u5b98\u65b9\u4ea4\u6613\u529f\u80fd")
            + text.count("not an official GMGN trading feature")
            + text.count("GMGNAI/skillmarket-demos")
        )
        print(
            f"[ok] {path}: rewrote {len(repls)} anchors;"
            f" NEW_ZH_count={n_zh}; NEW_EN_count={n_en};"
            f" old_text_remaining={n_old}",
            flush=True,
        )
    print(
        "[done] Round-15: demobar text per user spec, link to OneGearGo/YUJIN-AI-TRADER",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
