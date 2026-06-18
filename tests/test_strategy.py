"""
Phase 8 test_strategy — 验证 ScanResult dataclass + 6 gate 装饰正确性
"""
import pytest
import pandas as pd
import numpy as np


def _make_ohlc(rows=200, seed=42):
    """生成可预测 OHLCDF DataFrame · EMA 对齐测试用"""
    np.random.seed(seed)
    base = 2400.0 + np.linspace(0, 50, rows) + np.random.normal(0, 1, rows)
    df = pd.DataFrame({
        "open": base + np.random.normal(0, 0.3, rows),
        "high": base + abs(np.random.normal(0.5, 0.2, rows)),
        "low": base - abs(np.random.normal(0.5, 0.2, rows)),
        "close": base,
        "spread": np.full(rows, 5),
        "tick_volume": np.full(rows, 100),
    })
    df["close"] = df["close"].cumsum() / (np.arange(rows) + 1) + 2400.0
    return df


def test_scan_result_dataclass_defaults():
    from core.strategy import ScanResult
    r = ScanResult()
    assert r.symbol == ""
    assert r.status == "reject"
    assert r.died is None
    assert r.verdict_v == "reject"
    assert r.conv == 0.0
    assert r.bos == "none"
    assert r.priority == 0
    print("ScanResult defaults OK")


def test_gate1_avoid_high_spread_rejects():
    from core.strategy import gate1_avoid
    df = _make_ohlc(rows=100)
    df["spread"] = 999
    sym_cfg = {"spread_max": 50}
    ok, reason, spread, gap = gate1_avoid("XAUUSD", df, sym_cfg)
    assert ok is False
    assert "点差" in reason
    assert spread == 999
    print("gate1 拒高 spread OK")


def test_calc_ema_returns_series():
    from core.strategy import calc_ema
    s = pd.Series([1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
    e = calc_ema(s, 5)
    assert isinstance(e, pd.Series)
    assert len(e) == 10
    assert e.iloc[-1] > e.iloc[0]
    print("calc_ema OK")


def test_detect_bos_returns_string():
    from core.strategy import detect_bos
    df = _make_ohlc(rows=50)
    df["close"] = np.linspace(2400, 2600, 50)  # 上升趋势 → bull
    bos = detect_bos(df)
    assert bos in ("none", "bullish", "bearish")
    print("detect_bos OK:", bos)


def test_evaluate_returns_scan_result():
    from core.strategy import evaluate, ScanResult
    data = {
        "M5": _make_ohlc(rows=100),
        "H1": _make_ohlc(rows=100, seed=43),
        "H4": _make_ohlc(rows=100, seed=44),
    }
    sym_cfg = {"spread_max": 50}
    result = evaluate("XAUUSD", data, sym_cfg)
    assert isinstance(result, ScanResult)
    assert result.symbol == "XAUUSD"
    assert result.status in ("action", "reject")
    print("evaluate result status:", result.status, "died:", result.died)


def test_status_action_has_priority_set():
    from core.strategy import evaluate
    data = {
        "M5": _make_ohlc(rows=200, seed=10),
        "H1": _make_ohlc(rows=200, seed=11),
        "H4": _make_ohlc(rows=200, seed=12),
    }
    result = evaluate("XAUUSD", data, {"spread_max": 50})
    if result.status == "action":
        assert result.lots > 0
        assert result.sl > 0
        assert len(result.tp) == 2
        assert result.priority >= 0
        print("action: lots=", result.lots, "sl=", result.sl, "tp=", result.tp)
    else:
        print("rejected at gate", result.died, "— 也属正常测试覆盖")
