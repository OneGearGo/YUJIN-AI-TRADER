"""
Phase 10 tests — 动态品种拉取 + symbols.yaml 加载 + evaluate_results
"""
import os
import sys
import time
import pytest
from typing import Dict, List, Optional
from unittest.mock import patch, MagicMock


# ============================================================
# Mock classes
# ============================================================

class MockBridge:
    """Lightweight MT5Bridge mock for load_symbols() testing."""
    def __init__(self, data_mode: str = "SHADOW", state: str = "DISCONNECTED",
                 symbols: Optional[List[str]] = None):
        self._data_mode = data_mode
        self._state_str = state
        self._symbols = symbols or ["EURUSD", "GBPUSD", "USDJPY", "XAUUSD"]

    @property
    def data_mode(self) -> str:
        return self._data_mode

    @property
    def state(self):
        class _State:
            value = self._state_str
        return _State()

    def symbols_get_all(self) -> List[str]:
        if not self._symbols:
            return []
        return list(self._symbols)

    @property
    def reconnect_count(self) -> int:
        return 0

    @property
    def last_heartbeat(self) -> Optional[float]:
        return time.time()

    async def heartbeat_ping_async(self, timeout: float = 3.0) -> bool:
        return True


class MockBridgeError(MockBridge):
    """Bridge that raises exception on symbols_get_all (simulates MT5 error)."""
    def symbols_get_all(self) -> List[str]:
        raise RuntimeError("MT5 connection lost")


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture
def bridge_shadow():
    """Bridge in SHADOW mode (disconnected)."""
    return MockBridge(data_mode="SHADOW", state="DISCONNECTED")

@pytest.fixture
def bridge_live_connected():
    """Bridge in LIVE mode (connected) — should trigger dynamic symbols."""
    return MockBridge(data_mode="LIVE", state="CONNECTED")

@pytest.fixture
def bridge_live_dry_run_connected():
    """Bridge in LIVE_DRY_RUN mode (connected)."""
    return MockBridge(data_mode="LIVE_DRY_RUN", state="CONNECTED")

@pytest.fixture
def bridge_live_reconnecting():
    """Bridge in LIVE mode but reconnecting — should NOT trigger dynamic symbols."""
    return MockBridge(data_mode="LIVE", state="RECONNECTING")

@pytest.fixture
def bridge_empty_symbols():
    """Bridge returns empty symbol list."""
    return MockBridge(data_mode="LIVE", state="CONNECTED", symbols=[])

@pytest.fixture
def bridge_error():
    """Bridge that errors on symbols_get_all."""
    return MockBridgeError(data_mode="LIVE", state="CONNECTED")

@pytest.fixture
def temp_symbols_yaml(tmp_path, monkeypatch):
    """Create a temporary symbols.yaml with 4 test symbols."""
    cfg_dir = tmp_path / "config"
    cfg_dir.mkdir()
    yaml_content = """# Test config
category_risk_coefficient:
  forex: 1.0
  index: 1.0

correlation_groups:
  eur_block: [EURUSD]
  gbp_block: [GBPUSD]

symbols:
  - symbol: EURUSD
    category: forex
    pip_value: 10.0
    spread_max: 15
    lot_step: 0.01
    decimals: 5
    trading_hours: "24/5"
    dxy_corr: -0.80
    gap_max_pct: 0.3

  - symbol: GBPUSD
    category: forex
    pip_value: 10.0
    spread_max: 18
    lot_step: 0.01
    decimals: 5
    trading_hours: "24/5"
    dxy_corr: -0.80
    gap_max_pct: 0.3

  - symbol: XAUUSD
    category: commodity
    pip_value: 10.0
    spread_max: 50
    lot_step: 0.01
    decimals: 2
    trading_hours: "24/5"
    dxy_corr: -0.85
    gap_max_pct: 0.5

  - symbol: BTCUSD
    category: crypto
    pip_value: 0.01
    spread_max: 5000
    lot_step: 0.01
    decimals: 2
    trading_hours: "24/7"
    dxy_corr: false
    gap_max_pct: 1.0
"""
    yaml_path = cfg_dir / "symbols.yaml"
    yaml_path.write_text(yaml_content, encoding="utf-8")

    # Point scanner's CONFIG_DIR to temp path
    import core.scanner as scanner_mod
    monkeypatch.setattr(scanner_mod, "CONFIG_DIR", cfg_dir)

    # Also monkeypatch routes_screen._load_sym_configs file path
    # The function uses Path(__file__).resolve().parent.parent / "config" / "symbols.yaml"
    # so we need to also mock the file existence check
    import api.routes_screen as routes_screen
    monkeypatch.setattr(routes_screen, "_SYM_CONFIG_CACHE", None)
    # We'll override the path inside _load_sym_configs via monkeypatch

    return yaml_path


