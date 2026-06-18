#!/usr/bin/env python
"""
Phase 10 单元测试 — 直接 python 执行 (绕过 pytest 环境兼容性问题)
测试: scanner.load_symbols(bridge), routes_screen._load_sym_configs(), _evaluate_results()
"""
import sys, os, time, tempfile, json

# === Setup env like conftest ===
os.environ["MT5_DATA_MODE"] = "SHADOW"
os.environ["LIVE_TRADING_DISABLED"] = "true"
os.environ["MT5_LOGIN"] = "0"
os.environ["MT5_PASSWORD"] = ""
os.environ["MT5_SERVER"] = ""

sys.path.insert(0, r"F:/yujin-mt5")

# Fake MetaTrader5 module
import types as _types
fake_mt5 = _types.ModuleType("MetaTrader5")
fake_mt5.TIMEFRAME_M5 = "M5"
fake_mt5.TIMEFRAME_H1 = "H1"
fake_mt5.TIMEFRAME_H4 = "H4"
fake_mt5.TIMEFRAME_D1 = "D1"
fake_mt5.ORDER_TYPE_BUY = 0
fake_mt5.ORDER_TYPE_SELL = 1
fake_mt5.ORDER_TIME_GTC = 0
fake_mt5.ORDER_FILLING_IOC = 1
fake_mt5.TRADE_ACTION_DEAL = 2
fake_mt5.TRADE_RETCODE_DONE = 10009
fake_mt5.initialized = False

class FakeInfo:
    def __init__(self):
        self.connected = True
        self.name = "FAKE-MT5"

class FakeSymbolInfo:
    name = ""
    point = 0.01
    digits = 5
    spread = 10
    volume_min = 0.01
    volume_max = 100.0
    volume_step = 0.01
    trade_contract_size = 100000
    trade_mode = 4

def _fake_symbols_get():
    """Return all available symbols in account 1049211 simulation."""
    import types
    symbols_data = {
        "EURUSD": {"digits":5,"spread":13,"volume_step":0.01,"trade_contract_size":100000,"path":"Forex\\Major"},
        "GBPUSD": {"digits":5,"spread":15,"volume_step":0.01,"trade_contract_size":100000,"path":"Forex\\Major"},
        "USDJPY": {"digits":3,"spread":18,"volume_step":0.01,"trade_contract_size":100000,"path":"Forex\\Major"},
        "XAUUSD": {"digits":2,"spread":21,"volume_step":0.01,"trade_contract_size":100,"path":"CFDs\\Metal"},
        "NAS100": {"digits":2,"spread":80,"volume_step":0.1,"trade_contract_size":1,"path":"CFDs\\Indices"},
        "BTCUSD": {"digits":2,"spread":1703,"volume_step":0.01,"trade_contract_size":1,"path":"CFDs\\Crypto"},
    }
    result = []
    for name, info in symbols_data.items():
        si = types.SimpleNamespace()
        si.name = name
        si.digits = info["digits"]
        si.spread = info["spread"]
        si.volume_step = info["volume_step"]
        si.trade_contract_size = info["trade_contract_size"]
        si.trade_mode = 4  # SYMBOL_TRADE_MODE_FULL
        si.path = info["path"]
        result.append(si)
    return tuple(result)

fake_mt5.initialize = lambda **kw: True
fake_mt5.shutdown = lambda: None
fake_mt5.terminal_info = lambda: FakeInfo()
fake_mt5.symbol_info = lambda s: FakeSymbolInfo()
fake_mt5.symbols_get = _fake_symbols_get

sys.modules["MetaTrader5"] = fake_mt5

# === Mock classes ===
class MockBridge:
    """Lightweight MT5Bridge mock."""
    def __init__(self, data_mode="SHADOW", state="DISCONNECTED", symbols=None):
        self._data_mode = data_mode
        self._state_str = state
        self._symbols = symbols if symbols is not None else ["EURUSD","GBPUSD","USDJPY","XAUUSD"]
        self._reconnect_count = 0
        self._last_heartbeat = time.time()

    @property
    def data_mode(self): return self._data_mode
    @property
    def state(self):
        class _S: value = self._state_str
        return _S()
    @property
    def reconnect_count(self): return self._reconnect_count
    @property
    def last_heartbeat(self): return self._last_heartbeat
    def symbols_get_all(self): return list(self._symbols)
    async def heartbeat_ping_async(self, timeout=3.0): return True

