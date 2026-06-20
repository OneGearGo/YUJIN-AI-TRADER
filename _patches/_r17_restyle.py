#!/usr/bin/env python3
# Round-17: restore inline lime-bold style on the demobar link
# Per reference https://gmgnai.github.io/skillmarket-demos/aitrader/
import pathlib

files = [
    pathlib.Path('static/index.html'),
    pathlib.Path('docs/index.html'),
]

OLD_ZH = '<a href="https://github.com/OneGearGo/YUJIN-AI-TRADER" target="_blank" rel="noopener">查看源代码 ↗</a>'
NEW_ZH = '<a href="https://github.com/OneGearGo/YUJIN-AI-TRADER" target="_blank" rel="noopener" style="color:var(--lime);font-weight:600">查看源代码 ↗</a>'
OLD_EN = '<a href="https://github.com/OneGearGo/YUJIN-AI-TRADER" target="_blank" rel="noopener">View source ↗</a>'
NEW_EN = '<a href="https://github.com/OneGearGo/YUJIN-AI-TRADER" target="_blank" rel="noopener" style="color:var(--lime);font-weight:600">View source ↗</a>'

total = 0
for f in files:
    txt = f.read_text(encoding='utf-8')
    zh_n = txt.count(OLD_ZH)
    en_n = txt.count(OLD_EN)
    new = txt.replace(OLD_ZH, NEW_ZH).replace(OLD_EN, NEW_EN)
    f.write_text(new, encoding='utf-8')
    print(f'{f}: ZH swapped={zh_n}  EN swapped={en_n}')
    total += zh_n + en_n

print(f'TOTAL swaps: {total}')