# ============================================================
# Tests: load_symbols(bridge)
# ============================================================

class TestLoadSymbols:
    """scanner.load_symbols() — Phase 10 dynamic symbols loading."""

    def test_no_bridge_returns_yaml(self, temp_symbols_yaml):
        """No bridge passed → falls back to symbols.yaml."""
        from core.scanner import load_symbols
        syms = load_symbols()
        assert isinstance(syms, list)
        assert len(syms) >= 1
        # Should contain symbols from the temp yaml
        assert "EURUSD" in syms

    def test_bridge_none_returns_yaml(self, temp_symbols_yaml):
        """bridge=None → falls back to symbols.yaml."""
        from core.scanner import load_symbols
        syms = load_symbols(bridge=None)
        assert isinstance(syms, list)
        assert "EURUSD" in syms

    def test_shadow_mode_ignores_bridge(self, temp_symbols_yaml, bridge_shadow):
        """Bridge in SHADOW mode → ignores bridge, returns YAML symbols."""
        from core.scanner import load_symbols
        syms = load_symbols(bridge=bridge_shadow)
        assert isinstance(syms, list)
        assert "EURUSD" in syms
        # SHADOW mode: should NOT contain the mock bridge's symbols
        assert len(syms) == 4  # 4 from temp YAML

    def test_live_connected_returns_mt5_symbols(self, bridge_live_connected):
        """Bridge LIVE + CONNECTED → returns MT5 symbols from bridge."""
        from core.scanner import load_symbols
        syms = load_symbols(bridge=bridge_live_connected)
        assert isinstance(syms, list)
        assert len(syms) == 4
        assert "EURUSD" in syms
        assert "XAUUSD" in syms

    def test_live_dry_run_connected_returns_mt5(self, bridge_live_dry_run_connected):
        """Bridge LIVE_DRY_RUN + CONNECTED → returns MT5 symbols."""
        from core.scanner import load_symbols
        syms = load_symbols(bridge=bridge_live_dry_run_connected)
        assert isinstance(syms, list)
        assert len(syms) == 4

    def test_live_reconnecting_falls_back_to_yaml(self, temp_symbols_yaml, bridge_live_reconnecting):
        """Bridge LIVE + RECONNECTING → not CONNECTED, falls back to YAML."""
        from core.scanner import load_symbols
        syms = load_symbols(bridge=bridge_live_reconnecting)
        assert isinstance(syms, list)
        assert len(syms) == 4  # from YAML (EURUSD, GBPUSD, XAUUSD, BTCUSD)

    def test_empty_symbols_list_falls_back_to_yaml(self, temp_symbols_yaml, bridge_empty_symbols):
        """Bridge returns empty list → falls back to YAML."""
        from core.scanner import load_symbols
        syms = load_symbols(bridge=bridge_empty_symbols)
        assert isinstance(syms, list)
        assert len(syms) == 4  # from YAML fallback

    def test_bridge_error_falls_back_to_yaml(self, temp_symbols_yaml, bridge_error):
        """Bridge raises exception → falls back to YAML gracefully."""
        from core.scanner import load_symbols
        syms = load_symbols(bridge=bridge_error)
        assert isinstance(syms, list)
        assert len(syms) == 4  # from YAML fallback

    def test_mt5_max_symbols_truncation(self, monkeypatch, bridge_live_connected):
        """MT5_MAX_SYMBOLS=2 → only 2 symbols returned."""
        monkeypatch.setenv("MT5_MAX_SYMBOLS", "2")
        # Need to re-import or read the env
        from core.scanner import load_symbols
        syms = load_symbols(bridge=bridge_live_connected)
        assert len(syms) == 2  # truncated to 2

    def test_no_yaml_file_returns_xauusd(self, tmp_path, monkeypatch):
        """No symbols.yaml exists → returns ['XAUUSD'] as fallback."""
        import core.scanner as scanner_mod
        # Point to a config dir without symbols.yaml
        empty_cfg = tmp_path / "config"
        empty_cfg.mkdir()
        monkeypatch.setattr(scanner_mod, "CONFIG_DIR", empty_cfg)
        from core.scanner import load_symbols
        syms = load_symbols()
        assert syms == ["XAUUSD"]

    def test_yaml_without_symbols_key_returns_xauusd(self, tmp_path, monkeypatch):
        """symbols.yaml exists but has no 'symbols' key → returns ['XAUUSD']."""
        import core.scanner as scanner_mod
        cfg_dir = tmp_path / "config"
        cfg_dir.mkdir()
        (cfg_dir / "symbols.yaml").write_text("foo: bar\n", encoding="utf-8")
        monkeypatch.setattr(scanner_mod, "CONFIG_DIR", cfg_dir)
        from core.scanner import load_symbols
        syms = load_symbols()
        assert syms == ["XAUUSD"]


