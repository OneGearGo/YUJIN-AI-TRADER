"""
Phase 8 pytest conftest — fake_mt5 fixture monkeypatch 全局 MetaTrader5
"""
import os
import sys
import pathlib
import pytest


@pytest.fixture(autouse=True)
def _project_root(monkeypatch, tmp_path):
    """设置项目根到 sys.path (tests 跑在 phase 8 前后隔离)"""
    root = pathlib.Path('/f/yujin-mt5')
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    monkeypatch.setenv("MT5_DATA_MODE", "SHADOW")  # 默认 SHADOW 避免 启动 MT5
    monkeypatch.setenv("LIVE_TRADING_DISABLED", "true")
    monkeypatch.setenv("MT5_LOGIN", "0")
    monkeypatch.setenv("MT5_PASSWORD", "")
    monkeypatch.setenv("MT5_SERVER", "")
    yield


class FakeMT5:
    """Global fake MetaTrader5 module for tests"""
    TIMEFRAME_M5 = "M5"
    TIMEFRAME_M15 = "M15"
    TIMEFRAME_H1 = "H1"
    TIMEFRAME_H4 = "H4"
    TIMEFRAME_D1 = "D1"
    ORDER_TYPE_BUY = 0
    ORDER_TYPE_SELL = 1
    ORDER_TIME_GTC = 0
    ORDER_FILLING_IOC = 1
    TRADE_ACTION_DEAL = 2
    TRADE_RETCODE_DONE = 10009

    initialized = False
    last_error = lambda: "fake error"
    _rates = {}

    def initialize(**kwargs):
        FakeMT5.initialized = True
        return True

    def shutdown():
        FakeMT5.initialized = False

    def terminal_info():
        class Info:
            connected = True
            name = "FAKE-MT5"
        return Info()

    def symbol_info(symbol):
        class Info:
            name = symbol
            point = 0.01
            digits = 2
            spread = 5
            volume_min = 0.01
            volume_max = 100.0
            volume_step = 0.01
            trade_contract_size = 100
            trade_mode = 4
        return Info()

    def symbol_info_tick(symbol):
        class Tick:
            ask = 2400.50
            bid = 2400.30
        return Tick()

    def copy_rates_from_pos(symbol, tf, pos, count):
        # 生成假 K 线 · 返 dict-shaped row 让 pd.DataFrame(rates) 创建以列 名  式
        # 以 MT5  SDK real 名 · time/open/high/low/close/tick_volume/spread/real_volume
        import time as _t
        now = int(_t.time())
        rows = []
        for i in range(count):
            rows.append({
                "time": now - i * 900,
                "open": 2400.0 + i * 0.5,
                "high": 2400.5 + i * 0.5,
                "low": 2399.5 + i * 0.5,
                "close": 2400.2 + i * 0.5,
                "tick_volume": 1000,
                "spread": 0,
                "real_volume": 0,
            })
        return tuple(rows)

    def account_info():
        class Info:
            login = 12345678
            balance = 10000.0
            equity = 10000.0
            margin = 0.0
            free_margin = 10000.0
            leverage = 100
            server = "FAKE"
        return Info()

    def positions_get(symbol=None, ticket=None):
        return None

    def last_error():
        return "ok"


@pytest.fixture(autouse=True)
def _fake_mt5(monkeypatch):
    """Phase 8 fixture — replace MetaTrader5 module globally via sys.modules.

    pytest 7+ does not allow monkeypatch.setattr with bare module name
    (must be absolute path). Use sys.modules override instead.
    """
    import sys as _sys
    _sys.modules["MetaTrader5"] = FakeMT5
    monkeypatch.setattr(_sys, "modules", {**_sys.modules, "MetaTrader5": FakeMT5})
    yield
