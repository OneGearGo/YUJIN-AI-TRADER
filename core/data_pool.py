"""
CQRS 常驻数据池 — Phase 8 v6 救命药三:

  设计原则(thinker 论证后):
    · 单 daemon thread (NOT 6 per-tf) · MT5 DLL 单 thread 安全
    · Bucket-orient 调度 · per tf interval 检查 ·  1  daemon thread ·  loop:
    · Slice  → 5 sym yield 0.5s  ·  不 饿  trade/heartbeat 路  _mt5_executor
    · Storage 是 native [{time, open, high, low, close, volume}] dict  list · 不 缓存 pandas DataFrame
    · Invalid data (None/empty/NaN) → skip write ·  30s 同 wrong 老
    · Daemon thread  直接调 bridge.copy_rates(sync) · async wrapper
    · 首轮 warmup  lifespan 中 asyncio.to_thread(  赴  )  ·  wait_ready    限  10s
    · MT5 bridge down  → fetch 返 None ·  skip write ·  diag stale=True

 关键:
    /api/run 完全  与 MT5 解耦 ·  只读 data_pool.get(sym, tf) ·  cache hit 永  10ms
    bridge  ·  cache stale  ·  warning  不 fail
"""
import time
import threading
import logging
from typing import Dict, Any, Optional, List, Tuple

logger = logging.getLogger(__name__)

class DataPool:
    """后台  · 大 MT5 数据  cache ·  CQRS  read-side"""

    def __init__(self):
        # cache: (sym, tf) -> {"rows": List[Dict[str, Any]], "ts": float, "last_kline_time": str, "valid": bool}
        self._cache: Dict[Tuple[str, str], Dict[str, Any]] = {}
        self._lock = threading.RLock()
        self._last_tf_refresh_at: Dict[str, float] = {}
        self._fail_count: Dict[Tuple[str, str], int] = {}
        self._ticks: Dict[str, Dict[str, Any]] = {}

# ============================================================
    # API · scanner / routes 用 · fast read
    # ============================================================
    def get(self, sym: str, tf: str) -> Optional[Dict[str, Any]]:
        """返 cache entry 或 None · thread-safe"""
        with self._lock:
            entry = self._cache.get((sym, tf))
            if entry is None or not entry.get("valid"):
                return None
            return entry

    def get_age(self, sym: str, tf: str) -> Optional[float]:
        with self._lock:
            entry = self._cache.get((sym, tf))
            if entry is None:
                return None
            return time.time() - entry["ts"]

    def get_rows_for_routes(self, sym: str, tf: str) -> List[Dict[str, Any]]:
        """fast API read · 返 rows (献rate) ·  cache miss  返 []"""
        with self._lock:
            entry = self._cache.get((sym, tf))
            if entry is None or not entry.get("valid"):
                return []
            return list(entry["rows"])  # .copy 防 caller mutating

    def aggregate(self, symbols: List[str], tfs: List[str]) -> Dict[str, Dict[str, Dict[str, Any]]]:
        """/api/run  拼 sym × tf 形状 ·  read-only"""
        out: Dict[str, Dict[str, Dict[str, Any]]] = {}
        with self._lock:
            now = time.time()
            for sym in symbols:
                out[sym] = {}
                for tf in tfs:
                    entry = self._cache.get((sym, tf))
                    if entry is None or not entry.get("valid"):
                        out[sym][tf] = {"rows": [], "valid": False, "age_s": None, "last_kline_time": None}
                    else:
                        out[sym][tf] = {
                            "rows": list(entry["rows"]),
                            "valid": True,
                            "age_s": round(now - entry["ts"], 2),
                            "last_kline_time": entry["last_kline_time"],
                        }
        return out

    # ============================================================
    # ZMQ tick/bar 写入 (Phase 3)
    # ============================================================
    def update_tick(self, sym: str, bid: float, ask: float, time_str: str, spread: int):
        """ZMQ subscriber 调 · 更新最新 tick"""
        with self._lock:
            self._ticks[sym] = {
                "bid": bid, "ask": ask,
                "time": time_str, "spread": spread,
                "ts": time.time(),
            }

    def update_bar(self, sym: str, tf: str, bar: dict):
        """ZMQ subscriber 调 · 追加或更新已完成 bar"""
        with self._lock:
            key = (sym, tf)
            entry = self._cache.get(key)
            if entry is None:
                self._cache[key] = {
                    "rows": [bar],
                    "ts": time.time(),
                    "last_kline_time": bar.get("time", ""),
                    "valid": True,
                }
            else:
                rows = entry["rows"]
                if rows and rows[-1].get("time") == bar.get("time"):
                    rows[-1] = bar
                else:
                    rows.append(bar)
                entry["ts"] = time.time()
                entry["last_kline_time"] = bar.get("time", "")
                entry["valid"] = True
    def set_slice(self, sym: str, tf: str, rows: list):
        """ZMQ bar 调 · 按 time 合并追加/更新 k线切片，不替换整个列表"""
        with self._lock:
            key = (sym, tf)
            entry = self._cache.get(key)
            if entry is None:
                self._cache[key] = {
                    "rows": list(rows),
                    "ts": time.time(),
                    "last_kline_time": rows[-1]["time"] if rows else "",
                    "valid": True,
                }
            else:
                existing = entry["rows"]
                for bar in rows:
                    if existing and existing[-1].get("time") == bar.get("time"):
                        existing[-1] = bar
                    else:
                        existing.append(bar)
                entry["rows"] = existing
                entry["ts"] = time.time()
                entry["last_kline_time"] = existing[-1]["time"] if existing else ""
                entry["valid"] = True

    def get_tick(self, sym: str) -> Optional[Dict[str, Any]]:
        """routes / scanner 读 · 最新 tick 价"""
        with self._lock:
            return self._ticks.get(sym)

    def is_ready(self) -> bool:
        """always ready -- no daemon warmup"""
        return True

    def health(self) -> Dict[str, Any]:
        with self._lock:
            return {
                    "cache_size": len(self._cache),
                    "last_tf_refresh_at": dict(self._last_tf_refresh_at),
                "fail_count_total": sum(self._fail_count.values()),
                "fail_count_by_pair": {f"{k[0]}/{k[1]}": v for k, v in self._fail_count.items()},
            }


# ============================================================
# singleton  the route layer
# ============================================================
_pool: Optional["DataPool"] = None

def init_pool() -> "DataPool":
    global _pool
    if _pool is None:
        _pool = DataPool()
    return _pool

def get_pool() -> Optional["DataPool"]:
    global _pool
    if _pool is None:
        init_pool()
    return _pool