class MockBridgeError(MockBridge):
    def symbols_get_all(self):
        raise RuntimeError("MT5 not available")

# === Test helpers ===
PASS = 0
FAIL = 0

def assert_eq(a, b, msg=""):
    global PASS, FAIL
    if a == b:
        PASS += 1
        print(f"  [PASS] {msg}")
    else:
        FAIL += 1
        print(f"  [FAIL] {msg}: expected {b!r}, got {a!r}")

def assert_in(item, container, msg=""):
    global PASS, FAIL
    if item in container:
        PASS += 1
        print(f"  [PASS] {msg}")
    else:
        FAIL += 1
        print(f"  [FAIL] {msg}: {item!r} not in {container!r}")

def assert_true(val, msg=""):
    global PASS, FAIL
    if val:
        PASS += 1
        print(f"  [PASS] {msg}")
    else:
        FAIL += 1
        print(f"  [FAIL] {msg}: expected True, got {val}")

# ============================================================
# TEST: scanner.load_symbols(bridge)
# ============================================================
def test_load_symbols():
    print("\n=== scanner.load_symbols(bridge) ===")
    from core.scanner import load_symbols

    # 1. No bridge → YAML symbols
    syms = load_symbols()
    assert_true(len(syms) >= 1, "no bridge returns symbols")
    print(f"    count={len(syms)}, first={syms[0]}")

    # 2. bridge=None → YAML symbols
    syms = load_symbols(bridge=None)
    assert_true(len(syms) >= 1, "bridge=None returns symbols")

    # 3. SHADOW mode → ignores bridge, returns YAML
    b_shadow = MockBridge(data_mode="SHADOW", state="DISCONNECTED")
    syms = load_symbols(bridge=b_shadow)
    assert_true(len(syms) >= 1, "SHADOW mode returns YAML symbols")
    assert_true(len(syms) >= 20, f"YAML has 40+ syms, got {len(syms)}")

    # 4. LIVE + CONNECTED → returns MT5 symbols
    b_live = MockBridge(data_mode="LIVE", state="CONNECTED",
                        symbols=["EURUSD","GBPUSD","USDJPY","XAUUSD","NAS100"])
    syms = load_symbols(bridge=b_live)
    assert_eq(syms, ["EURUSD","GBPUSD","USDJPY","XAUUSD","NAS100"],
              "LIVE+CONNECTED returns bridge symbols")

    # 5. LIVE_DRY_RUN + CONNECTED → returns MT5 symbols
    b_dry = MockBridge(data_mode="LIVE_DRY_RUN", state="CONNECTED",
                       symbols=["XAUUSD","EURUSD"])
    syms = load_symbols(bridge=b_dry)
    assert_eq(sorted(syms), ["EURUSD","XAUUSD"],
              "LIVE_DRY_RUN+CONNECTED returns bridge symbols")

    # 6. LIVE + RECONNECTING → falls back to YAML
    b_rec = MockBridge(data_mode="LIVE", state="RECONNECTING")
    syms = load_symbols(bridge=b_rec)
    assert_true(len(syms) >= 20, "RECONNECTING falls back to YAML")

    # 7. Bridge returns empty list → falls back to YAML
    b_empty = MockBridge(data_mode="LIVE", state="CONNECTED", symbols=[])
    syms = load_symbols(bridge=b_empty)
    assert_true(len(syms) >= 20, "empty bridge symbols falls back to YAML")

    # 8. Bridge raises error → falls back to YAML
    b_err = MockBridgeError(data_mode="LIVE", state="CONNECTED")
    syms = load_symbols(bridge=b_err)
    assert_true(len(syms) >= 20, "bridge error falls back to YAML")

    # 9. MT5_MAX_SYMBOLS truncation
    os.environ["MT5_MAX_SYMBOLS"] = "2"
    b_trunc = MockBridge(data_mode="LIVE", state="CONNECTED",
                         symbols=["EURUSD","GBPUSD","USDJPY","XAUUSD"])
    syms = load_symbols(bridge=b_trunc)
    assert_eq(len(syms), 2, "MT5_MAX_SYMBOLS=2 truncates to 2")
    del os.environ["MT5_MAX_SYMBOLS"]

    print(f"  => Result: {PASS}/{PASS+FAIL} passed (so far)")