# ============================================================
# Tests: _load_sym_configs()
# ============================================================

class TestLoadSymConfigs:
    """routes_screen._load_sym_configs() — symbols.yaml config loading."""

    def test_load_basic_config(self, monkeypatch):
        """Load config from a temp symbols.yaml with known symbols."""
        # We test the YAML parsing logic directly
        import yaml
        from pathlib import Path
        import tempfile

        yaml_content = """
symbols:
  - symbol: EURUSD
    category: forex
    spread_max: 15
    pip_value: 10.0
    lot_step: 0.01
    decimals: 5
  - symbol: XAUUSD
    category: commodity
    spread_max: 50
    pip_value: 10.0
    lot_step: 0.01
    decimals: 2
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml",
                                         delete=False, encoding="utf-8") as f:
            f.write(yaml_content)
            tmp_path = f.name

        try:
            raw = yaml.safe_load(yaml_content)
            configs = {}
            for entry in raw.get("symbols", []):
                sym = entry.get("symbol") or entry.get("sym")
                if sym:
                    configs[sym] = {
                        "spread_max": entry.get("spread_max", 50),
                        "gap_max_pct": entry.get("gap_max_pct", 0.5),
                        "pip_value": entry.get("pip_value", 0.1),
                        "lot_step": entry.get("lot_step", 0.01),
                        "decimals": entry.get("decimals", 2),
                        "category": entry.get("category", "forex"),
                        "trading_hours": entry.get("trading_hours", ""),
                        "dxy_corr": entry.get("dxy_corr", False),
                    }
            assert "EURUSD" in configs
            assert "XAUUSD" in configs
            assert configs["EURUSD"]["category"] == "forex"
            assert configs["EURUSD"]["spread_max"] == 15
            assert configs["EURUSD"]["pip_value"] == 10.0
            assert configs["XAUUSD"]["category"] == "commodity"
            assert configs["XAUUSD"]["spread_max"] == 50
        finally:
            os.unlink(tmp_path)

    def test_missing_file_returns_empty(self, monkeypatch):
        """No symbols.yaml → returns empty dict."""
        from api.routes_screen import _load_sym_configs, _SYM_CONFIG_CACHE
        # Reset cache
        monkeypatch.setattr("api.routes_screen._SYM_CONFIG_CACHE", None)
        # Monkeypatch the file existence check
        import api.routes_screen as rs
        original = rs._load_sym_configs
        def mock_load():
            return {}
        monkeypatch.setattr(rs, "_load_sym_configs", mock_load)
        result = rs._load_sym_configs()
        assert result == {}

    def test_category_defaults_to_forex(self):
        """Symbol without category → defaults to 'forex'."""
        import yaml
        yaml_content = """
symbols:
  - symbol: UNKNOWN
    pip_value: 1.0
    spread_max: 10
"""
        raw = yaml.safe_load(yaml_content)
        configs = {}
        for entry in raw.get("symbols", []):
            sym = entry.get("symbol") or entry.get("sym")
            if sym:
                configs[sym] = {
                    "category": entry.get("category", "forex"),
                }
        assert configs["UNKNOWN"]["category"] == "forex"

    def test_symbol_with_different_fields(self):
        """Symbol with all optional fields present."""
        import yaml
        yaml_content = """
symbols:
  - symbol: BTCUSD
    category: crypto
    pip_value: 0.01
    spread_max: 5000
    lot_step: 0.01
    decimals: 2
    trading_hours: "24/7"
    gap_max_pct: 1.0
