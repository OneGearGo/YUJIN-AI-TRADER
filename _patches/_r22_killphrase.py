#!/usr/bin/env python3
# Round-22 step 1: delete the rendered phrase
#   "v0.0.1 · 确定性规则抓全 · ML 砍狠 · LLM 只解释幸存者 · 你按下成交"
#
# 3 string-anchored edits per file:
# 1. HTML element on line 281: empty content of <div class="tag" data-i18n="tag">
# 2. I18N.zh.tag literal on line 400
# 3. JS injection on line 1377: tagEl.innerHTML = APP_VERSION + ' · ' + t('tag')
#
# NOT touched (per user rule):
# - I18N.en.tag (line 548)
# - APP_VERSION const (line 699)
# - CSS rules
# - any other literal / phrase
#
# Literal UTF-8 chars here (no \u escapes) so heredoc delivery stays byte-perfect.
# -*- coding: utf-8 -*-
import pathlib

files = [
    pathlib.Path('static/index.html'),
    pathlib.Path('docs/index.html'),
]

OLD_HTML = '<div class="tag" data-i18n="tag">确定性规则抓全 · ML 砍狠 · LLM 只解释幸存者 · 你按下成交</div>'
NEW_HTML = '<div class="tag" data-i18n="tag"></div>'

OLD_ZH   = "    tag:'确定性规则抓全 · ML 砍狠 · LLM 只解释幸存者 · 你按下成交',"
NEW_ZH   = "    tag:'',"

OLD_JS   = "const tagEl=document.querySelector('.tag');if(tagEl)tagEl.innerHTML=APP_VERSION+' · '+t('tag');"
NEW_JS   = "const tagEl=document.querySelector('.tag');if(tagEl)tagEl.innerHTML='';   // version+tagline removed per spec step 1"

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

print('Round-22 patch complete')
