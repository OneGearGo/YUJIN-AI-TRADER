"""
DataPool 单元测试 — Phase 8 v6 救命药三:

验证:
1. 启/停 lifecycle
2. cache write:bridge.fetch()返 fake DF → writer  写 native dict list
3. cache read:get / get_rows_for_routes / aggregate  shape  · thread-safe
4. invalid data skip:bridge.fetch() 返 None  ·  cache 不  覆盖
5. stale detection:age_s 作为 field
6. health snapshot:is_ready · cache_size · fail_count
"""
import threading
import time
import pytest


# ============================================================
# Helpers
# ============================================================
@pytest.fixture
def fresh_bridge(monkeypatch):
    from core import mt5_bridge as bridge_mod
    b = bridge_mod.bridge
    b._ro = True
    b._tr = False
    b._state = bridge_mod.MT5State.CONNECTED
    b._last_heartbeat = time.time()
    b._reconnect_count = 0
    yield b
    b._ro = False


@pytest.fixture
def one_symbol(monkeypatch):
    """override scanner.load_symbols → 1 sym (XAUUSD) 快 warmup"""
    import core.scanner as scanner_mod
    monkeypatch.setattr(scanner_mod, "load_symbols", lambda: ["XAUUSD"])
    yield ["XAUUSD"]


def test_data_pool_start_and_stop_with_fake_mt5(fresh_bridge, one_symbol):
    """Daemon启后  set ready flag + 启 后  stop join"""
    from core.data_pool import DataPool, shutdown_pool, init_pool
    shutdown_pool()  # clean any prior

    pool = DataPool(fresh_bridge, symbols=one_symbol)
    pool.start()
    try:
        # wait for first-pass warmup
        ready = pool.wait_ready(timeout=10.0)
        assert ready
        assert pool.is_ready()
        # data should have been written for XAUUSD × M5..D1
        for tf in ("M5", "M15", "H1", "H4", "D1"):
            entry = pool.get("XAUUSD", tf)
            assert entry is not None
            assert entry["valid"] is True
            assert len(entry["rows"]) > 0
    finally:
        pool.stop(timeout=5.0)
    assert pool._worker is None or not pool._worker.is_alive()


def test_data_pool_get_returns_rows_after_first_pass(fresh_bridge, one_symbol):
    from core.data_pool import DataPool, shutdown_pool
    shutdown_pool()
    pool = DataPool(fresh_bridge, symbols=one_symbol)
    pool.start()
    try:
        assert pool.wait_ready(timeout=10)
        rows = pool.get_rows_for_routes("XAUUSD", "M5")
        assert isinstance(rows, list)
        assert len(rows) > 0
        # Each row必备 fields
        sample = rows[0]
        for k in ("time", "open", "high", "low", "close", "volume"):
            assert k in sample
    finally:
        pool.stop(timeout=5)


def test_data_pool_get_returns_none_for_missing(fresh_bridge, one_symbol):
    from core.data_pool import DataPool, shutdown_pool
    shutdown_pool()
    pool = DataPool(fresh_bridge, symbols=one_symbol)
    # 不 start · cache 为空
    assert pool.get("UNKNOWN", "M5") is None
    assert pool.get_rows_for_routes("UNKNOWN", "M5") == []


def test_data_pool_invalid_data_skip_no_overwrite(fresh_bridge, one_symbol, monkeypatch):
    """bridge.copy_rates 返回 None · _fetch_one return False · cache 不被  覆盖"""
    from core.data_pool import DataPool, shutdown_pool
    shutdown_pool()
    pool = DataPool(fresh_bridge, symbols=one_symbol)

    # 预  cache 写入 · → fake stale data
    real_rows = [{"time": "2024-01-01T00:00:00", "open": 100.0, "high": 101.0,
                  "low": 99.0, "close": 100.5, "volume": 1000}]
    with pool._lock:
        pool._cache[("XAUUSD", "M5")] = {
            "rows": real_rows, "ts": time.time(), "last_kline_time": "2024-01-01T00:00:00",
            "valid": True,
        }

    # 强  bridge.copy_rates 返 None ·  模拟 MT5  ·  将 fake bridge
    monkeypatch.setattr(fresh_bridge, "copy_rates", lambda sym, tf, count=100: None)

    # _fetch_one 返 False
    ok = pool._fetch_one("XAUUSD", "M5")
    assert ok is False

    # cache 仍  越  ·  不被  返回 None  ·  覆盖
    entry = pool.get("XAUUSD", "M5")
    assert entry["rows"] == real_rows