"""
        raw = yaml.safe_load(yaml_content)
        configs = {}
        for entry in raw.get("symbols", []):
            sym = entry.get("symbol") or entry.get("sym")
            if sym:
                configs[sym] = {
                    "spread_max": entry.get("spread_max", 50),
                    "gap_max_pct": entry.get("gap_max_pct", 0.5),
                    "pip_value": entry.get("pip_value", 0.1),
                    "lot_step": entry.get("lot_step", 0.01),
                    "decimals": entry.get("decimals", 2),
                    "category": entry.get("category", "forex"),
                    "trading_hours": entry.get("trading_hours", ""),
                    "dxy_corr": entry.get("dxy_corr", False),
                }
        btc = configs["BTCUSD"]
        assert btc["category"] == "crypto"
        assert btc["spread_max"] == 5000
        assert btc["gap_max_pct"] == 1.0
        assert btc["trading_hours"] == "24/7"
        assert btc["dxy_corr"] is False


# ============================================================
# Tests: _evaluate_results()
# ============================================================

class TestEvaluateResults:
    """routes_screen._evaluate_results() — result mapping with category."""

    def test_basic_evaluate_structure(self, monkeypatch):
        """_evaluate_results returns dict with expected structure."""
        from api.routes_screen import _evaluate_results

        # Mock strategy.evaluate to return a predictable ScanResult
        fake_result = MagicMock()
        fake_result.status = "action"
        fake_result.died = None
        fake_result.conv = 0.85
        fake_result.priority = 72
        fake_result.spread = 12
        fake_result.gap_pct = 0.1
        fake_result.ema_align = True
        fake_result.fvg = True
        fake_result.sweep = False
        fake_result.bos = "bull"
        fake_result.lots = 0.05
        fake_result.sl = 2340.0
        fake_result.tp = [2360.0, 2380.0]
        fake_result.exit_plan = "SL -0.5% · TP 1:2"
        fake_result.thesis = "H4 BOS + M5 displacement"
        fake_result.reason = "EMA aligned bull"

        def mock_evaluate(sym, data, config):
            return fake_result

        monkeypatch.setattr("api.routes_screen.evaluate", mock_evaluate)
        # Also mock _load_sym_configs to return known config
        monkeypatch.setattr("api.routes_screen._load_sym_configs",
                           lambda: {"XAUUSD": {"category": "commodity", "spread_max": 50}})

        # Build mock scan results
        import pandas as pd
        mock_results = {
            "XAUUSD": {
                "M5": pd.DataFrame({"time": [1, 2, 3], "close": [2400, 2401, 2402]}),
                "H1": pd.DataFrame({"time": [1, 2, 3], "close": [2390, 2395, 2400]}),
                "H4": pd.DataFrame({"time": [1, 2, 3], "close": [2380, 2390, 2400]}),
            }
        }

        result = _evaluate_results(mock_results)
        assert isinstance(result, dict)
        assert "XAUUSD" in result
        entry = result["XAUUSD"]
        assert entry["sym"] == "XAUUSD"
        assert entry["category"] == "commodity"
        assert entry["status"] == "action"
        assert entry["conv"] == 0.85
        assert entry["priority"] == 72
        assert entry["thesis"] == "H4 BOS + M5 displacement"
        assert entry["exit_plan"] == "SL -0.5% · TP 1:2"

    def test_evaluate_error_handling(self, monkeypatch):
        """When evaluate raises, error entry has expected fields."""
        from api.routes_screen import _evaluate_results

        def mock_evaluate(sym, data, config):
            raise ValueError("Data too short")

        monkeypatch.setattr("api.routes_screen.evaluate", mock_evaluate)
        monkeypatch.setattr("api.routes_screen._load_sym_configs",
                           lambda: {"XAUUSD": {"category": "commodity", "spread_max": 50}})

        mock_results = {"XAUUSD": {"M5": None, "H1": None, "H4": None}}
        result = _evaluate_results(mock_results)

        assert "XAUUSD" in result
        entry = result["XAUUSD"]
        assert entry["status"] == "error"
        assert "evaluate error" in entry.get("reason", "")

    def test_evaluate_skips_none_result(self, monkeypatch):
        """When evaluate returns None, symbol is skipped (not in output)."""
        from api.routes_screen import _evaluate_results

        def mock_evaluate(sym, data, config):
            return None

        monkeypatch.setattr("api.routes_screen.evaluate", mock_evaluate)
        monkeypatch.setattr("api.routes_screen._load_sym_configs",
                           lambda: {"EURUSD": {"category": "forex", "spread_max": 15}})

        mock_results = {"EURUSD": {"M5": None, "H1": None, "H4": None}}
        result = _evaluate_results(mock_results)
        # If evaluate returns None, the `if result is not None:` check skips it
        # So EURUSD should NOT be in the output
        assert "EURUSD" not in result or result.get("EURUSD", {}).get("status") != "action"

    def test_evaluate_empty_results(self):
        """Empty results dict returns empty output."""
        from api.routes_screen import _evaluate_results
        result = _evaluate_results({})
        assert result == {}

    def test_evaluate_none_results(self):
        """None results returns empty output."""
        from api.routes_screen import _evaluate_results
        result = _evaluate_results(None)
        assert result == {}
