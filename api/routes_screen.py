"""
扫描路由 · Phase 8 v4 · 救命药一:

  · /api/run  await scan_all_async ·  走 async ·
  · /api/symbols load_symbols  sync ·  fast
"""
from fastapi import APIRouter
from typing import Dict, Any

router = APIRouter(prefix="/api", tags=["screen"])


@router.post("/run")
async def run_scan() -> Dict[str, Any]:
    """触发全量扫描 · Phase 8 v4:await scan_all_async · 走 event loop · 卡"""
    from core.scanner import scan_all_async, load_symbols
    from core.mt5_bridge import bridge
    symbols = load_symbols()
    results = await scan_all_async(bridge, symbols)
    connected = await bridge.heartbeat_ping_async(timeout=3.0)
    return {
        "data_mode": bridge.data_mode,
        "state": bridge.state.value,
        "symbol_count": len(symbols),
        "results": _summary(results),
        "health": {
            "heartbeat": connected,
            "last_heartbeat": bridge.last_heartbeat,
            "reconnect_count": bridge.reconnect_count,
        },
    }


@router.get("/symbols")
async def get_symbols() -> Dict[str, Any]:
    from core.scanner import load_symbols
    syms = load_symbols()
    return {"count": len(syms), "symbols": syms}


def _summary(results) -> Dict[str, Dict[str, int]]:
    out: Dict[str, Dict[str, int]] = {}
    for sym, tfs in results.items():
        out[sym] = {tf: (0 if df is None else len(df)) for tf, df in tfs.items()}
    return out
