# -*- coding: utf-8 -*-
"""Round-10 demobar restore: replace demoBar text + I18N.zh/en.demobar with
user-provided wording. Literal-anchor find/replace (no regex on HTML body)."""

import codecs

ROOT = r"F:\yujin-mt5"

# User-provided Chinese text (with <b> preserved around the key phrase)
NEW_ZH = (
    "\u26a0 <b>\u6f14\u793a\u6a21\u5f0f</b> \u00b7 \u793a\u4f8b\u6570\u636e\uff0c"
    "\u975e\u5b98\u65b9\u4ea4\u6613\u529f\u80fd\uff0c\u4e0d\u6784\u6210\u6295\u8d44\u5efa\u8bae "
    "\u00b7 \u60f3\u63a5\u771f\u5b9e\u6570\u636e\uff0c\u8bf7 clone \u6e90\u7801\u672c\u5730\u8fd0\u884c"
    "\uff08\u81ea\u914d\u7ecf\u9500\u5546\u767b\u5165\u4fe1\u606f\uff0c\u4e70\u5356\u4ec5\u5728\u4f60\u672c\u673a\u6267\u884c\uff09 "
    "\u00b7 \u67e5\u770b\u6e90\u4ee3\u7801 \u2197"
)
# Faithful English translation
NEW_EN = (
    "\u26a0 <b>Demo mode</b> \u00b7 Sample data \u2014 not an official trading "
    "function, not investment advice \u00b7 To use real data, clone the source "
    "locally and run (configure your broker login yourself; trades execute "
    "only on your machine) \u00b7 View source \u2197"
)

# Anchors (each must appear EXACTLY ONCE in the target file).
REPLACEMENTS = {
    r"F:\yujin-mt5\static\index.html": [
        # HTML element (single-line, starts after >, ends before </div>)
        (
            '<div class="demobar" id="demoBar" data-i18n="demobar">'
            "\u26a0 <b>\u6f14\u793a\u6570\u636e</b> \u00b7 \u4ec5\u4f5c MT5 thin-proxy "
            "\u6280\u672f\u6f14\u793a\uff0c\u975e\u4ea4\u6613\u7cfb\u7edf\u3001\u65e0\u4efb\u4f55\u6295\u8d44\u5efa\u8bae "
            "\u00b7 \u771f\u5b9e\u63a5\u5165\u8bf7 clone \u4ed3\u5e93\u5230\u672c\u5730\u3001"
            "\u81ea\u914d\u7ecf\u7eaa\u5546\u8d26\u6237\uff0c\u6240\u6709\u4e0b\u5355\u4ec5\u5728\u4f60\u672c\u673a\u6267\u884c"
            "</div>",
            '<div class="demobar" id="demoBar" data-i18n="demobar">' + NEW_ZH + "</div>",
        ),
        # I18N.zh.demobar literal (zh dict)
        (
            "demobar:'\u26a0 <b>\u6f14\u793a\u6570\u636e</b> \u00b7 \u4ec5\u4f5c MT5 thin-proxy "
            "\u6280\u672f\u6f14\u793a\uff0c\u975e\u4ea4\u6613\u7cfb\u7edf\u3001\u65e0\u4efb\u4f55\u6295\u8d44\u5efa\u8bae "
            "\u00b7 \u771f\u5b9e\u63a5\u5165\u8bf7 clone \u4ed3\u5e93\u5230\u672c\u5730\u3001"
            "\u81ea\u914d\u7ecf\u7eaa\u5546\u8d26\u6237\uff0c\u6240\u6709\u4e0b\u5355\u4ec5\u5728\u4f60\u672c\u673a\u6267\u884c,",
            "demobar:'" + NEW_ZH + ",'",
        ),
        # I18N.en.demobar literal (en dict)
        (
            "demobar:'\u26a0 <b>Demo data</b> \u00b7 MT5 thin-proxy technical demo "
            "only, not a trading system, no investment advice \u00b7 For real usage: "
            "clone the repo locally, configure your own broker account, all orders "
            "execute only on your machine,",
            "demobar:'" + NEW_EN + ",'",
        ),
    ],
    r"F:\yujin-mt5\docs\index.html": [
        # docs has empty <div id="demoBar"> -- skip; only patch dict literals.
        # I18N.zh.demobar literal (zh dict)
        (
            "demobar:'\u26a0 <b>\u6f14\u793a\u6570\u636e</b> \u00b7 \u4ec5\u4f5c MT5 thin-proxy "
            "\u6280\u672f\u6f14\u793a\uff0c\u975e\u4ea4\u6613\u7cfb\u7edf\u3001\u65e0\u4efb\u4f55\u6295\u8d44\u5efa\u8bae "
            "\u00b7 \u771f\u5b9e\u63a5\u5165\u8bf7 clone \u4ed3\u5e93\u5230\u672c\u5730\u3001"
            "\u81ea\u914d\u7ecf\u7eaa\u5546\u8d26\u6237\uff0c\u6240\u6709\u4e0b\u5355\u4ec5\u5728\u4f60\u672c\u673a\u6267\u884c,",
            "demobar:'" + NEW_ZH + ",'",
        ),
        # I18N.en.demobar literal (en dict)
        (
            "demobar:'\u26a0 <b>Demo data</b> \u00b7 MT5 thin-proxy technical demo "
            "only, not a trading system, no investment advice \u00b7 For real usage: "
            "clone the repo locally, configure your own broker account, all orders "
            "execute only on your machine,",
            "demobar:'" + NEW_EN + ",'",
        ),
    ],
}


def main():
    for path, repls in REPLACEMENTS.items():
        text = codecs.open(path, "r", encoding="utf-8").read()
        for old, new in repls:
            cnt = text.count(old)
            if cnt != 1:
                print(
                    f"  [warn] {path}: anchor found {cnt}x (expected 1)\n"
                    f"         anchor head: {old[:60]!r}",
                    flush=True,
                )
                return 1
            text = text.replace(old, new)
        codecs.open(path, "w", encoding="utf-8").write(text)
        # verify post-write
        post = codecs.open(path, "r", encoding="utf-8").read()
        n_new_zh = post.count(NEW_ZH)
        n_new_en = post.count(NEW_EN)
        n_old = post.count(
            "\u26a0 <b>\u6f14\u793a\u6570\u636e</b> \u00b7 \u4ec5\u4f5c MT5"
        )
        print(
            f"[ok] {path}: rewrote {len(repls)} anchors;"
            f" NEW_ZH_count={n_new_zh}; NEW_EN_count={n_new_en};"
            f" old_text_remaining={n_old}",
            flush=True,
        )
    print("[done] demobar restored", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
