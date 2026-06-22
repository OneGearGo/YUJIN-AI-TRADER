"""
CQRS 数据缓存池 — 精简版（ZMQ 替代 MT5 轮询后）

只保留缓存读写，MT5 轮询 daemon 已砍掉。
数据来源：ZMQ subscriber（EA push tick/bar）。
"""
import time
import threading
import logging
from typing import Dict, Any, Optional, List, Tuple

logger = logging.getLogger(__name__)


class DataPool:
    """纯缓存容器 — ZMQ subscriber 写入，routes / scanner 读取。"""

    def __init__(self):
        # (sym, tf) -> {"rows": [...], "ts": float, "last_kline_time": str, "valid": bool}
        self._cache: Dict[Tuple[str, str], Dict[str, Any]] = {}
        self._ticks: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.RLock()

    # ================================================================
    # 读取 API — routes / scanner / SSE 调
    # ================================================================

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

    def get_tick(self, sym: str) -> Optional[Dict[str, Any]]:
        """routes / scanner 读 · 最新 tick 价"""
        with self._lock:
            return self._ticks.get(sym)

    def get_rows_for_routes(self, sym: str, tf: str) -> List[Dict[str, Any]]:
        """fast API read · 返 rows · cache miss 返 []"""
        with self._lock:
            entry = self._cache.get((sym, tf))
            if entry is None or not entry.get("valid"):
                return []
            return list(entry["rows"])

    def aggregate(self, symbols: List[str], tfs: List[str]) -> Dict[str, Dict[str, Dict[str, Any]]]:
        """/api/run 拼 sym × tf 形状 · read-only"""
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

    def is_ready(self) -> bool:
        """无 daemon 永远 ready"""
        return True

    def health(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "is_ready": True,
                "cache_size": len(self._cache),
                "tick_count": len(self._ticks),
            }

    # ================================================================
    # ZMQ 写入 — zmq_subscriber 调
    # ================================================================

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


# ================================================================
# singleton · routes / ZMQ 共用
# ================================================================
_pool: Optional[DataPool] = None


def init_pool() -> DataPool:
    """创建或返回 singleton（无参数，不需要 bridge）"""
    global _pool
    if _pool is None:
        _pool = DataPool()
    return _pool


def get_pool() -> Optional[DataPool]:
    return _pool


def shutdown_pool(timeout: float = 6.0):
    """lifespan shutdown 调 · 清引用"""
    global _pool
    _pool = None
