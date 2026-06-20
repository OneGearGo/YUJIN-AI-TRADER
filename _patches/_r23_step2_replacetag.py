#!/usr/bin/env python3
# Round-23 step 2: replace .tag content with the user's new zh phrase.
# After step 1 (Round-22), .tag was emptied across HTML element + zh i18n literal + JS injection.
# Step 2: repopulate with "你按下成交 ➡️ 人机协同 / 一锤定音 / 闭环收口 / 最终授权 / 拍板转化"
#
# 3 edits per file × 2 files:
# 1. HTML line 281: empty <div class="tag"> → contains new phrase (defensive vs FOUC)
# 2. I18N.zh.tag literal line 400: tag:'' → tag:'<new phrase>'
# 3. JS line 1377: tagEl.innerHTML=''; → tagEl.innerHTML=t('tag');
#    (drop APP_VERSION + ' · ' prefix: user deleted "v0.0.1 · ..." in step 1, did NOT
#     want the version prefix back when re-populating. en mode still shows EN literal
#     because t('tag') reads current lang dict key.)
#
# NOT touched (per user mandate of zh-only change):
#   - I18N.en.tag literal (line 548): "Deterministic rules cast wide · ... · you press to trade"
#   - APP_VERSION const (line 699)
#   - CSS .tag rule (line 49)
#   - any other literal
#
# Literal UTF-8 chars here (no \u escapes) so heredoc delivery stays byte-perfect.
# -*- coding: utf-8 -*-
import pathlib

files = [
    pathlib.Path('static/index.html'),
    pathlib.Path('docs/index.html'),
]

NEW_PHRASE = '你按下成交 ➡️ 人机协同 / 一锤定音 / 闭环收口 / 最终授权 / 拍板转化'

# 1. HTML element
OLD_HTML = '<div class="tag" data-i18n="tag"></div>'
NEW_HTML = f'<div class="tag" data-i18n="tag">{NEW_PHRASE}</div>'

# 2. I18N.zh.tag literal
OLD_ZH = "    tag:'',"
NEW_ZH = f"    tag:'{NEW_PHRASE}',"

# 3. JS injection: revert from "= '';   // version+tagline removed per spec step 1"
#                  to "= t('tag');   // spec step 2: render the t('tag') literal only"
OLD_JS = "tagEl.innerHTML='';   // version+tagline removed per spec step 1"
NEW_JS = "tagEl.innerHTML=t('tag');   // spec step 2: drop APP_VERSION prefix; render only t('tag') zh/en dict value"

for f in files:
    txt = f.read_text(encoding='utf-8')
    a = txt.count(OLD_HTML)
    b = txt.count(OLD_ZH)
    c = txt.count(OLD_JS)
    assert a == 1, f'{f}: HTML anchor count={a}, abort'
    assert b == 1, f'{f}: zh tag anchor count={b}, abort'
    assert c == 1, f'{f}: JS anchor count={c}, abort'
    new = txt.replace(OLD_HTML, NEW_HTML).replace(OLD_ZH, NEW_ZH).replace(OLD_JS, NEW_JS)
    f.write_text(new, encoding='utf-8')
    print(f'{f}: HTML=1 zh=1 JS=1 OK')

print('Round-23 (spec step 2) patch complete')
