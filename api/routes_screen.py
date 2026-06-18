"""
扫描路由 · Phase 8:从 bridge 读取数据 mode · 数据 shape 跟前 SHADOW 对齐
"""
from fastapi import APIRouter
from typing import Dict, Any

router = APIRouter(prefix="/api", tags=["screen"])


@router.post("/run")
async def run_scan() -> Dict[str, Any]:
    """触发全量扫描 · Phase 8:返 { data_mode, symbols, results, health }"""
    from core.scanner import scan_all, load_symbols
    from core.mt5_bridge import bridge
    symbols = load_symbols()
    results = scan_all(bridge, symbols)
    return {
        "data_mode": bridge.data_mode,
        "state": bridge.state.value,
        "symbol_count": len(symbols),
        "results": _summary(results),
        "health": {
            "heartbeat": bridge.heartbeat_ping(),
            "last_heartbeat": bridge.last_heartbeat,
            "reconnect_count": bridge.reconnect_count,
        },
    }


@router.get("/symbols")
async def get_symbols() -> Dict[str, Any]:
    """获取扫描品种列表"""
    from core.scanner import load_symbols
    syms = load_symbols()
    return {"count": len(syms), "symbols": syms}


def _summary(results) -> Dict[str, Dict[str, int]]:
    """将 DataFrame 折算成 {sym: {tf: row_count}} 摘要 · 网络负载小"""
    out = {}
    for sym, tfs in results.items():
        out[sym] = {tf: (0 if df is None else len(df)) for tf, df in tfs.items()}
    return out
