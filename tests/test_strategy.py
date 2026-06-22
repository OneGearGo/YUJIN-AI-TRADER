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
    from core.strategy import gate1_avoid, FOREX_PARAMS
    df = _make_ohlc(rows=100)
    df["spread"] = 999
    sym_cfg = {"spread_max": 50}
    ok, reason, spread, gap = gate1_avoid("XAUUSD", df, sym_cfg, FOREX_PARAMS)
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


# ── Indicator score tests ─────────────────────────────────────────


def _make_uptrend_ohlc(rows=200, seed=42):
    """Clear uptrend for EMA alignment (fast > slow)."""
    np.random.seed(seed)
    close = np.linspace(2400, 2500, rows) + np.random.normal(0, 0.05, rows)
    df = pd.DataFrame({
        "open": close - abs(np.random.normal(0.1, 0.05, rows)),
        "high": close + abs(np.random.normal(0.3, 0.1, rows)),
        "low": close - abs(np.random.normal(0.3, 0.1, rows)),
        "close": close,
        "spread": np.full(rows, 5),
        "tick_volume": np.full(rows, 100),
    })
    return df


def _make_downtrend_ohlc(rows=200, seed=42):
    """Clear downtrend (EMA fast < slow)."""
    np.random.seed(seed)
    close = np.linspace(2500, 2400, rows) + np.random.normal(0, 0.05, rows)
    df = pd.DataFrame({
        "open": close + abs(np.random.normal(0.1, 0.05, rows)),
        "high": close + abs(np.random.normal(0.3, 0.1, rows)),
        "low": close - abs(np.random.normal(0.3, 0.1, rows)),
        "close": close,
        "spread": np.full(rows, 5),
        "tick_volume": np.full(rows, 100),
    })
    return df


def _make_fvg_ohlc(rows=200, seed=42):
    """Uptrend with bullish FVG injected near the end (low[i] > high[i-2])."""
    df = _make_uptrend_ohlc(rows, seed)
    idx = rows - 5
    df.iloc[idx, df.columns.get_loc("low")] = df["high"].iloc[idx - 2] + 5
    return df


def _make_flat_ohlc(rows=200, seed=42):
    """Flat/ranging market — no FVG, no sweep, no BOS."""
    np.random.seed(seed)
    close = np.full(rows, 2450.0) + np.random.normal(0, 0.1, rows)
    df = pd.DataFrame({
        "open": close + np.random.normal(0, 0.05, rows),
        "high": close + abs(np.random.normal(0.1, 0.05, rows)),
        "low": close - abs(np.random.normal(0.1, 0.05, rows)),
        "close": close,
        "spread": np.full(rows, 5),
        "tick_volume": np.full(rows, 100),
    })
    # Ensure last close below previous highs → no BOS
    prev_high = df["high"].iloc[-21:-1].max()
    df.iloc[-1, df.columns.get_loc("close")] = prev_high - 0.5
    return df


def _make_bos_disp_ohlc(rows=200, seed=42):
    """Uptrend + BOS (close above prev high) + displacement (big body)."""
    df = _make_uptrend_ohlc(rows, seed)
    prev_high = df["high"].iloc[-21:-1].max()
    df.iloc[-1, df.columns.get_loc("open")] = prev_high + 2
    df.iloc[-1, df.columns.get_loc("close")] = prev_high + 12
    df.iloc[-1, df.columns.get_loc("high")] = prev_high + 14
    return df


def _make_bos_only_ohlc(rows=200, seed=42):
    """BOS present (close above prev high) but no displacement (tiny body)."""
    df = _make_uptrend_ohlc(rows, seed)
    prev_high = df["high"].iloc[-21:-1].max()
    mid = prev_high + 0.5
    # Body = 0.002 — well below any ATR * 1.5
    df.iloc[-1, df.columns.get_loc("open")] = mid - 0.001
    df.iloc[-1, df.columns.get_loc("close")] = mid + 0.001
    df.iloc[-1, df.columns.get_loc("high")] = prev_high + 1.0
    return df


def _make_no_bos_ohlc(rows=200, seed=42):
    """Uptrend but last close NOT above prev high → no BOS."""
    df = _make_uptrend_ohlc(rows, seed)
    prev_high = df["high"].iloc[-21:-1].max()
    df.iloc[-1, df.columns.get_loc("close")] = prev_high - 1.0
    df.iloc[-1, df.columns.get_loc("open")] = prev_high - 1.5
    df.iloc[-1, df.columns.get_loc("high")] = prev_high - 0.5
    return df


