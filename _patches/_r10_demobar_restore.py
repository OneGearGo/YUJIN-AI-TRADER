import codecs, re, sys

ROOT = r"F:\yujin-mt5"

NEW_CN_LIT = (
    "\u26a0 <b>\u6f14\u793a\u6a21\u5f0f</b> \u00b7 \u793a\u4f8b\u6570\u636e\uff0c"
    "\u975e\u5b98\u65b9\u4ea4\u6613\u529f\u80fd\uff0c\u4e0d\u6784\u6210\u6295\u8d44\u5efa\u8bae "
    "\u00b7 \u60f3\u63a5\u771f\u5b9e\u6570\u636e\uff0c\u8bf7 clone \u6e90\u7801\u672c\u5730\u8fd0\u884c"
    "\uff08\u81ea\u914d\u7ecf\u9500\u5546\u767b\u5165\u4fe1\u606f\uff0c\u4e70\u5356\u4ec5\u5728\u4f60\u672c\u673a\u6267\u884c\uff09 "
    "\u00b7 \u67e5\u770b\u6e90\u4ee3\u7801 \u2197"
)
NEW_EN_LIT = (
    "\u26a0 <b>Demo Mode</b> \u00b7 sample data, not an official trading feature, "
    "not investment advice \u00b7 To use real data, clone the source code locally and run "
    "(configure broker login info yourself, trading only on your machine) "
    "\u00b7 View source \u2197"
)

CJK_RE = re.compile(r"[\u4e00-\u9fff]")
PAT_DICT = re.compile(r"(demobar:\s*')([^']*)(')")
PAT_HTML_CN = re.compile(r'(<div\s+id="demoBar"[^>]*>)([^<]*)(</div>)')
PAT_HTML_EN = re.compile(r'(<div\s+id="publicBar"[^>]*>)([^<]*)(</div>)')


def has_cjk(s):
    return bool(CJK_RE.search(s))


def dict_repl(m):
    content = m.group(2)
    new = NEW_CN_LIT if has_cjk(content) else NEW_EN_LIT
    return m.group(1) + new + m.group(3)


def apply(file_path, label):
    text = codecs.open(file_path, "r", encoding="utf-8").read()
    text2 = PAT_DICT.sub(dict_repl, text)
    text2 = PAT_HTML_CN.sub(lambda m: m.group(1) + NEW_CN_LIT + m.group(3), text2, count=1)
    text2 = PAT_HTML_EN.sub(lambda m: m.group(1) + NEW_EN_LIT + m.group(3), text2, count=1)
    codecs.open(file_path, "w", encoding="utf-8").write(text2)
    n_dict = text2.count("demobar:'") + text2.count('demobar:"')
    n_db = text2.count('id="demoBar"')
    n_pb = text2.count('id="publicBar"')
    print("[ok] " + label + " rewritten; file size=" + str(len(text2))
    print("     hits post-write: demobar literals=" + str(n_dict) + ", #demoBar=" + str(n_db) + ", #publicBar=" + str(n_pb))


apply(ROOT + r"\static\index.html", "static/index.html")
apply(ROOT + r"\docs\index.html", "docs/index.html")
print("[done] demobar restored to user-specified wording")
