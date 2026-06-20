#!/usr/bin/env python3
# Round-19: Restore reference markup wrappers (b + a style) in zh & en demobar literals.
# Goal: demobar visual on our https://onegeargo.github.io/YUJIN-AI-TRADER/
#       matches reference https://gmgnai.github.io/skillmarket-demos/aitrader/ exactly.
#
# Permission: user explicitly asked to match reference colors in this turn.
# Scope: ONLY add <b>...</b> wrappers around the same phrases reference wraps
#        AND re-attach the inline lime-bold style on the <a> link tag.
# No other texts, no CSS, no HTML element changes outside the I18N literals.

import pathlib

files = [
    pathlib.Path('static/index.html'),
    pathlib.Path('docs/index.html'),
]

# ZH — current state on disk after Round-18 phrase change
OLD_ZH = ('\u26a0 \u6f14\u793a\u6a21\u5f0f \u00b7 \u793a\u4f8b\u6570\u636e\uff0c'
          '\u975e\u5b98\u65b9\u4ea4\u6613\u529f\u80fd\uff0c\u4e0d\u6784\u6210\u6295\u8d44\u5efa\u8bae '
          '\u00b7 \u60f3\u63a5\u771f\u5b9e\u6570\u636e\uff0c'
          '\u8bf7 clone \u6e90\u7801\u672c\u5730\u8fd0\u884c\uff08'
          '\u81ea\u914d\u7ecf\u9500\u5546\u548c\u81ea\u8425\u5546\u8d26\u6237\u4fe1\u606f\uff0c'
          '\u4e70\u5356\u4ec5\u5728\u4f60\u672c\u673a\u6267\u884c\uff09 \u00b7 '
          '<a href="https://github.com/OneGearGo/YUJIN-AI-TRADER" '
          'target="_blank" rel="noopener">\u67e5\u770b\u6e90\u4ee3\u7801 \u2197</a>')

NEW_ZH = ('\u26a0 <b>\u6f14\u793a\u6a21\u5f0f</b> \u00b7 \u793a\u4f8b\u6570\u636e\uff0c'
          '<b>\u975e\u5b98\u65b9\u4ea4\u6613\u529f\u80fd\uff0c\u4e0d\u6784\u6210\u6295\u8d44\u5efa\u8bae</b> '
          '\u00b7 \u60f3\u63a5\u771f\u5b9e\u6570\u636e\uff0c'
          '\u8bf7 clone \u6e90\u7801\u672c\u5730\u8fd0\u884c\uff08'
          '\u81ea\u914d\u7ecf\u9500\u5546\u548c\u81ea\u8425\u5546\u8d26\u6237\u4fe1\u606f\uff0c'
          '\u4e70\u5356\u4ec5\u5728\u4f60\u672c\u673a\u6267\u884c\uff09 \u00b7 '
          '<a href="https://github.com/OneGearGo/YUJIN-AI-TRADER" '
          'target="_blank" rel="noopener" '
          'style="color:var(--lime);font-weight:600">'
          '\u67e5\u770b\u6e90\u4ee3\u7801 \u2197</a>')

# EN
OLD_EN = ('\u26a0 Demo Mode \u00b7 sample data, not an official trading '
          'function, not investment advice \u00b7 for real data, clone the '
          'source and run locally (your broker or own-up account info; '
          'trades execute only on your machine) \u00b7 '
          '<a href="https://github.com/OneGearGo/YUJIN-AI-TRADER" '
          'target="_blank" rel="noopener">View source \u2197</a>')

NEW_EN = ('\u26a0 <b>Demo Mode</b> \u00b7 sample data, '
          '<b>not an official trading function, not investment advice</b> '
          '\u00b7 for real data, clone the source and run locally '
          '(your broker or own-up account info; trades execute only on '
          'your machine) \u00b7 '
          '<a href="https://github.com/OneGearGo/YUJIN-AI-TRADER" '
          'target="_blank" rel="noopener" '
          'style="color:var(--lime);font-weight:600">'
          'View source \u2197</a>')

for f in files:
    txt = f.read_text(encoding='utf-8')
    zh_n = txt.count(OLD_ZH)
    en_n = txt.count(OLD_EN)
    assert zh_n == 1, f'{f}: zh anchor match count = {zh_n}, abort'
    assert en_n == 1, f'{f}: en anchor match count = {en_n}, abort'
    new = txt.replace(OLD_ZH, NEW_ZH, 1).replace(OLD_EN, NEW_EN, 1)
    f.write_text(new, encoding='utf-8')
    print(f'{f}: zh=1 en=1 OK')

print('Round-19 patch complete')
