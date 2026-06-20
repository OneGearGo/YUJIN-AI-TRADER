import codecs, re, ast

ROOT = r"F:\yujin-mt5"

# PATCH 1: aitrader_adapter.py - rewrite map_mt5_to_aitrader for legacy aitrader schema
adapter_path = ROOT + r"\aitrader_adapter.py"
text = codecs.open(adapter_path, "r", encoding="utf-8").read()
marker = "def map_mt5_to_aitrader("
idx = text.find(marker)
assert idx >= 0, "map_mt5_to_aitrader not found"

rest = text[idx:]
m = re.search(r"\ndef\s", rest[len(marker):])
end_idx = idx + len(marker) + m.start() + 1 if m else len(text)
assert end_idx > idx, "no end of function found"

codecs.open(adapter_path + ".bak_map", "w", encoding="utf-8").write(text[idx:end_idx])

NEW_FUNC = (
    "def map_mt5_to_aitrader(idx, mt_row, symbol, price):\n"
    "    if not isinstance(mt_row, dict):\n"
    "        mt_row = {}\n"
    "    sym = (mt_row.get('sym') or symbol or '').strip()\n"
    "    addr = ('MT5_' + sym) if sym else 'MT5_UNK'\n"
    "    status_raw = (mt_row.get('status') or mt_row.get('action') or '').upper()\n"
    "    if status_raw in ('OPEN', 'EXEC'):\n"
    "        action = 'action'\n"
    "    elif status_raw in ('HOLD', 'WARN', 'WAIT'):\n"
    "        action = 'warn'\n"
    "    else:\n"
    "        action = 'reject'\n"
    "    reason = mt_row.get('reason') or ''\n"
    "    v = mt_row.get('verdict') or {}\n"
    "    if isinstance(v, dict):\n"
    "        vstr = v.get('verdict') or 'WARN'\n"
    "        conv_v = float(v.get('conviction') or 0.5)\n"
    "        crowd_v = v.get('crowdedness') or ('early' if conv_v > 0.7 else ('mid' if conv_v > 0.4 else 'late'))\n"
    "        thr_v = v.get('thesis') or reason\n"
    "    else:\n"
    "        vstr = 'WARN'\n"
    "        conv_v = 0.5\n"
    "        crowd_v = 'late'\n"
    "        thr_v = reason\n"
    "    f = mt_row.get('features') or {}\n"
    "    if not isinstance(f, dict):\n"
    "        f = {}\n"
    "    b = f.get('bundler')\n"
    "    if b is True:\n"
    "        bund_v = 1.0\n"
    "    elif b is False:\n"
    "        bund_v = 0.0\n"
    "    else:\n"
    "        try:\n"
    "            bund_v = float(b or 0.0)\n"
    "        except Exception:\n"
    "            bund_v = 0.0\n"
    "    smc_raw = f.get('sm_confluence')\n"
    "    smc_v = float(smc_raw) if isinstance(smc_raw, (int, float)) else 0.0\n"
    "    sd_raw = f.get('smart_degen')\n"
    "    if isinstance(sd_raw, (int, float)):\n"
    "        prio_v = float(sd_raw)\n"
    "    else:\n"
    "        try:\n"
    "            prio_v = float(mt_row.get('priority') or 50.0)\n"
    "        except Exception:\n"
    "            prio_v = 50.0\n"
    "    prio_int = max(0, min(99, int(prio_v)))\n"
    "    try:\n"
    "        size_v = float(mt_row.get('lots') or 0.01)\n"
    "    except Exception:\n"
    "        size_v = 0.01\n"
    "    exit_obj = mt_row.get('exit_plan') or {}\n"
    "    if not isinstance(exit_obj, dict):\n"
    "        exit_obj = {}\n"
    "    return {\n"
    "        '_i': idx,\n"
    "        'sym': sym,\n"
    "        'inj': False,\n"
    "        'addr': addr,\n"
    "        'address': addr,\n"
    "        'hp': bool(f.get('honeypot', False)),\n"
    "        'ren': bool(f.get('renounced', True)),\n"
    "        'bund': round(bund_v, 4),\n"
    "        'dev': round(float(f.get('dev_hold') or 0.0), 4),\n"
    "        'top10': round(float(f.get('top10') or 0.0), 4),\n"
    "        'smc': round(smc_v, 2),\n"
    "        'degen': float(f.get('smart_degen') or 0),\n"
    "        'kol': float(f.get('renowned') or 0),\n"
    "        'age': int(f.get('age_min') or 0),\n"
    "        'crowd': crowd_v,\n"
    "        'v': vstr,\n"
    "        'conv': round(conv_v, 3),\n"
    "        'status': action,\n"
    "        'warn': reason[:200],\n"
    "        'size': size_v,\n"
    "        'died': reason,\n"
    "        'exit': exit_obj,\n"
    "        'exit_plan': exit_obj,\n"
    "        'reason': reason,\n"
    "        'sl': mt_row.get('sl') or (mt_row.get('exec') or {}).get('hard_sl') or 0,\n"
    "        'tp': mt_row.get('tp') or (mt_row.get('exec') or {}).get('tp_ladder') or 0,\n"
    "        'spread': mt_row.get('spread'),\n"
    "        'gap_pct': mt_row.get('gap_pct'),\n"
    "        'thesis': thr_v,\n"
    "        'priority': prio_int,\n"
    "        'symbol': sym,\n"
    "    }\n\n"
)