def _scores_data(m5, h1=None, h4=None, seed_h1=11, seed_h4=12, rows=200):
    """Build 3-timeframe data dict, reusing m5 for missing frames."""
    return {
        "M5": m5,
        "H1": h1 if h1 is not None else _make_uptrend_ohlc(rows, seed_h1),
        "H4": h4 if h4 is not None else _make_uptrend_ohlc(rows, seed_h4),
    }


def test_ema_score_uptrend_is_one():
    """All 3 timeframes uptrend → ema_score = 1.0."""
    from core.strategy import evaluate
    data = _scores_data(
        _make_uptrend_ohlc(200, 10),
        _make_uptrend_ohlc(200, 11),
        _make_uptrend_ohlc(200, 12),
    )
    r = evaluate("EURUSD", data, {"spread_max": 50, "category": "forex"})
    assert r.ema_score == 1.0, f"Expected 1.0, got {r.ema_score}"
    print(f"ema_score uptrend: {r.ema_score}")


def test_ema_score_downtrend_is_zero():
    """All 3 timeframes downtrend → ema_score = 0.0, gate2 still passes."""
    from core.strategy import evaluate
    data = _scores_data(
        _make_downtrend_ohlc(200, 10),
        _make_downtrend_ohlc(200, 11),
        _make_downtrend_ohlc(200, 12),
    )
    r = evaluate("EURUSD", data, {"spread_max": 50, "category": "forex"})
    assert r.ema_score == 0.0, f"Expected 0.0, got {r.ema_score}"
    assert r.died != 2, "Gate2 should pass for aligned downtrend"
    print(f"ema_score downtrend: {r.ema_score}")


def test_fvg_score_with_fvg():
    """FVG in H4 → fvg_score = 1.0."""
    from core.strategy import evaluate
    data = _scores_data(
        _make_uptrend_ohlc(200, 10),
        _make_uptrend_ohlc(200, 11),
        _make_fvg_ohlc(200, 12),
    )
    r = evaluate("EURUSD", data, {"spread_max": 50, "category": "forex"})
    assert r.fvg_score == 1.0, f"Expected 1.0, got {r.fvg_score}"
    print(f"fvg_score with FVG: {r.fvg_score}")


def test_fvg_score_without_fvg():
    """Flat/ranging data — no FVG, fvg_score = 0.0."""
    from core.strategy import evaluate
    data = _scores_data(
        _make_flat_ohlc(200, 10),
        _make_flat_ohlc(200, 11),
        _make_flat_ohlc(200, 12),
    )
    r = evaluate("EURUSD", data, {"spread_max": 50, "category": "forex"})
    assert r.fvg_score == 0.0, f"Expected 0.0, got {r.fvg_score}"
    # Flat data may reject at gate2 or gate3 — fvg_score is always 0.0
    print(f"fvg_score no FVG: {r.fvg_score} (died={r.died})")


def test_dxy_score_bos_and_displacement():
    """BOS + displacement → dxy_score = 1.0."""
    from core.strategy import evaluate
    data = _scores_data(
        _make_bos_disp_ohlc(200, 10),
        _make_uptrend_ohlc(200, 11),
        _make_fvg_ohlc(200, 12),
    )
    r = evaluate("EURUSD", data, {"spread_max": 50, "category": "forex"})
    assert r.dxy_score == 1.0, f"Expected 1.0, got {r.dxy_score}"
    print(f"dxy_score BOS+disp: {r.dxy_score}")


def test_dxy_score_bos_only():
    """BOS without displacement → dxy_score = 0.5."""
    from core.strategy import evaluate
    data = _scores_data(
        _make_bos_only_ohlc(200, 10),
        _make_uptrend_ohlc(200, 11),
        _make_fvg_ohlc(200, 12),
    )
    r = evaluate("EURUSD", data, {"spread_max": 50, "category": "forex"})
    assert r.dxy_score == 0.5, f"Expected 0.5, got {r.dxy_score}"
    print(f"dxy_score BOS only: {r.dxy_score}")


def test_dxy_score_no_bos():
    """No BOS → dxy_score = 0.0."""
    from core.strategy import evaluate
    data = _scores_data(
        _make_no_bos_ohlc(200, 10),
        _make_uptrend_ohlc(200, 11),
        _make_fvg_ohlc(200, 12),
    )
    r = evaluate("EURUSD", data, {"spread_max": 50, "category": "forex"})
    assert r.dxy_score == 0.0, f"Expected 0.0, got {r.dxy_score}"
    print(f"dxy_score no BOS: {r.dxy_score}")
