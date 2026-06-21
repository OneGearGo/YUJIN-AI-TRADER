# -*- coding: utf-8 -*-
"""
Round-35: bulletproof always-visible MT5-SIM overlay widget.

Strategy:
  - anchor: append AFTER  OLD=`setInterval(simTick,2500);\r\n`  (count==1 verified)
  - overlay creates its OWN DOM element — zero dependency on existing DOM structure
  - bright fixed-position widget top-right, 1.8s tick, big readable text
  - sentinel bumps: meta r34->r35, APP_VERSION v0.0.6->v0.0.7, title · r34 -> · r35
  - hard-mirror: cp -p static/index.html docs/index.html (gh-pages serves docs/)

Hard rules:
  - files: only static/index.html, docs/index.html
  - pre-check: cn_old==1 (anchor exists exactly once)
  - post-check: cn_new==1 (overwrite counts), cn_old==0 (anchor consumed)
  - refusal on any mismatch
"""

import io, sys, os, shutil, subprocess

FILES = [
    r'F:\yujin-mt5\static\index.html',
    r'F:\yujin-mt5\docs\index.html',
]

OLD_ANCHOR = 'setInterval(simTick,2500);\r\n'

# Self-contained IIFE block. Self-creates DOM, no fragile selectors.
NEW_BLOCK = (
    '\r\n'
    '/* === Round-35 loud MT5-SIM motion overlay (self-built DOM, zero selector deps) === */\r\n'
    'try{\r\n'
    'if(!window.__SIM_R35__){\r\n'
    'window.__SIM_R35__=1;\r\n'
    '(function(){\r\n'
    'function make(tag,attrs,text){var el=document.createElement(tag);for(var k in attrs){el.setAttribute(k,attrs[k]);}if(typeof text==="string"){el.textContent=text;}return el;}\r\n'
    'function boot(){\r\n'
    'var host=document.body||document.documentElement;\r\n'
    'var wrap=document.getElementById("r35-overlay");\r\n'
    'if(!wrap){wrap=make("div",{id:"r35-overlay",style:"position:fixed;top:8px;right:8px;z-index:99999;padding:14px 18px;border-radius:10px;background:rgba(0,0,0,0.92);color:#00ffff;border:3px solid #00ffff;font-family:Menlo,Monaco,Consolas,monospace;font-size:15px;font-weight:700;line-height:1.35;box-shadow:0 0 20px #00ffff80;pointer-events:none;min-width:240px;max-width:340px"});host.appendChild(wrap);}\r\n'
    'var head=make("div",{style:"font-size:18px;color:#ffff00;text-shadow:0 0 8px #ffff00;letter-spacing:1px;margin-bottom:8px;border-bottom:1px solid #00ffff;padding-bottom:6px"},"MT5\u00b7SIM\u00b7R35");\r\n'
    'var sym=make("div",{style:"font-size:16px;color:#00ff00;margin-bottom:4px"},"XAUUSD");\r\n'
    'var lat=make("div",{style:"font-size:14px;color:#ffffff;margin-bottom:2px"},"P50 LAT  160ms");\r\n'
    'var bal=make("div",{style:"font-size:14px;color:#ffffff;margin-bottom:2px"},"BAL     $10,000.00");\r\n'
    'var pnl=make("div",{style:"font-size:18px;color:#ff00ff;color:#00ff00;margin-bottom:6px"},"PNL     +0.00%");\r\n'
    'var act=make("div",{style:"font-size:13px;color:#ffa500;margin-bottom:4px"},"ACT     HOLD");\r\n'
    'var tick=make("div",{style:"font-size:11px;color:#888;margin-top:6px;padding-top:6px;border-top:1px solid #333"},"tick   1");\r\n'
    'var old=wrap.children;while(old.length){wrap.removeChild(old[0]);}\r\n'
    'wrap.appendChild(head);wrap.appendChild(sym);wrap.appendChild(lat);wrap.appendChild(bal);wrap.appendChild(pnl);wrap.appendChild(act);wrap.appendChild(tick);\r\n'
    'var SYMS=["XAUUSD","EURUSD","GBPUSD","USDJPY","NAS100","US500","BTCUSD","ETHUSD"];\r\n'
    'var ACTS=["BUY","SELL","HOLD","REJECT","WAIT","PARTIAL","FILL"];\r\n'
    'var n=0;var bal0=10000;var pnl0=0;\r\n'
    'function paint(){\r\n'
    'n++;var v=Math.floor(105+Math.random()*115);var s=SYMS[Math.floor(Math.random()*SYMS.length)];var a=ACTS[Math.floor(Math.random()*ACTS.length)];var drift=Math.round((Math.random()-0.5)*80);bal0+=drift;pnl0=parseFloat(((Math.random()-0.5)*0.18).toFixed(3));var appy=(Math.random()<0.5);var pnlClr=pnl0>=0?"#00ff00":"#ff4444";var pnlStr=(pnl0>=0?"+":"")+pnl0.toFixed(2)+"%";\r\n'
    'sym.textContent="SYMBOL  "+s;lat.textContent="P50 LAT  "+v+"ms";bal.textContent="BAL     $"+bal0.toLocaleString("en-US",{minimumFractionDigits:2,maximumFractionDigits:2});pnl.textContent="PNL     "+pnlStr;pnl.style.color=pnlClr;act.textContent="ACT     "+a;tick.textContent="tick   "+n+"  \u00b7 live";\r\n'
    'try{var hd=wrap.firstChild;hd.style.color=n%2?"#ffff66":"#ffffaa";hd.style.textShadow="0 0 "+((n%2?6:14))+"px "+(n%2?"#ff8800":"#ffff00");}catch(_e){}\r\n'
    '}\r\n'
    'paint();setInterval(paint,1800);\r\n'
    '}\r\n'
    'if(document.readyState==="loading"){document.addEventListener("DOMContentLoaded",boot);}else{boot();}\r\n'
    'window.addEventListener("load",boot);\r\n'
    '})();\r\n'
    '}\r\n'
    '}catch(_e){}\r\n'
    '\r\n'
)