def test_data_pool_age_increases_over_time(fresh_bridge, one_symbol):
    from core.data_pool import DataPool, shutdown_pool
    shutdown_pool()
    pool = DataPool(fresh_bridge, symbols=one_symbol)
    # 预  写入 + 手动 设  ts 为 0.0  · → age = time.time()
    with pool._lock:
        pool._cache[("XAUUSD", "M5")] = {
            "rows": [], "ts": 0.0, "last_kline_time": None, "valid": True,
        }
    age = pool.get_age("XAUUSD", "M5")
    assert age is not None
    assert age > 1000  # ts=0 from 1970 = very old


def test_data_pool_aggregate_shape(fresh_bridge, one_symbol):
    from core.data_pool import DataPool, shutdown_pool
    shutdown_pool()
    pool = DataPool(fresh_bridge, symbols=one_symbol)
    pool.start()
    try:
        assert pool.wait_ready(timeout=10)
        agg = pool.aggregate(["XAUUSD"], ["M5", "H1", "D1"])
        assert "XAUUSD" in agg
        for tf in ("M5", "H1", "D1"):
            assert tf in agg["XAUUSD"]
            # valid OR not · 不   ·  shape 降 一
            assert "valid" in agg["XAUUSD"][tf]
            assert "age_s" in agg["XAUUSD"][tf]
            assert "rows" in agg["XAUUSD"][tf]
    finally:
        pool.stop(timeout=5)


def test_data_pool_health(fresh_bridge, one_symbol):
    from core.data_pool import DataPool, shutdown_pool
    shutdown_pool()
    pool = DataPool(fresh_bridge, symbols=one_symbol)
    h = pool.health()
    assert h["is_ready"] is False  # not started yet
    assert h["cache_size"] == 0
    assert h["first_pass_done"] is False

    pool.start()
    try:
        assert pool.wait_ready(timeout=10)
        h = pool.health()
        assert h["is_ready"] is True
        assert h["first_pass_done"] is True
        assert h["cache_size"] >= 5  # at least XAUUSD × 5 tf = 5 entries
    finally:
        pool.stop(timeout=5)


def test_data_pool_thread_safe_concurrent_reads(fresh_bridge, one_symbol):
    """Thread Safety:10 reader thread   lock  · 不 crash"""
    from core.data_pool import DataPool, shutdown_pool
    shutdown_pool()
    pool = DataPool(fresh_bridge, symbols=one_symbol)
    pool.start()
    try:
        assert pool.wait_ready(timeout=10)

        errors = []

        def reader():
            try:
                for _ in range(50):
                    pool.get("XAUUSD", "M5")
                    pool.get_rows_for_routes("XAUUSD", "H1")
                    pool.aggregate(["XAUUSD"], ["M5", "H1"])
                    pool.health()
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=reader) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert errors == [], f"concurrent reads raised: {errors}"
    finally:
        pool.stop(timeout=5)


def test_data_pool_rows_conversion_to_dataframe_shape():
    """verify _rows_to_dataframe from scanner yields correct pd.DataFrame shape"""
    from core.scanner import _rows_to_dataframe
    rows = [
        {"time": "2024-01-01T00:00:00", "open": 100.0, "high": 101.0,
         "low": 99.0, "close": 100.5, "volume": 100},
        {"time": "2024-01-01T00:05:00", "open": 100.5, "high": 101.5,
         "low": 100.0, "close": 101.0, "volume": 200},
    ]
    df = _rows_to_dataframe(rows)
    assert df is not None
    assert len(df) == 2
    assert "open" in df.columns
    assert "close" in df.columns
