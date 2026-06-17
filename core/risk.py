"""
风控模块 -- RiskAmount=$50(按类目系数), 日亏>$300 强制 SHADOW, 连亏>=3 kill-switch
"""
import os, json, yaml
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, Tuple
import logging

logger = logging.getLogger(__name__)
CONFIG_DIR = Path(__file__).parent.parent / "config"
OUTPUTS_DIR = Path(__file__).parent.parent / "outputs"

class RiskState:
    def __init__(self):
        self.daily_pnl: float = 0.0
        self.consecutive_losses: int = 0
        self.today_str: str = ""
        self.live_disabled: bool = os.getenv("LIVE_TRADING_DISABLED", "false").lower() == "true"
    def reset_if_new_day(self):
        now = datetime.now(timezone(timedelta(hours=8)))
        today = now.strftime("%Y-%m-%d")
        if today != self.today_str:
            self.daily_pnl = 0.0
            self.consecutive_losses = 0
            self.today_str = today
    def record_trade_result(self, pnl: float):
        self.daily_pnl += pnl
        self.consecutive_losses = 0 if pnl >= 0 else self.consecutive_losses + 1

risk_state = RiskState()

def load_symbols_config() -> Dict:
    p = CONFIG_DIR / "symbols.yaml"
    if not p.exists(): return {}
    with open(p, "r", encoding="utf-8") as f: return yaml.safe_load(f)

def get_symbol_config(symbol: str) -> Optional[Dict]:
    cfg = load_symbols_config()
    if not cfg or "symbols" not in cfg: return None
    for s in cfg["symbols"]:
        if s["symbol"] == symbol: return s
    return None

def get_category_coefficient(category: str) -> float:
    cfg = load_symbols_config()
    if not cfg or "category_risk_coefficient" not in cfg: return 1.0
    return cfg["category_risk_coefficient"].get(category, 1.0)

def calculate_risk_amount(symbol: str) -> float:
    base = float(os.getenv("RISK_AMOUNT_USD", "50"))
    sc = get_symbol_config(symbol)
    if not sc: return base
    return base * get_category_coefficient(sc.get("category", "forex"))

def calculate_lot(symbol: str, entry: float, sl: float) -> float:
    sc = get_symbol_config(symbol)
    if not sc: return 0.01
    risk = calculate_risk_amount(symbol)
    pv = sc.get("pip_value", 10.0)
    ls = sc.get("lot_step", 0.01)
    decimals = sc.get("decimals", 5)
    point = 10 ** (-decimals)
    sd = abs(entry - sl)
    if sd <= 0 or pv <= 0: return ls
    # FIX: use symbol-specific point value instead of hardcoded 0.0001
    pips = sd / point
    raw = risk / (pips * pv)
    if ls > 0: raw = round(raw / ls) * ls
    return max(ls, round(raw, 2))

def check_daily_loss() -> Tuple[bool, str]:
    risk_state.reset_if_new_day()
    cap = float(os.getenv("DAILY_LOSS_CAP_USD", "300"))
    if risk_state.daily_pnl < -cap:
        return False, f"日亏已达 ${abs(risk_state.daily_pnl):.2f}, 上限 ${cap}"
    return True, "日亏正常"

def check_consecutive_losses() -> Tuple[bool, str]:
    risk_state.reset_if_new_day()
    if risk_state.consecutive_losses >= 3:
        return False, f"连亏 {risk_state.consecutive_losses} 次, kill-switch"
    return True, "连亏正常"

def check_concurrent_positions(cnt: int) -> Tuple[bool, str]:
    mx = int(os.getenv("MAX_CONCURRENT_POSITIONS", "3"))
    if cnt >= mx: return False, f"持仓 {cnt} 笔, 上限 {mx}"
    return True, "并发正常"

def check_exposure(equity: float, margin: float) -> Tuple[bool, str]:
    if equity <= 0: return False, "净值异常"
    pct = (margin / equity) * 100
    if pct > 30: return False, f"敞口 {pct:.1f}%, 上限 30%"
    return True, "敞口正常"

def validate_buy(symbol, lots, pos_cnt, equity, margin) -> Tuple[bool, str]:
    risk_state.reset_if_new_day()
    if risk_state.live_disabled: return False, "实盘交易已锁定"
    for fn in [check_daily_loss, check_consecutive_losses]:
        ok, msg = fn()
        if not ok: return False, msg
    ok, msg = check_concurrent_positions(pos_cnt)
    if not ok: return False, msg
    ok, msg = check_exposure(equity, margin)
    if not ok: return False, msg
    return True, "校验通过"

def write_trade_log(action, symbol, reason, **kw):
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    entry = {"ts": datetime.now(timezone(timedelta(hours=8))).isoformat(),
             "action": action, "symbol": symbol, "reason": reason, **kw}
    with open(OUTPUTS_DIR / "trade_decisions.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
