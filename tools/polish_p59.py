"""Polish #5.9 micro-cleanup applier v3: fix Edit 2 anchor + UTF-8 stdout reconfigure."""
import sys
try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass  # older Python; fall back to ASCII-safe prints below

EMDASH = chr(0x2014)  # \\u2014
MIDDOT = chr(0x00B7)  # \\u00b7 middle dot
TIAN   = chr(0x5929)  # \\u5929

# Track success/failure for post-mortem
ok1 = ok2 = ok3 = False

# ===== EDIT 1: renderKpiPanel body L1131 =====
# Sub-label rendering: ${KPI_LABEL[k]} <MIDDOT> 7 <TIAN>
with open('static/index.html', 'rb') as f:
    raw = f.read()
src = raw.replace(b'\r\n', b'\n').replace(b'\r', b'\n').decode('utf-8')

o1 = '${KPI_LABEL[k]} ' + MIDDOT + ' 7 ' + TIAN
n1 = "${KPI_LABEL[k]??'" + EMDASH + "'} " + MIDDOT + ' 7 ' + TIAN
c1 = src.count(o1)
print('Edit 1 anchor count (L1131 sub-label):', c1)
if c1 != 1:
    print('FAIL Edit 1: anchor not unique')
    sys.exit(2)
src = src.replace(o1, n1, 1)
print('OK Edit 1: KPI_LABEL[k]??em-dash added to renderKpiPanel .sub label')
ok1 = True

# ===== EDIT 2: UI dispatch L967 =====
# The actual byte sequence in the line '.. <MIDDOT> <SPACE>\'+KPI_LABEL[k];'
# Anchor: MIDDOT + ' \'+KPI_LABEL[k];'  (NO leading apostrophe; apostrophe lives in the JS string-end position)
o2 = MIDDOT + " '+KPI_LABEL[k];"
n2 = MIDDOT + " '+(KPI_LABEL[k]??'" + EMDASH + "');"
c2 = src.count(o2)
print('Edit 2 anchor count (L967 concat):', c2)
if c2 != 1:
    print('FAIL Edit 2: anchor not unique; bytes near "KPI_LABEL[k]":')
    # ASCII-safe diagnostic: show only printable ASCII
    idx = src.find('KPI_LABEL[k]')
    cnt = 0
    while idx != -1 and cnt < 5:
        ctx = src[max(0,idx-25):idx+45]
        ctx_safe = ctx.encode('ascii', 'replace').decode('ascii')
        print('  offset', idx, ':', ctx_safe)
        idx = src.find('KPI_LABEL[k]', idx+1)
        cnt += 1
    sys.exit(2)
src = src.replace(o2, n2, 1)
print('OK Edit 2: KPI_LABEL[k]??em-dash added to UI title concatenation')
ok2 = True

# Verify final counts
print('escapeHtml count after edits:', src.count('escapeHtml('))
emdash_fallback_count = src.count("KPI_LABEL[k]??'" + EMDASH + "'")
print('KPI_LABEL[k]??em-dash count after edits:', emdash_fallback_count)

with open('static/index.html', 'wb') as f:
    f.write(src.encode('utf-8'))
print('Wrote static/index.html (utf-8,', len(src), 'chars)')

# ===== EDIT 3: append 1-line pytest assertion to tests/test_routes_broker.py =====
with open('tests/test_routes_broker.py', 'rb') as f:
    t_raw = f.read()
t_src = t_raw.replace(b'\r\n', b'\n').replace(b'\r', b'\n').decode('utf-8')

new_test = (
    "\n\n# Polish #5.9 micro-cleanup: KPI_LABEL[k] em-dash fallback assertion\n"
    "def test_renderKpiPanel_kpi_label_has_emdash_fallback():\n"
    "    src = open('static/index.html', encoding='utf-8').read()\n"
    '    assert "KPI_LABEL[k]??" + chr(0x2014) + "\'" in src and src.count("KPI_LABEL[k]??" + chr(0x2014) + "\'") >= 2\n'
)
t_src_with_test = t_src + new_test

with open('tests/test_routes_broker.py', 'wb') as f:
    f.write(t_src_with_test.encode('utf-8'))
print('Wrote tests/test_routes_broker.py (', len(t_src_with_test), 'chars, +', len(t_src_with_test) - len(t_src), ')')
ok3 = True

print('\nSUMMARY: ok1=', ok1, 'ok2=', ok2, 'ok3=', ok3)