text_new = text[:idx] + NEW_FUNC + text[end_idx:]
ast.parse(text_new)
codecs.open(adapter_path, "w", encoding="utf-8").write(text_new)
print("[ok] aitrader_adapter.py: map_mt5_to_aitrader rewritten " + str(len(text)) + " -> " + str(len(text_new)))

# PATCH 2: static/index.html - update #demoBar and #publicBar hardcoded text
static_path = ROOT + r"\static\index.html"
text2 = codecs.open(static_path, "r", encoding="utf-8").read()

NEW_DEMOBAR_CN = (
    "\u26a0 <b>\u6f14\u793a\u6570\u636e</b> "
    "\u00b7 \u4ec5\u4f5c MT5 thin-proxy \u6280\u672f\u6f14\u793a\uff0c"
    "\u975e\u4ea4\u6613\u7cfb\u7edf\u3001\u65e0\u4efb\u4f55\u6295\u8d44\u5efa\u8bae "
    "\u00b7 \u771f\u5b9e\u63a5\u5165\u8bf7 clone \u4ed3\u5e93\u5230\u672c\u5730\u3001"
    "\u81ea\u914d\u7ecf\u7eaa\u5546\u8d26\u6237\uff0c"
    "\u6240\u6709\u4e0b\u5355\u4ec5\u5728\u4f60\u672c\u673a\u6267\u884c"
)
NEW_DEMOBAR_EN = (
    "\u26a0 <b>Demo data</b> "
    "\u00b7 MT5 thin-proxy technical demo only, not a trading system, no investment advice "
    "\u00b7 For real usage: clone the repo locally, configure your own broker account, "
    "all orders execute only on your machine"
)

count_hit = 0
for elem_id in ('demoBar', 'publicBar'):
    new_inner = NEW_DEMOBAR_CN if elem_id == 'demoBar' else NEW_DEMOBAR_EN
    pat = re.compile(r"(id\s*=\s*['\"]" + elem_id + r"['\"][^>]*>)([^<]*)(</[^>]+>)")
    if pat.search(text2):
        text2 = pat.sub(lambda mm: mm.group(1) + new_inner + mm.group(3), text2, count=1)
        print("[ok] #" + elem_id + " updated")
        count_hit += 1
    else:
        print("[miss] #" + elem_id + " not matched")

# PATCH 3: CSS word-break on .bar h1
pat3 = re.compile(r"(\.bar\s+h1\s*\{[^}]*)(\})")
m3 = pat3.search(text2)
if m3:
    inner3 = m3.group(1)
    if "word-break" not in inner3:
        text2 = pat3.sub(lambda mm: mm.group(1) + ";word-break:break-word;overflow-wrap:anywhere" + mm.group(2), text2, count=1)
        print("[ok] .bar h1 CSS updated with word-break")
    else:
        print("[skip] .bar h1 already has word-break")
else:
    print("[miss] .bar h1 selector not found")

codecs.open(static_path, "w", encoding="utf-8").write(text2)
print("[ok] static/index.html final size: " + str(len(text2)))
print("[done] all Round-8 patches applied (" + str(count_hit) + " demobar hits)")
