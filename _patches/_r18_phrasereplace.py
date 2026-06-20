import pathlib, sys

files = [
    pathlib.Path('static/index.html'),
    pathlib.Path('docs/index.html'),
]

OLD = '\u81ea\u914d\u7ecf\u9500\u5546\u6216\u81ea\u8425\u4e0a\u8d26\u6237\u4fe1\u606f'
NEW = '\u81ea\u914d\u7ecf\u9500\u5546\u548c\u81ea\u8425\u5546\u8d26\u6237\u4fe1\u606f'

for f in files:
    txt = f.read_text(encoding='utf-8')
    n = txt.count(OLD)
    assert n >= 1, f'{f}: anchor not found, abort'
    new = txt.replace(OLD, NEW)
    f.write_text(new, encoding='utf-8')
    print(f'{f}: swapped {n} occurrence(s)')
