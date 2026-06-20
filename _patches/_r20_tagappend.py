import pathlib
files = ['static/index.html', 'docs/index.html']
OLD = '\u786e\u5b9a\u6027\u89c4\u5219\u6293\u5168 \u00b7 ML \u780d\u72e0 \u00b7 LLM \u53ea\u89e3\u91ca\u5b58\u6d3b\u8005 \u00b7 \u4f60\u6309\u4e0b\u6210\u4ea4'
NEW = '\u786e\u5b9a\u6027\u89c4\u5219\u6293\u5168 \u00b7 ML \u780d\u72e0 \u00b7 LLM \u53ea\u89e3\u91ca\u5b58\u6d3b\u8005 \u00b7 \u4f60\u6309\u4e0b\u6210\u4ea4 \u27a1\ufe0f \u4eba\u673a\u534f\u540c / \u4e00\u9525\u5b9a\u97f3 / \u95ed\u73af\u6536\u53e3 / \u6700\u7ec8\u6388\u6743 / \u62cd\u677f\u8f6c\u5316'
for f in files:
  p = pathlib.Path(f)
  txt = p.read_text(encoding='utf-8')
  n = txt.count(OLD)
  assert n == 2, f'{f}: expected 2 chinese anchors (HTML element + zh i18n literal), got {n}'
  new = txt.replace(OLD, NEW)
  p.write_text(new, encoding='utf-8')
  print(f'{f}: swapped {n} occurrences')
