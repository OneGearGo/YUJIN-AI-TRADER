"""
多品种多周期扫描器 -- Phase 8:加 source 切换(SHADOW/LIVE_DRY_RUN/LIVE) · facade 转返一致 shape
"""
import os
import yaml
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime, timedelta, timezone
import pandas as pd
import logging

logger = logging.getLogger(__name__)
CONFIG_DIR = Path(__file__).parent.parent / "config"
TIMEFRAMES = ["M5", "M15", "H1", "H4", "D1"]
DATA_MODE = os.getenv("MT5_DATA_MODE", "SHADOW").upper()


def load_symbols() -> List[str]:
    p = CONFIG_DIR / "symbols.yaml"
    if not p.exists():
        return ["XAUUSD"]
    with open(p, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    if not cfg or "symbols" not in cfg:
        return ["XAUUSD"]
    return [s["symbol"] for s in cfg["symbols"]]


def _pick_source() -> str:
    """根据 MT5_DATA_MODE 返回 source 名 — facade 决策"""
    return DATA_MODE


def scan_symbol(bridge, symbol: str) -> Dict[str, Optional[pd.DataFrame]]:
    """单品种多周期扫描 · Phase 8 facade · MT5 失败时返 None per tf"""
    source = _pick_source()
    mode = getattr(bridge, "data_mode", "SHADOW")
    logger.debug("scan_symbol %s source=%s mode=%s", symbol, source, mode)
    result = {}
    for tf in TIMEFRAMES:
        df = bridge.copy_rates(symbol, tf, count=200)
        result[tf] = df
    return result


def scan_all(bridge, symbols: Optional[List[str]] = None) -> Dict[str, Dict[str, Optional[pd.DataFrame]]]:
    """所有品种 × 所有周期扫描 · 返 shape 与 SHADOW 一致(front 不动)"""
    if symbols is None:
        symbols = load_symbols()
    results = {}
    for sym in symbols:
        try:
            results[sym] = scan_symbol(bridge, sym)
        except Exception as e:
            logger.error("扫描 %s 异常: %s", sym, e)
            results[sym] = {tf: None for tf in TIMEFRAMES}
    logger.info(
        "扫描完成: %d 品种 × %d 周期 (data_mode=%s)",
        len(symbols), len(TIMEFRAMES), DATA_MODE,
    )
    return results