# ============================================================
# TEST: routes_screen._load_sym_configs()
# ============================================================
def test_load_sym_configs():
    print("\n=== routes_screen._load_sym_configs() ===")
    from api.routes_screen import _load_sym_configs

    # Reset cache
    import api.routes_screen as rs
    rs._SYM_CONFIG_CACHE = None

    configs = _load_sym_configs()
    assert_true(isinstance(configs, dict), "returns dict")
    assert_true(len(configs) >= 1, "has symbols")
    print(f"    loaded {len(configs)} symbol configs")

    if "XAUUSD" in configs:
        xau = configs["XAUUSD"]
        assert_eq(xau["category"], "commodity", "XAUUSD category=commodity")
        assert_in("spread_max", xau, "XAUUSD has spread_max")
        assert_in("pip_value", xau, "XAUUSD has pip_value")
        assert_in("lot_step", xau, "XAUUSD has lot_step")
        assert_in("decimals", xau, "XAUUSD has decimals")

    if "EURUSD" in configs:
        eur = configs["EURUSD"]
        assert_eq(eur["category"], "forex", "EURUSD category=forex")

    # Test caching — second call should return same object
    configs2 = _load_sym_configs()
    assert_true(configs is configs2, "second call returns cached")

    print(f"  => Result: {PASS}/{PASS+FAIL} passed (so far)")


# ============================================================
# TEST: routes_screen._evaluate_results()
# ============================================================
def test_evaluate_results():
    print("\n=== routes_screen._evaluate_results() ===")
    from api.routes_screen import _evaluate_results
    import pandas as pd

    # Mock strategy.evaluate via the module it's imported from
    import core.strategy as strategy_mod
    original_evaluate = strategy_mod.evaluate

    class FakeScanResult:
        status = "action"
        died = None
        conv = 0.88
        priority = 76
        spread = 12
        gap_pct = 0.1
        ema_align = True
        fvg = True
        sweep = False
        bos = "bull"
        lots = 0.05
        sl = 2340.0
        tp = (2360.0, 2380.0)
        exit_plan = "SL -0.5% · TP 1:2"
        thesis = "H4 BOS + M5 displacement, DXY weakening supports gold"
        reason = "EMA50>EMA200 on H1, FVG on H4, sweep of Asian low"

    mock_results = {
        "XAUUSD": {
            "M5": pd.DataFrame({"time": [1,2,3], "close": [2400,2401,2402]}),
            "H1": pd.DataFrame({"time": [1,2,3], "close": [2390,2395,2400]}),
            "H4": pd.DataFrame({"time": [1,2,3], "close": [2380,2390,2400]}),
        }
    }

    def mock_evaluate(sym, data, config):
        return FakeScanResult()

    strategy_mod.evaluate = mock_evaluate
    result = _evaluate_results(mock_results)
    strategy_mod.evaluate = original_evaluate

    assert_true(isinstance(result, dict), "returns dict")
    assert_in("XAUUSD", result, "XAUUSD in results")

    entry = result["XAUUSD"]
    assert_eq(entry["sym"], "XAUUSD", "sym=XAUUSD")
    assert_eq(entry["category"], "commodity", "category=commodity (from YAML)")
    assert_eq(entry["status"], "action", "status=action")
    assert_eq(entry["conv"], 0.88, "conv=0.88")
    assert_eq(entry["priority"], 76, "priority=76")
    assert_eq(entry["ema_align"], True, "ema_align=True")
    assert_eq(entry["fvg"], True, "fvg=True")
    assert_eq(entry["bos"], "bull", "bos=bull")
    assert_eq(entry["lots"], 0.05, "lots=0.05")
    assert_eq(entry["sl"], 2340.0, "sl=2340.0")
    assert_eq(entry["tp"], 2360.0, "tp=2360.0 (first of tuple)")
    assert_in("thesis", entry, "thesis field exists")
    assert_in("reason", entry, "reason field exists")
    assert_in("exit_plan", entry, "exit_plan field exists")

    # Test empty results
    empty = _evaluate_results({})
    assert_eq(empty, {}, "empty dict input -> empty output")

    # Test None results
    none_result = _evaluate_results(None)
    assert_eq(none_result, {}, "None input -> empty output")

    # Test evaluate error → error entry
    def mock_evaluate_error(sym, data, config):
        raise ValueError("Insufficient data")

    strategy_mod.evaluate = mock_evaluate_error
    error_result = _evaluate_results(mock_results)
    strategy_mod.evaluate = original_evaluate

    assert_in("XAUUSD", error_result, "error entry has XAUUSD")
    assert_eq(error_result["XAUUSD"]["status"], "error", "status=error on evaluate failure")

    print(f"  => Result: {PASS}/{PASS+FAIL} passed (so far)")


