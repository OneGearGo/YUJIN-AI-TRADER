import pathlib
files = ['static/index.html', 'docs/index.html']
OLD_HTML = '<div class="tag" data-i18n="tag">\u786e\u5b9a\u6027\u89c4\u5219\u6293\u5168 \u00b7 ML \u780d\u72e0 \u00b7 LLM \u53ea\u89e3\u91ca\u5b58\u6d3b\u8005 \u00b7 \u4f60\u6309\u4e0b\u6210\u4ea4</div>'
NEW_HTML = '<div class="tag" data-i18n="tag"></div>'
OLD_ZH = "    tag:'\u786e\u5b9a\u6027\u89c4\u5219\u6293\u5168 \u00b7 ML \u780d\u72e0 \u00b7 LLM \u53ea\u89e3\u91ca\u5b58\u6d3b\u8005 \u00b7 \u4f60\u6309\u4e0b\u6210\u4ea4',"
NEW_ZH = "    tag:'',"
OLD_JS = "const tagEl=document.querySelector('.tag');if(tagEl)tagEl.innerHTML=APP_VERSION+' \u00b7 '+t('tag');"
NEW_JS = "const tagEl=document.querySelector('.tag');if(tagEl)tagEl.innerHTML='';   // version+tagline removed per spec step 1"
for f in files:
    p = pathlib.Path(f)
    txt = p.read_text(encoding='utf-8')
    a = txt.count(OLD_HTML); b = txt.count(OLD_ZH); c = txt.count(OLD_JS)
    assert a == 1, f'{f}: HTML anchor count={a}, abort'
    assert b == 1, f'{f}: zh tag anchor count={b}, abort'
    assert c == 1, f'{f}: JS anchor count={c}, abort'
    new = txt.replace(OLD_HTML, NEW_HTML).replace(OLD_ZH, NEW_ZH).replace(OLD_JS, NEW_JS)
    p.write_text(new, encoding='utf-8')
    print(f'{f}: HTML=1 zh=1 JS=1 OK')
