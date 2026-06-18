"""
多品种多周期扫描器 — Phase 8 v6 救命药三(CQRS 解耦):

 · 加 async scan_all_async 提供  如 · 但  优先 data_pool.aggregate(syms, tfs)
 · data_pool 是  CQRS read side  · 一  10ms  返
 · data_pool cache miss  →  fallback bridge.copy_rates_async (inner 5s timeout)
 ·  用 serve ( fallback bridge 不 hang  · 大部分前  业务 由 data_pool 托  ·  slow                                                                                边  edge)
"""
import os
import time
import yaml
import asyncio
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional
import pandas as pd
import logging

logger = logging.getLogger(__name__)
CONFIG_DIR = Path(__file__).parent.parent / "config"
TIMEFRAMES = ["M5", "M15", "H1", "H4", "D1"]
DATA_MODE = os.getenv("MT5_DATA_MODE", "SHADOW").upper()
SCAN_COUNT_DEFAULT = int(os.getenv("MT5_SCAN_COUNT", "100"))
SCAN_CACHE_TTL_S = int(os.getenv("MT5_SCAN_CACHE_TTL_S", "30"))

_cache_lock: Optional[asyncio.Lock] = None
_sync_cache_lock = threading.Lock()
_cache: Dict[str, Dict[str, object]] = {
    "data": {},
    "ts": 0.0,
    "data_mode": None,
}


def _get_cache_lock() -> asyncio.Lock:
    global _cache_lock
    if _cache_lock is None:
        _cache_lock = asyncio.Lock()
    return _cache_lock


