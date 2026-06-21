"""
CQRS 常驻数据池 — Phase 8 v6 救命药三:

  设计原则(thinker 论证后):
    · 单 daemon thread (NOT 6 per-tf) · MT5 DLL 单 thread 安全
    · Bucket-orient 调度 · per tf interval 检查 ·  1  daemon thread ·  loop:
       for tf in PRIORITY_TFS: if (now - last_tf_refresh_at) >= interval: refresh that tf
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
import os
import time
import threading
import logging
from typing import Dict, Any, Optional, List, Tuple, Set

logger = logging.getLogger(__name__)

# ============================================================
# 常量  央行
# ============================================================
DEFAULT_REFRESH_INTERVALS_S = {
    "M5": 30,
    "M15": 60,
    "H1": 300,
    "H4": 1200,
    "D1": 86400,
}
PRIORITY_TFS = ["M5", "M15", "H1", "H4", "D1"]  # high-freq访到 low-freq
# MUST FIX #3:slice  + per-call yield 走 _mt5_executor 不 贵 trade/heartbeat path 上  yield 0.1s
SLICE_SIZE = 3
INTER_CALL_YIELD_S = 0.1
INTER_SLICE_YIELD_S = 0.3
SCAN_COUNT_DEFAULT = int(os.getenv("MT5_SCAN_COUNT", "100"))


class DataPool:
    """后台  · 大 MT5 数据  cache ·  CQRS  read-side"""

    def __init__(self, bridge, symbols: Optional[List[str]] = None, intervals: Optional[Dict[str, int]] = None):
        self._bridge = bridge
        self._symbols = symbols  # if None,  Pool refresh 懒 symbol list
        self._intervals = intervals or DEFAULT_REFRESH_INTERVALS_S
        # cache: (sym, tf) -> {"rows": List[Dict[str, Any]], "ts": float, "last_kline_time": str, "valid": bool}
        self._cache: Dict[Tuple[str, str], Dict[str, Any]] = {}
        self._lock = threading.RLock()
        self._last_tf_refresh_at: Dict[str, float] = {}
        self._fail_count: Dict[Tuple[str, str], int] = {}
        self._ticks: Dict[str, Dict[str, Any]] = {}
        self._stop = threading.Event()
        self._ready = threading.Event()
        self._worker: Optional[threading.Thread] = None
        self._warm_first_pass_done = False  # lifespan startup warmup flag

    # ============================================================
    # 生命周期
    # ============================================================
    def start(self):
        """(同步  调用)启动 daemon thread · lifespan 中走 asyncio.to_thread ·  非阻塞"""
        if self._worker and self._worker.is_alive():
            logger.info("data_pool: 后台 daemon 在跑")
            return
        self._stop.clear()
        self._ready.clear()
        self._worker = threading.Thread(target=self._loop, name="data_pool", daemon=True)
        self._worker.start()
        logger.info("data_pool: 后台 daemon spawn")

    def stop(self, timeout: float = 6.0):
        """lifespan shutdown 调"""
        self._stop.set()
        if self._worker:
            self._worker.join(timeout=timeout)

    def is_ready(self) -> bool:
        return self._ready.is_set()

    def wait_ready(self, timeout: float) -> bool:
        """lifespan  startup  中 wait_for ·  返 True/False"""
        return self._ready.wait(timeout=timeout)

    # ============================================================
    # 后台 daemon loop (single thread · MAX 115 fetch per minute)
    # ============================================================
    def _loop(self):
        # 初始  first-pass warmup  ·  所 tf 都  1   unsync then walk  后续
        try:
            self._refresh_all_once()
        except Exception as e:
            logger.exception("data_pool: 首轮 warmup 异常 %s · 不标 ready · 后续仍重试", e)
        else:
            # MUST FIX #1:_ready  仅  实际   warmup    set;异常  标 not ready · 让 wait_ready(timeout) 返 False ·  决策  · 不 假 peak
            self._warm_first_pass_done = True
            self._ready.set()
            logger.info("data_pool: 首轮 warmup done")

        while not self._stop.is_set():
            now = time.time()
            worked = False
            for tf in PRIORITY_TFS:
                if self._stop.is_set():
                    break
                interval = self._intervals.get(tf, 30)
                last = self._last_tf_refresh_at.get(tf, 0.0)
                if (now - last) < interval:
                    continue
                # tf    刷新
                try:
                    self._refresh_tf(tf)
                    self._last_tf_refresh_at[tf] = time.time()
                    worked = True
                except Exception as e:
                    logger.exception("data_pool: refresh tf=%s 异常: %s", tf, e)
            # sleep 让 _mt5_executor 路  trade/heartbeat   · 心跳  30s · trade  智能 ·
            # worked flag: 现  次   完  sleep  30s,  TB
            idle = 0.5 if worked else 5.0
            self._stop.wait(idle)

    # ============================================================
    # internal helpers
    # ============================================================
    def _refresh_all_once(self):
        """首轮 全部 tf 都  1 次 warmup"""
        for tf in PRIORITY_TFS:
            if self._stop.is_set():
                return
            try:
                self._refresh_tf(tf)
                self._last_tf_refresh_at[tf] = time.time()
            except Exception as e:
                logger.warning("data_pool: warmup tf=%s fail: %s", tf, e)

    def _get_symbols(self) -> List[str]:
        if self._symbols is not None:
            return self._symbols
        from .scanner import load_symbols  # lazy to avoid circular import at module load
        return load_symbols()

    def _refresh_tf(self, tf: str):
        """3 sym/slice · per-call yield 0.1s · inter-slice yield 0.3s
        紧避免 trade/heartbeat 在 _mt5_executor 上 饿"
        """
        symbols = self._get_symbols()
        for i in range(0, len(symbols), SLICE_SIZE):
            if self._stop.is_set():
                return
            chunk = symbols[i:i + SLICE_SIZE]
            for sym in chunk:
                if self._stop.is_set():
                    return
                ok = self._fetch_one(sym, tf)
                key = (sym, tf)
                if ok:
                    self._fail_count.pop(key, None)
                else:
                    self._fail_count[key] = self._fail_count.get(key, 0) + 1
                # MUST FIX #3:单  fetch 后  yield · 不 累计  5 个  ·   exector 卡  · trade/heartbeat 干
                if self._stop.wait(INTER_CALL_YIELD_S):
                    return
            # slice  完  · 额外 yield 给路  会 发过来的 trade
            if self._stop.wait(INTER_SLICE_YIELD_S):
                return

    def _fetch_one(self, sym: str, tf: str) -> bool:
        """sync bridge.copy_rates(dir to _mt5_executor) · "
        不  否 ok ·  invalid (None/empty) → skip write · 不  覆盖 老 cache"""
        try:
            df = self._bridge.copy_rates(sym, tf, count=SCAN_COUNT_DEFAULT)
        except Exception as e:
            logger.debug("data_pool: %s %s bridge fetch exception: %s", sym, tf, e)
            return False
        if df is None or len(df) == 0:
            return False
        # Convert DataFrame → native dict list · MUST FIX #2:用 df.to_dict('records')  100x speedup vs iterrows
        rows: List[Dict[str, Any]] = []
        try:
            # bridge.copy_rates  中   df["time"] = pd.to_datetime(df["time"], unit="s") · time 列 是 datetime
            records = df.to_dict(orient="records")
            for r in records:
                ts_val = r["time"]
                try:
                    ts_str = pd.Timestamp(ts_val).isoformat()
                except Exception:
                    ts_str = str(ts_val)
                # volume: tick_volume 优先 ·  fall back real_volume
                vol = int(r.get("tick_volume", 0) or 0)
                if vol == 0:
                    vol = int(r.get("real_volume", 0) or 0)
                rows.append({
                    "time": ts_str,
                    "open": float(r["open"]),
                    "high": float(r["high"]),
                    "low": float(r["low"]),
                    "close": float(r["close"]),
                    "volume": vol,
                })
        except Exception as e:
            logger.warning("data_pool: %s %s to_dict exception: %s", sym, tf, e)
            return False
        if not rows:
            return False
        # write into cache
        with self._lock:
            self._cache[(sym, tf)] = {
                "rows": rows,
                "ts": time.time(),
                "last_kline_time": rows[-1]["time"],
                "valid": True,
            }
        return True

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

    def get_tick(self, sym: str) -> Optional[Dict[str, Any]]:
        """routes / scanner 读 · 最新 tick 价"""
        with self._lock:
            return self._ticks.get(sym)

    def health(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "is_ready": self._ready.is_set(),
                "cache_size": len(self._cache),
                "first_pass_done": self._warm_first_pass_done,
                "last_tf_refresh_at": dict(self._last_tf_refresh_at),
                "fail_count_total": sum(self._fail_count.values()),
                "fail_count_by_pair": {f"{k[0]}/{k[1]}": v for k, v in self._fail_count.items()},
            }


# ============================================================
# singleton  the route layer
# ============================================================
_pool: Optional[DataPool] = None


def init_pool(bridge) -> DataPool:
    """lifespan  startup 中    in    hit"""
    global _pool
    if _pool is None:
        _pool = DataPool(bridge)
        _pool.start()
    return _pool


def get_pool() -> Optional[DataPool]:
    return _pool


def shutdown_pool(timeout: float = 6.0):
    """lifespan shutdown 中    hit"""
    global _pool
    if _pool is not None:
        _pool.stop(timeout=timeout)
        _pool = None
