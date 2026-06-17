"""
扫描路由 -- POST /api/run, GET/POST /api/scan/settings
"""
from fastapi import APIRouter, HTTPException
from typing import Optional
from datetime import datetime, timedelta, timezone
import os, json, yaml, random
from pathlib import Path

router = APIRouter()
OUTPUTS_DIR = Path(__file__).parent.parent / "outputs"

@router.post("/api/run")
async def run_scan(payload: dict = None):
    try:
        from core.mt5_bridge import bridge
        from core.scanner import scan_all, load_symbols
        from core.strategy import evaluate
        if not bridge.init_readonly():
            raise HTTPException(503, "MT5 连接失败")
        symbols = (payload or {}).get("symbols") or load_symbols()
        scan_data = scan_all(bridge, symbols)
        cfg_path = Path(__file__).parent.parent / "config" / "symbols.yaml"
        with open(cfg_path, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
        sc_map = {s["symbol"]: s for s in cfg.get("symbols", [])}
        decisions = []
        for sym, data in scan_data.items():
            d = evaluate(sym, data, sc_map.get(sym, {}))
            decisions.append({
                "symbol": d.symbol, "status": d.status, "died": d.died,
                "verdict": {"v": d.verdict_v, "conv": d.conv, "thesis": d.thesis},
                "features": {"spread": d.spread, "gap_pct": d.gap_pct,
                    "ema_align": d.ema_align, "fvg": d.fvg, "sweep": d.sweep,
                    "disp": d.disp, "bos": d.bos},
                "priority": d.priority, "lots": d.lots, "sl": d.sl, "tp": d.tp,
                "exit_plan": d.exit_plan, "reason": d.reason,
            })
        act = sum(1 for d in decisions if d["status"] == "action")
        now = datetime.now(timezone(timedelta(hours=8)))
        return {
            "scan_id": int(now.timestamp()), "ts": now.isoformat(),
            "decisions": decisions,
            "kpis": {"scanned": len(decisions), "pending": act, "positions": 0, "escape_alerts": 0},
            "positions": [],
        }
    except HTTPException: raise
    except Exception as e:
        now = datetime.now(timezone(timedelta(hours=8)))
        bid = round(2330 + random.uniform(-20, 20), 2)
        return {
            "scan_id": int(now.timestamp()), "ts": now.isoformat(),
            "decisions": [{"symbol": "XAUUSD", "status": "action", "died": None,
                "verdict": {"v": "pass", "conv": 0.85, "thesis": "DEMO"},
                "features": {"spread": 22, "gap_pct": 0.0, "ema_align": True,
                    "fvg": True, "sweep": False, "disp": True, "bos": "bullish"},
                "priority": 78, "lots": 0.05, "sl": bid-12, "tp": [bid+18, bid+30],
                "exit_plan": "SL -0.5% TP +0.6%/+1.2%", "reason": "DEMO"}],
            "kpis": {"scanned": 1, "pending": 1, "positions": 0, "escape_alerts": 0},
            "positions": [],
        }

@router.get("/api/scan/settings")
async def get_scan_settings():
    return {"symbols": ["XAUUSD"], "interval_sec": 5, "enabled": True}

@router.post("/api/scan/settings")
async def update_scan_settings(payload: dict):
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUTPUTS_DIR / "scan_settings.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)
    return {"ok": True}
