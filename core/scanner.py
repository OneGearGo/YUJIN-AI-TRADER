"""
多品种多周期扫描器 — Phase 8 v4 · 救命药一 (fix-patched):

  ·  asyncio.Lock _cache_lock 走 async scan_all_async  锁
  ·  threading.Lock _sync_cache_lock 走 sync scan_all  · race safe
  ·  async scan_symbol_async ·  sync scan_symbol  test/upgrade fallback
"""
import os
import time
import yaml
import asyncio
import threading
from pathlib import Path
from typing import Dict, List, Optional
import pandas as pd
import logging

logger = logging.getLogger(__name__)
CONFIG_DIR = Path(__file__).parent.parent / "config"
TIMEFRAMES = ["M5", "M15", "H1", "H4", "D1"]
DATA_MODE = os.getenv("MT5_DATA_MODE", "SHADOW").upper()
SCAN_COUNT_DEFAULT = int(os.getenv("MT5_SCAN_COUNT", "100"))  # v3 EMA50 alignment safety
SCAN_CACHE_TTL_S = int(os.getenv("MT5_SCAN_CACHE_TTL_S", "30"))

_cache_lock: Optional[asyncio.Lock] = None  # lazy — bound to first caller's loop
_sync_cache_lock = threading.Lock()  # sync path 走 thread lock  race with async
_cache: Dict[str, Dict[str, object]] = {
    "data": {},
    "ts": 0.0,
    "data_mode": None,
}


def _get_cache_lock() -> asyncio.Lock:
    """Lazy init asyncio.Lock — bound to first caller's event loop."""
    global _cache_lock
    if _cache_lock is None:
        _cache_lock = asyncio.Lock()
    return _cache_lock


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
    return DATA_MODE


def scan_symbol(bridge, symbol: str, count: int = SCAN_COUNT_DEFAULT) -> Dict[str, Optional[pd.DataFrame]]:
    """sync 版本单品种多周期扫描 — test compatibility + sync fallback."""
    logger.debug("scan_symbol sync %s count=%d", symbol, count)
    result: Dict[str, Optional[pd.DataFrame]] = {}
    for tf in TIMEFRAMES:
        df = bridge.copy_rates(symbol, tf, count=count)
        result[tf] = df
    return result


async def scan_symbol_async(
    bridge, symbol: str, count: int = SCAN_COUNT_DEFAULT,
) -> Dict[str, Optional[pd.DataFrame]]:
    """async 版本单品种多周期扫描 — error返 None per tf."""
    logger.debug("scan_symbol_async %s count=%d", symbol, count)
    result: Dict[str, Optional[pd.DataFrame]] = {}
    for tf in TIMEFRAMES:
        df = await bridge.copy_rates_async(symbol, tf, count=count)
        result[tf] = df
    return result


async def scan_all_async(
    bridge,
    symbols: Optional[List[str]] = None,
    use_cache: bool = True,
    count: int = SCAN_COUNT_DEFAULT,
) -> Dict[str, Dict[str, Optional[pd.DataFrame]]]:
    """async 版本全扫描 — 事件循环 friendly; cache hit 不卡 event loop."""
    if symbols is None:
        symbols = load_symbols()
    lock = _get_cache_lock()
    now = time.time()
    if use_cache:
        async with lock:
            if (
                _cache["data"]
                and (now - _cache["ts"]) < SCAN_CACHE_TTL_S
                and _cache["data_mode"] == DATA_MODE
            ):
                logger.info(
                    "scan_all cache hit age=%.1fs · %d sym",
                    now - _cache["ts"], len(symbols),
                )
                return {
                    s: _cache["data"].get(s, {tf: None for tf in TIMEFRAMES})
                    for s in symbols
                }

    logger.info(
        "scan_all fresh fetch %d sym × %d tf × %d count",
        len(symbols), len(TIMEFRAMES), count,
    )
    started = time.time()
    fresh: Dict[str, Dict[str, Optional[pd.DataFrame]]] = {}
    for sym in symbols:
        try:
            fresh[sym] = await scan_symbol_async(bridge, sym, count=count)
        except Exception as e:
            logger.error("扫描 %s 异常: %s", sym, e)
            fresh[sym] = {tf: None for tf in TIMEFRAMES}
    elapsed = time.time() - started
    logger.info("scan_all done %.2fs %d sym", elapsed, len(symbols))
    async with lock:
        _cache["data"] = fresh
        _cache["ts"] = now
        _cache["data_mode"] = DATA_MODE
    return fresh


def scan_all(
    bridge,
    symbols: Optional[List[str]] = None,
    use_cache: bool = True,
    count: int = SCAN_COUNT_DEFAULT,
) -> Dict[str, Dict[str, Optional[pd.DataFrame]]]:
    """sync 版本全扫描 (供 tests + 后台 cron/style fallback) — 走 _sync_cache_lock."""
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
                logger.info("scan_all sync cache hit age=%.1fs", now - _cache["ts"])
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
    """lifespan 调用; 预扫描 with timeout degrade — 返回 sym 数."""
    logger.info("warm_cache_async starting timeout=%.1fs", timeout)
    started = time.time()
    try:
        async def _do_warm():
            return await scan_all_async(bridge, use_cache=False)

        fresh = await asyncio.wait_for(_do_warm(), timeout=timeout)
        elapsed = time.time() - started
        logger.info("warm_cache_async done %.2fs · %d sym", elapsed, len(fresh))
        return len(fresh)
    except (asyncio.TimeoutError, TimeoutError):
        logger.warning(
            "warm_cache_async timeout %.1fs · 降级 冷却启 · 首次 /api/run 可能 slow",
            timeout,
        )
        return 0
    except Exception as e:
        logger.error("warm_cache_async exception: %s · 降级 冷却启", e)
        return 0


def warm_cache(bridge) -> int:
    """sync 版本 (lifespan pre-async 用) — running loop 中直接拒返 0."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            logger.warning("warm_cache sync 在 running loop 中 — 返 0, async 版会用")
            return 0
    except RuntimeError:
        pass
    return len(scan_all(bridge, use_cache=False))
