import pathlib
p = pathlib.Path('F:/yujin-mt5/static/g3.py')
txt = p.read_text('utf-8')
# The 3 broken lines use Python single quotes wrapping JS that also has single quotes.
# Fix: change w('...') to w("...") for those lines, escaping inner double quotes.
old_gi = "w('function gi(v){return v?'" + '<span class="gg ok">Y</span>' + "':'" + '<span class="gg no">N</span>' + "'}')"
new_gi = 'w("function gi(v){return v?\'\'<span class="gg ok">Y</span>\'\':\'\'<span class="gg no">N</span>\'\'\'})"'
# Actually simpler: just find and replace the broken lines
lines = txt.split('\n')
fixed = []
for line in lines:
    if 'function gi(v){return' in line:
        fixed.append('w("function gi(v){return v?\'\'<span class="gg ok">Y</span>\'\':\'\'<span class="gg no">N</span>\'\'\'})")')
    elif 'function gn(){return' in line:
        fixed.append('w(\'function gn(){return \'\'<span class="gg na">-</span>\'\'\'}\')')
    elif 'function bi(b){return' in line:
        fixed.append('w("function bi(b){return b===\'bull\'?\'\'<span class="gg ok">^</span>\'\':b===\'bear\'?\'\'<span class="gg no">v</span>\'\':gn()}")')
    else:
        fixed.append(line)
result = '\n'.join(fixed)
p.write_text(result, 'utf-8')
print('Fixed 3 lines in g3.py')