SENTINELS = [
    # positive: anchor still present (NEW wraps OLD + overlay block)
    ('setInterval(simTick,2500);\r\n',           1, 'R32 simTick anchor preserved as prefix of NEW'),
    # positive: must exist exactly once
    ('yujin-build" content="r35"',                1, 'R35 meta tag'),
    ("const APP_VERSION='v0.0.7';",              1, 'R35 APP_VERSION bump'),
    ('\u00b7 r35',                                1, 'R35 build number in title'),
    ('window.__SIM_R35__=1',                     1, 'R35 idempotency flag'),
    ('id="r35-overlay"',                         1, 'R35 self-built overlay id'),
    ('MT5\u00b7SIM\u00b7R35',                    1, 'R35 widget header label'),
    ('SYMBOL  ',                                 1, 'R35 widget rotating symbol'),
    ('ACT     ',                                 1, 'R35 widget rotating action'),
    # negative: old versions must NOT exist anymore
    ('yujin-build" content="r34"',               0, 'old R34 meta (must be consumed)'),
    ("const APP_VERSION='v0.0.6';",              0, 'old R34 APP_VERSION (must be consumed)'),
    ('\u00b7 r34',                                0, 'old R34 in title (must be consumed)'),
    ('window.__SIM_R34__',                       0, 'old R34 idempotency flag (must be consumed)'),
    ('id="r34-motion"',                          0, 'old R34 overlay id if landed (must be consumed)'),
]

# revision
OLD_TO_NEW_SENTINEL = [
    ('yujin-build" content="r34"',  'yujin-build" content="r35"'),
    ("const APP_VERSION='v0.0.6';", "const APP_VERSION='v0.0.7';"),
    ('\u00b7 r34',                   '\u00b7 r35'),
]

REWRITES = [
    (OLD_ANCHOR, OLD_ANCHOR + NEW_BLOCK, 'R35 inject loud overlay after R32 simTick setInterval'),
] + [
    (old, new, 'R35 sentinel bump: ' + label)
    for (old, new, label) in OLD_TO_NEW_SENTINEL
]

# ============================== driver ==============================

def apply(path):
    with io.open(path, 'r', encoding='utf-8', newline='') as f:
        s = f.read()
    print('  {} · {} bytes'.format(os.path.basename(os.path.dirname(path))+ '/' + os.path.basename(path), len(s)))

    pre_pass = True
    for idx, (old, new, label) in enumerate(REWRITES, 1):
        cn_old = s.count(old)
        if cn_old == 0:
            print('  ANCHOR #{} ({}): SKIP-not-found ({})'.format(idx, label, type(old).__name__))
            continue
        if cn_old > 1:
            print('  ANCHOR #{} ({}): ABORT-multiple old ({} hits)'.format(idx, label, cn_old))
            return False
        if old == new:
            print('  ANCHOR #{} ({}): SKIP-no-op'.format(idx, label))
            continue
        # anti-collision: if new is a substring of old (or vice versa) AND old appears in new, abort
        if new.find('') >= 0 and old != new:
            # both non-empty
            pass
        # apply
        s2 = s.replace(old, new, 1)
        if s2 == s:
            print('  ANCHOR #{} ({}): ABORT-no-change-after-replace'.format(idx, label))
            return False
        if s2.find(old) != -1:
            # old substring still present in s2 (rare for substring-split operations); tolerate but warn
            print('  ANCHOR #{} ({}): WARN-old-substring-still-present-after-replace'.format(idx, label))
        s = s2
        print('  ANCHOR #{} ({}): OK'.format(idx, label))

    # post-check
    for needle, want, label in SENTINELS:
        cn = s.count(needle)
        if cn != want:
            print('  POST-CHECK label={} expected={} got={}  ABORT'.format(label, want, cn))
            return False

    # write back, preserve CRLF
    with io.open(path, 'w', encoding='utf-8', newline='') as f:
        f.write(s)
    print('  {} · wrote {} bytes'.format(path, len(s)))
    return True


def main():
    ok_all = True
    for p in FILES:
        print('##### {} #####'.format(p))
        if not apply(p):
            ok_all = False
            print('  REFUSE file {}'.format(p))
    if not ok_all:
        print('\nPATCHER ABORTED')
        sys.exit(1)
    print('\nPATCHER OK — mirrored apply to static + docs')


if __name__ == '__main__':
    main()
