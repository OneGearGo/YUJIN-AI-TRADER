"""MT5 \u2192 aitrader frontend row adapter."""
from __future__ import annotations
import asyncio
from pathlib import Path
from typing import Any, Mapping

REPO = Path(__file__).resolve().parent

DEFAULT_MT5_PROXY_SYMBOLS: list[str] = [
    "XAUUSD", "GBPUSD", "EURUSD", "USDJPY", "USDCAD",
    "AUDUSD", "NZDUSD", "CHFJPY", "EURJPY", "GBPJPY",
    "USDCHF", "BTCUSD", "ETHUSD", "US30", "NAS100", "SPX500", "UK100",
]

def _load_mt5_proxy_symbols() -> list[str]:
    try:
        import yaml
        with open(REPO / "config" / "symbols.yaml", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        lst = data.get("mt5_proxy_symbols")
        if isinstance(lst, list) and lst:
            return [str(x) for x in lst if isinstance(x, (str, int))]
    except Exception:
        pass
    return list(DEFAULT_MT5_PROXY_SYMBOLS)

MT5_PROXY_SYMBOLS: list[str] = _load_mt5_proxy_symbols()

def synth_price(symbol: str, last_close):
    if last_close and float(last_close) > 0:
        return round(float(last_close), 6)
    seed = 0
    for ch in symbol:
        seed = (seed * 131 + ord(ch)) & 0xFFFFFFFF
    return round(1000.0 + (seed % 5000) / 100.0, 6)

def map_mt5_to_aitrader(idx, mt_row, symbol, price):
    if not isinstance(mt_row, dict):
        mt_row = {}
    sym = (mt_row.get('sym') or symbol or '').strip()
    addr = ('MT5_' + sym) if sym else 'MT5_UNK'
    status_raw = (mt_row.get('status') or mt_row.get('action') or '').upper()
    if status_raw in ('OPEN', 'EXEC'):
        action = 'action'
    elif status_raw in ('HOLD', 'WARN', 'WAIT'):
        action = 'warn'
    else:
        action = 'reject'
    reason = mt_row.get('reason') or ''
    v = mt_row.get('verdict') or {}
    if isinstance(v, dict):
        vstr = v.get('verdict') or 'WARN'
        conv_v = float(v.get('conviction') or 0.5)
        crowd_v = v.get('crowdedness') or ('early' if conv_v > 0.7 else ('mid' if conv_v > 0.4 else 'late'))
        thr_v = v.get('thesis') or reason
    else:
        vstr = 'WARN'
        conv_v = 0.5
        crowd_v = 'late'
        thr_v = reason
    f = mt_row.get('features') or {}
    if not isinstance(f, dict):
        f = {}
    b = f.get('bundler')
    if b is True:
        bund_v = 1.0
    elif b is False:
        bund_v = 0.0
    else:
        try:
            bund_v = float(b or 0.0)
        except Exception:
            bund_v = 0.0
    smc_raw = f.get('sm_confluence')
    smc_v = float(smc_raw) if isinstance(smc_raw, (int, float)) else 0.0
    sd_raw = f.get('smart_degen')
    if isinstance(sd_raw, (int, float)):
        prio_v = float(sd_raw)
    else:
        try:
            prio_v = float(mt_row.get('priority') or 50.0)
        except Exception:
            prio_v = 50.0
    prio_int = max(0, min(99, int(prio_v)))
    try:
        size_v = float(mt_row.get('lots') or 0.01)
    except Exception:
        size_v = 0.01
    exit_obj = mt_row.get('exit_plan') or {}
    if not isinstance(exit_obj, dict):
        exit_obj = {}
    return {
        '_i': idx,
        'sym': sym,
        'inj': False,
        'addr': addr,
        'address': addr,
        'hp': bool(f.get('honeypot', False)),
        'ren': bool(f.get('renounced', True)),
        'bund': round(bund_v, 4),
        'dev': round(float(f.get('dev_hold') or 0.0), 4),
        'top10': round(float(f.get('top10') or 0.0), 4),
        'smc': round(smc_v, 2),
        'degen': float(f.get('smart_degen') or 0),
        'kol': float(f.get('renowned') or 0),
        'age': int(f.get('age_min') or 0),
        'crowd': crowd_v,
        'v': vstr,
        'conv': round(conv_v, 3),
        'status': action,
        'warn': reason[:200],
        'size': size_v,
        'died': reason,
        'exit': exit_obj,
        'exit_plan': exit_obj,
        'reason': reason,
        'sl': mt_row.get('sl') or (mt_row.get('exec') or {}).get('hard_sl') or 0,
        'tp': mt_row.get('tp') or (mt_row.get('exec') or {}).get('tp_ladder') or 0,
        'spread': mt_row.get('spread'),
        'gap_pct': mt_row.get('gap_pct'),
        'thesis': thr_v,
        'priority': prio_int,
        'symbol': sym,
    }

def _extract_last_close(scan_result, sym):
    if not isinstance(scan_result, dict):
        return None
    bundle = scan_result.get(sym)
    if not isinstance(bundle, dict):
        return None
    for tf in ("M5", "M15", "H1", "H4", "D1"):
        df = bundle.get(tf)
        if df is None:
            continue
        try:
            if hasattr(df, "iloc"):
                return float(df.iloc[-1]["close"])
            if isinstance(df, list) and df:
                return float(df[-1].get("close", 0) or 0)
            if isinstance(df, dict) and "close" in df:
                return float(df.get("close", 0) or 0)
        except Exception:
            continue
    return None

def build_scanner_payload(chain: str = "mt5") -> dict:
    scan_result = {}
    try:
        from core.scanner import scan_all_async
        try:
            loop = asyncio.get_running_loop()
            future = asyncio.run_coroutine_threadsafe(scan_all_async(MT5_PROXY_SYMBOLS), loop)
            scan_result = future.result(timeout=15) or {}
        except RuntimeError:
            scan_result = asyncio.run(scan_all_async(MT5_PROXY_SYMBOLS)) or {}
    except Exception:
        scan_result = {}
    strategy_evaluate = None
    try:
        from core.strategy import evaluate as strategy_evaluate
    except Exception:
        strategy_evaluate = None
    decisions = []
    for idx, sym in enumerate(MT5_PROXY_SYMBOLS):
        try:
            mt_row = (strategy_evaluate(scan_result, sym) if strategy_evaluate else {})
            if not isinstance(mt_row, dict):
                mt_row = {}
        except Exception:
            mt_row = {}
        close = _extract_last_close(scan_result, sym)
        decisions.append(map_mt5_to_aitrader(idx, mt_row, sym, price=close))
    return dict(
        decisions=decisions,
        portfolio=dict(
            open_positions=0, max_concurrent=10, total_exposure=0.0,
            realized_loss_today=0.0, kill_switch=False,
        ),
        positions=[],
    )
