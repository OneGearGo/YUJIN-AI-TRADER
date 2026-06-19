"""HANDOFF.md commit 3 docs-handoff applier (final recovery) — 4 edits + hook-clean."""
import subprocess
import sys

CHORE_SHORT = '31bf44b'
FEAT_SHORT = 'f7fe3e7'

with open('HANDOFF.md', 'rb') as f:
    raw = f.read()
src = raw.replace(b'\r\n', b'\n').replace(b'\r', b'\n').decode('utf-8')

# ===== Edit 1: tally bump (5 PIECES across 5 COMMITS -> 6 PIECES across 8 COMMITS)
o1 = '**pieces count**: 5 PIECES across 5 COMMITS'
n1 = '**pieces count**: 6 PIECES across 8 COMMITS'
if src.count(o1) != 1:
    print('FAIL Edit 1: tally anchor mismatch (count=%d)' % src.count(o1))
    sys.exit(2)
src = src.replace(o1, n1, 1)
print('OK Edit 1: tally bump')

# ===== Edit 2: TBD pointer closure with feat hash + breadcrumb for chore + feat hash
lines = src.split('\n')
tbd_idx = None
for i, ln in enumerate(lines):
    if 'commit TBD' in ln and 'Polish #5.5 frontend XSS hardening' in ln:
        tbd_idx = i
        print('OK Edit 2: TBD line index =', i)
        break
if tbd_idx is None:
    print('FAIL Edit 2: TBD line not found')
    sys.exit(2)

new_main = '- Polish #5.5 frontend XSS hardening closed in feat(frontend) commit [' + FEAT_SHORT + ']: 4 escapeHtml() wraps + TODO breadcrumb close-out landed on static/index.html.'
new_extra = '  - chore commit [' + CHORE_SHORT + ']: Polish #5.7 test tier closure (UI resilience + helper parity). Polish #5.5/#5.7/#5.8 frontend XSS + resilience ladder finalize on origin/main.'
lines[tbd_idx] = new_main
lines.insert(tbd_idx + 1, new_extra)
src = '\n'.join(lines)
print('OK Edit 2: TBD closure')

# ===== Edit 3: insert new bullet entry (Polish #5.7 test tier) before bullet 5 to keep
# [closed] section count = 6 (matching 6 PIECES tally)
# Look for the prior Polish #5.4 / Polish #5.5/.5.6 / Polish #5.7 / Polish #5.8 ladder block
idx_5_8 = None
idx_5_x = None
for i, ln in enumerate(lines):
    if 'Polish #5.8' in ln and any(x in ln for x in ['audit', '###', '[closed]', 'audit complete']):
        idx_5_8 = i
    if ('Polish #5.x ladder' in ln) or ('### [closed] Polish #5' in ln):
        idx_5_x = i
# find the "Polish #5.5 frontend XSS hardening" line that we just replaced (it's now new_main)
# and INSERT a new bullet "Polish #5.7 test tier closure" just above it.
new_main_idx = None
for i, ln in enumerate(lines):
    if ln == new_main:
        new_main_idx = i
        break
if new_main_idx is None:
    print('FAIL Edit 3: new_main line not found for insertion above')
    sys.exit(2)

# Find the line just above that says 'X. Polish #5.8: ...' which is the LAST numbered bullet
# (Help: list the 5 lines above new_main)
above = []
for j in range(max(0, new_main_idx - 12), new_main_idx):
    above.append((j, lines[j]))
print('  above new_main (last 12 lines):')
for j, ln in above:
    print('   ', j, repr(ln[:120]))

# Insert a NEW bullet labeled 'Polish #5.7 test tier' right above the "X. Polish #5.8:" line
# (Or anywhere in the [closed] Polish #5.x ladder block that adds 1 bullet)
# Plan: insert it just above the TBD-replacement line so it appears as a NEW 4th or 5th bullet.
# We'll insert a 'Polish #5.7 test tier: ...' bullet right above new_main.
# But bullet numbering is sequential. The cleanest is to INSERT it as a NEW bullet named
# 'Polish #5.7 test tier closure' (numbering left as 4.5 or 5.5 in narrative).
new_bullet = '- Polish #5.7 test tier closure (chore commit [' + CHORE_SHORT + ']): UI resilience + helper parity.'
lines.insert(new_main_idx, new_bullet)
# Now new_main is at new_main_idx+1
src = '\n'.join(lines)
print('OK Edit 3: new bullet insert (Polish #5.7 test tier closure)')

# Write back
with open('HANDOFF.md', 'wb') as f:
    f.write(src.encode('utf-8'))
print('Wrote HANDOFF.md (utf-8,', len(src), 'chars)')

# ===== Verify hook
print('\n--- hook validation ---')
r = subprocess.run(['python', 'tools/check_unicode_escapes.py', '--check-handoff', 'HANDOFF.md'],
                   capture_output=True, text=True)
print('exit code:', r.returncode)
print('stdout:', r.stdout.strip())
print('stderr:', r.stderr.strip()[:200])
if r.returncode != 0:
    print('HOOK REJECTED — exiting without committing')
    sys.exit(3)
print('HOOK OK')
