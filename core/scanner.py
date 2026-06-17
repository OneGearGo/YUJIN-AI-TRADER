"""
多品种多周期扫描器 -- 23 品种 x 5 周期
"""
import yaml
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime, timedelta, timezone
import pandas as pd
import logging

logger = logging.getLogger(__name__)
CONFIG_DIR = Path(__file__).parent.parent / "config"
TIMEFRAMES = ["M5", "M15", "H1", "H4", "D1"]

def load_symbols() -> List[str]:
    p = CONFIG_DIR / "symbols.yaml"
    if not p.exists(): return ["XAUUSD"]
    with open(p, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    if not cfg or "symbols" not in cfg: return ["XAUUSD"]
    return [s["symbol"] for s in cfg["symbols"]]

def scan_symbol(bridge, symbol: str) -> Dict[str, Optional[pd.DataFrame]]:
    result = {}
    for tf in TIMEFRAMES:
        df = bridge.copy_rates(symbol, tf, count=200)
        result[tf] = df
    return result

def scan_all(bridge, symbols: Optional[List[str]] = None) -> Dict[str, Dict[str, Optional[pd.DataFrame]]]:
    if symbols is None: symbols = load_symbols()
    results = {}
    for sym in symbols:
        try:
            results[sym] = scan_symbol(bridge, sym)
        except Exception as e:
            logger.error("扫描 %s 异常: %s", sym, e)
            results[sym] = {tf: None for tf in TIMEFRAMES}
    logger.info("扫描完成: %d 品种 x %d 周期", len(symbols), len(TIMEFRAMES))
    return results
