"""Polish #6.3 recovery applier: trim F:/yujin-mt5/.gitignore to user-spec 4 patterns.

Per the just-finished code-review (🟢 LGTM + 2 🟡 LOW):
- Remove `.tmp*/` (over-broad; would match `.tmpfiles/` etc.)
- Remove `.bak*` (over-broad; would match `.bakery.txt` etc.)
- Keep only the 4 user-spec patterns: `*.bak`, `.bak*/`, `.tmp_patch_backup/`, `.tmp_patch_*/`
- Section header comment preserved.
"""
import sys
try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

path = r'C:/Users/Administrator/Desktop/_patch_gitignore'

with open(path, 'rb') as f:
    raw = f.read()
src = raw.replace(b'\r\n', b'\n').replace(b'\r', b'\n').decode('utf-8')

# Multi-line anchor: the 6 patterns appended earlier (must be unique in .gitignore)
o = '*.bak\n.bak*/\n.tmp_patch_backup/\n.tmp_patch_*/\n.tmp*/\n.bak*\n'
n = '*.bak\n.bak*/\n.tmp_patch_backup/\n.tmp_patch_*/\n'

c = src.count(o)
print('Anchor count (6-pattern block to trim):', c)
if c != 1:
    print('FAIL: anchor not unique')
    sys.exit(2)
src = src.replace(o, n, 1)
print('OK: trimmed 6 patterns -> 4 patterns (dropped .tmp*/ and .bak*)')

with open(path, 'wb') as f:
    f.write(src.encode('utf-8'))
print('Wrote', path, '(' + str(len(src)) + ' chars)')