# ============================================================
# TEST: symbols_get_all (via bridge.symbols_get_all)
# ============================================================
def test_symbols_get_all():
    print("\n=== mt5_bridge.symbols_get_all() ===")
    from core.mt5_bridge import bridge

    # Reset bridge state for test
    from core.mt5_bridge import MT5State
    bridge._ro = False
    bridge._tr = False
    bridge._state = MT5State.DISCONNECTED

    # symbols_get_all should try init_readonly → with FakeMT5 it will succeed
    result = bridge.symbols_get_all()
    assert_true(isinstance(result, list), "returns list")
    assert_true(len(result) >= 1, f"has symbols: {len(result)}")
    assert_in("EURUSD", result, "EURUSD in symbols")

    # Async version
    import asyncio
    async def test_async():
        result2 = await bridge.symbols_get_all_async()
        assert_true(len(result2) >= 1, f"async returns {len(result2)} symbols")
        print("  [PASS] symbols_get_all_async OK")

    asyncio.run(test_async())

    print(f"  => Result: {PASS}/{PASS+FAIL} passed (so far)")


# ============================================================
# TEST: _evaluate_results with category field
# ============================================================
def test_evaluate_results_category():
    print("\n=== _evaluate_results() category field ===")
    from api.routes_screen import _evaluate_results
    import pandas as pd
    import core.strategy as strategy_mod
    original_evaluate = strategy_mod.evaluate

    class FakeResult:
        status = "watch"
        died = 3
        conv = 0.6
        priority = 50
        spread = 5
        gap_pct = 0.0
        ema_align = False
        fvg = True
        sweep = True
        bos = "none"
        lots = 0
        sl = 0
        tp = ()
        exit_plan = ""
        thesis = ""
        reason = ""

    def mock_evaluate(sym, data, config):
        return FakeResult()

    strategy_mod.evaluate = mock_evaluate

    mock_data = {
        "BTCUSD": {
            "M5": pd.DataFrame({"time":[1],"close":[50000]}),
            "H1": pd.DataFrame({"time":[1],"close":[50000]}),
            "H4": pd.DataFrame({"time":[1],"close":[50000]}),
        }
    }

    result = _evaluate_results(mock_data)
    strategy_mod.evaluate = original_evaluate

    if "BTCUSD" in result:
        assert_eq(result["BTCUSD"]["category"], "crypto",
                  "BTCUSD category=crypto from symbols.yaml")

    print(f"  => Result: {PASS}/{PASS+FAIL} passed (so far)")


# ============================================================
# Main
# ============================================================
if __name__ == "__main__":
    print("=" * 60)
    print("Phase 10 单元测试")
    print("=" * 60)

    test_load_symbols()
    test_load_sym_configs()
    test_evaluate_results()
    test_evaluate_results_category()
    test_symbols_get_all()

    print()
    print("=" * 60)
    print(f"RESULT: {PASS}/{PASS+FAIL} passed, {FAIL} failed")
    print("=" * 60)
    if FAIL > 0:
        sys.exit(1)
    else:
        print("** ALL PHASE 10 TESTS PASSED!")
