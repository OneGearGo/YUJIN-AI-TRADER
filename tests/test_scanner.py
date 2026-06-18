"""
Phase 8 test_scanner — 验证 SHADOW mode 扫描器 facade 返 shape
"""
import pytest


def test_scan_all_returns_dict_with_timeframes(bridge, fake_symbols):
    from core.scanner import scan_all, TIMEFRAMES
    results = scan_all(bridge, ["XAUUSD"])
    assert isinstance(results, dict)
    assert "XAUUSD" in results
    sym_data = results["XAUUSD"]
    for tf in TIMEFRAMES:
        assert tf in sym_data
    print("scan_all SHADOW OK:", list(sym_data.keys()))


def test_scan_symbol_returns_per_tf_dict(bridge):
    from core.scanner import scan_symbol, TIMEFRAMES
    out = scan_symbol(bridge, "XAUUSD")
    assert isinstance(out, dict)
    assert set(out.keys()) == set(TIMEFRAMES)
    print("scan_symbol shape OK:", list(out.keys()))


def test_load_symbols_returns_list():
    from core.scanner import load_symbols
    syms = load_symbols()
    assert isinstance(syms, list)
    assert len(syms) >= 1
    print("load_symbols:", len(syms), "symbols")


def test_pick_source_returns_string(bridge):
    from core.scanner import _pick_source
    assert _pick_source() in ("SHADOW", "LIVE_DRY_RUN", "LIVE")
    print("_pick_source OK")


def test_fallback_when_symbols_empty(bridge):
    from core.scanner import scan_all
    out = scan_all(bridge, [])
    assert out == {}
    print("empty symbols yields empty dict")


@pytest.fixture
def bridge(monkeypatch):
    """Reset bridge 单例状态 to a clean baseline for each test."""
    from core.mt5_bridge import bridge as _b, MT5State
    _b._ro = False
    _b._tr = False
    _b._state = MT5State.DISCONNECTED
    _b._last_heartbeat = None
    _b._reconnect_count = 0
    yield _b


@pytest.fixture
def fake_symbols(tmp_path, monkeypatch):
    """override symbols.yaml 路径 → minimal fixture"""
    cfg_dir = tmp_path / "config"
    cfg_dir.mkdir()
    (cfg_dir / "symbols.yaml").write_text(
        "symbols:\n  - symbol: XAUUSD\n    category: commodity\n",
        encoding="utf-8",
    )
    import core.scanner as scanner_mod
    monkeypatch.setattr(scanner_mod, "CONFIG_DIR", cfg_dir)
    monkeypatch.setattr(scanner_mod, "load_symbols", lambda: ["XAUUSD"])
    return cfg_dir