def load_symbols(bridge=None) -> List[str]:
    """
    加载品种列表。
    优先顺序:
      1. MT5 已连接 → 动态拉取 MT5 帐户内所有可交易品种
      2. config/symbols.yaml 存在 → 从 YAML 加载 23 预设品种
      3. 兜底 → 只扫 XAUUSD
    """
    # 优先: MT5 已连接 → 动态拉取
    if bridge is not None:
        try:
            mode = getattr(bridge, 'data_mode', 'SHADOW')
            if mode != 'SHADOW' and bridge.state.value == 'CONNECTED':
                mt5_syms = bridge.symbols_get_all()
                if mt5_syms:
                    MAX_SYMS = int(os.getenv("MT5_MAX_SYMBOLS", "60"))
                    if len(mt5_syms) > MAX_SYMS:
                        logger.info("load_symbols: MT5 返回 %d 品种, 截取前 %d 个",
                                    len(mt5_syms), MAX_SYMS)
                        mt5_syms = mt5_syms[:MAX_SYMS]
                    logger.info("load_symbols: 从 MT5 动态拉取 %d 品种", len(mt5_syms))
                    return mt5_syms
        except Exception as e:
            logger.warning("load_symbols: 从 MT5 拉取失败, 回退 YAML: %s", e)

    # 次选: 从 symbols.yaml 加载
    p = CONFIG_DIR / "symbols.yaml"
    if not p.exists():
        return ["XAUUSD"]
    with open(p, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    if not cfg or "symbols" not in cfg:
        return ["XAUUSD"]
    yaml_syms = [s["symbol"] for s in cfg["symbols"]]
    logger.info("load_symbols: 从 symbols.yaml 加载 %d 品种", len(yaml_syms))
    return yaml_syms


def _pick_source() -> str:
    return DATA_MODE


def scan_symbol(bridge, symbol: str, count: int = SCAN_COUNT_DEFAULT) -> Dict[str, Optional[pd.DataFrame]]:
    """sync fallback for tests/back-compat."""
    logger.debug("scan_symbol sync %s count=%d", symbol, count)
    result: Dict[str, Optional[pd.DataFrame]] = {}
    for tf in TIMEFRAMES:
        df = bridge.copy_rates(symbol, tf, count=count)
        result[tf] = df
    return result


async def scan_symbol_async(
    bridge, symbol: str, count: int = SCAN_COUNT_DEFAULT,
) -> Dict[str, Optional[pd.DataFrame]]:
    """async version — tests/back-compat."""
    logger.debug("scan_symbol_async %s count=%d", symbol, count)
    result: Dict[str, Optional[pd.DataFrame]] = {}
    for tf in TIMEFRAMES:
        df = await bridge.copy_rates_async(symbol, tf, count=count, timeout=5.0)
        result[tf] = df
    return result


# ============================================================
# v6 CQRS scan_all_async —  优先  data_pool (native dict rows)
# ============================================================
async def scan_all_async(
    bridge,
    symbols: Optional[List[str]] = None,
    use_cache: bool = True,
    count: int = SCAN_COUNT_DEFAULT,
) -> Dict[str, Dict[str, Optional[pd.DataFrame]]]:
    """
    CQRS read path:

    1. 扫描器 _cache hit  → fast return (旧式 scanner._cache · cache hit (mmm))链路 )
    2.  data_pool (CQRS singleton 后台 daemon pull  → live MT5   )_加载 rows
        · valid=True  → dict → pandas DataFrame (read shape 不  )
        · valid=False → fallback  bridge.copy_rates_async (最后  catch)
    3. 写回 _cache( 下  次 cache hit 走快速 )
    """
    if symbols is None:
        symbols = load_symbols()

    # 1. _cache hit fast-path
    lock = _get_cache_lock()
    now = time.time()
    if use_cache:
        async with lock:
            if (
                _cache["data"]
                and (now - _cache["ts"]) < SCAN_CACHE_TTL_S
                and _cache["data_mode"] == DATA_MODE
            ):
                logger.info("scan_all _cache hit age=%.1fs · %d sym",
                            now - _cache["ts"], len(symbols))
                return {
                    s: _cache["data"].get(s, {tf: None for tf in TIMEFRAMES})
                    for s in symbols
                }

    # 2. CQRS read-side (data_pool)
    logger.info("scan_all CQRS read · %d sym × %d tf", len(symbols), len(TIMEFRAMES))
    started = time.time()
    fresh: Dict[str, Dict[str, Optional[pd.DataFrame]]] = {}
    pool_data_count = 0
    fallback_count = 0

    # lazy import (avoid circular)
    try:
        from .data_pool import get_pool
        pool = get_pool()
    except Exception:
        pool = None

    for sym in symbols:
        fresh[sym] = {}
        for tf in TIMEFRAMES:
            df = None
            # 优先 CQRS data_pool
            if pool is not None and pool.is_ready():
                rows = pool.get_rows_for_routes(sym, tf)
                if rows:
                    df = _rows_to_dataframe(rows)
                    if df is not None and len(df) > 0:
                        pool_data_count += 1
            # fallback  bridge 直接 fetch · inner 5S  timeout ( 不卡 event loop)
            if df is None or len(df) == 0:
                try:
                    df = await bridge.copy_rates_async(sym, tf, count=count, timeout=5.0)
                    if df is not None and len(df) > 0:
                        fallback_count += 1
                except Exception as e:
                    logger.debug("scan_all fallback %s %s fail: %s", sym, tf, e)
                    df = None
            fresh[sym][tf] = df

    elapsed = time.time() - started
    logger.info(
        "scan_all CQRS done · %.3fs · %d/%d from pool · %d/%d fallback · %d sym",
        elapsed,
        pool_data_count, len(symbols) * len(TIMEFRAMES),
        fallback_count, len(symbols) * len(TIMEFRAMES),
        len(symbols),
    )

    # 3. write-back to scanner _cache (老占下cache)
    async with lock:
        _cache["data"] = fresh
        _cache["ts"] = now
        _cache["data_mode"] = DATA_MODE
    return fresh


def _rows_to_dataframe(rows: List[Dict[str, Any]]) -> Optional["pd.DataFrame"]:
    """convert native rows (from data_pool) → pandas DataFrame shape.
    None if conversion failed (empty/garbage)."""
    if not rows:
        return None
    try:
        df = pd.DataFrame(rows)
        df["time"] = pd.to_datetime(df["time"], errors="coerce")
        df = df.dropna(subset=["time"])
        if len(df) == 0:
            return None
        return df
    except Exception as e:
        logger.warning("scan_all _rows_to_dataframe exception: %s", e)
        return None


# ============================================================
# sync version (tests/back-compat)
# ============================================================
def scan_all(
    bridge,
    symbols: Optional[List[str]] = None,
    use_cache: bool = True,
    count: int = SCAN_COUNT_DEFAULT,
) -> Dict[str, Dict[str, Optional[pd.DataFrame]]]:
    if symbols is None:
        symbols = load_symbols()
    now = time.time()
    if use_cache:
        with _sync_cache_lock:
            if (
                _cache["data"]
                and (now - _cache["ts"]) < SCAN_CACHE_TTL_S
                and _cache["data_mode"] == DATA_MODE
            ):
                logger.info("scan_all sync _cache hit age=%.1fs", now - _cache["ts"])
                return {
                    s: _cache["data"].get(s, {tf: None for tf in TIMEFRAMES})
                    for s in symbols
                }

    logger.info("scan_all sync fresh fetch %d sym", len(symbols))
    fresh: Dict[str, Dict[str, Optional[pd.DataFrame]]] = {}
    for sym in symbols:
        try:
            res: Dict[str, Optional[pd.DataFrame]] = {}
            for tf in TIMEFRAMES:
                res[tf] = bridge.copy_rates(sym, tf, count=count)
            fresh[sym] = res
        except Exception as e:
            logger.error("sync scan %s 异常: %s", sym, e)
            fresh[sym] = {tf: None for tf in TIMEFRAMES}
    with _sync_cache_lock:
        _cache["data"] = fresh
        _cache["ts"] = now
        _cache["data_mode"] = DATA_MODE
    return fresh


async def warm_cache_async(bridge, timeout: float = 10.0) -> int:
    """lifespan deprecated path · v6 dedups to data_pool.add_pool()"""
    logger.info("warm_cache_async deprecated · v6 里走 data_pool 冷启替换")
    return 0


def warm_cache(bridge) -> int:
    """sync deprecated · 不 调  Daemon 是  lifepan 提倔 Q"""
    return 0
