"""
持仓管理模块 -- CRUD + JSONL + severity评分 + 逃生信号
severity算法见 SPEC S10.3
"""
import json
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict
import logging

logger = logging.getLogger(__name__)
OUTPUTS_DIR = Path(__file__).parent.parent / "outputs"
POSITIONS_FILE = OUTPUTS_DIR / "positions.json"

def _now():
    return datetime.now(timezone(timedelta(hours=8))).isoformat()


def _load() -> List[Dict]:
    if not POSITIONS_FILE.exists():
        return []
    try:
        with open(POSITIONS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        logger.warning("positions.json 读取失败: %s", e)
        return []


def _save(positions: List[Dict]):
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    with open(POSITIONS_FILE, "w", encoding="utf-8") as f:
        json.dump(positions, f, ensure_ascii=False, indent=2)


def add(ticket: int, symbol: str, direction: str, lots: float,
        entry: float, sl: float, tp: list, mode: str, reason: str = "") -> Dict:
    """添加持仓 + 写 JSONL"""
    positions = _load()
    pos = {
        "ticket": ticket,
        "symbol": symbol,
        "type": direction,
        "lots": lots,
        "entry": entry,
        "current": entry,
        "sl": sl,
        "tp": tp if isinstance(tp, list) else [tp],
        "pnl": 0.0,
        "pnl_pct": 0.0,
        "severity": 0,
        "escape_alert": False,
        "mode": mode,
        "open_time": _now(),
    }
    positions.append(pos)
    _save(positions)
    _write_log("BUY", symbol, lots, sl, tp, reason, ticket=ticket, mode=mode)
    logger.info("持仓添加: ticket=%d %s %s %.2f [%s]", ticket, direction, symbol, lots, mode)
    return pos


def remove(ticket: int, reason: str = "") -> Optional[Dict]:
    """移除持仓(不真平仓)"""
    positions = _load()
    for i, pos in enumerate(positions):
        if pos["ticket"] == ticket:
            removed = positions.pop(i)
            _save(positions)
            _write_log("UNMONITOR", pos["symbol"], pos["lots"], pos["sl"], pos["tp"],
                       reason or "unmonitor", ticket=ticket)
            return removed
    return None


def close(ticket: int, pnl: float, reason: str = "") -> Optional[Dict]:
    """平仓后移除"""
    positions = _load()
    for i, pos in enumerate(positions):
        if pos["ticket"] == ticket:
            closed = positions.pop(i)
            _save(positions)
            _write_log("SELL", pos["symbol"], pos["lots"], pos["sl"], pos["tp"],
                       reason or "close", ticket=ticket, pnl=pnl)
            return closed
    return None


def mark_escape(ticket: int) -> Optional[Dict]:
    """标记逃生信号 + 写 ALERT 日志"""
    positions = _load()
    for pos in positions:
        if pos["ticket"] == ticket:
            pos["escape_alert"] = True
            _save(positions)
            _write_log("ESCAPE", pos["symbol"], pos["lots"], pos["sl"], pos["tp"],
                       f"severity={pos.get('severity', 0)}", ticket=ticket)
            logger.warning("逃生触发: ticket=%d %s severity=%d", ticket, pos["symbol"], pos.get("severity", 0))
            return pos
    return None


def list_all() -> List[Dict]:
    return _load()


def get(ticket: int) -> Optional[Dict]:
    for pos in _load():
        if pos["ticket"] == ticket:
            return pos
    return None


def count() -> int:
    return len(_load())


# ============================================================
# severity 评分 (SPEC S10.3)
# ============================================================

def calc_severity(pos: Dict, m5_ema20: float = 0, m5_ema50: float = 0,
                  consec_losses: int = 0) -> int:
    """
    severity 0-100:
      浮亏%: < -0.3% → +30, < -0.1% → +15
      SL接近度: < 0.1% → +25, < 0.3% → +12
      M5反向: EMA20 < EMA50 且 BUY → +20
      连亏: >=1 → +10
    """
    score = 0
    # 浮亏
    pnl_pct = pos.get("pnl_pct", 0)
    if pnl_pct < -0.3:
        score += 30
    elif pnl_pct < -0.1:
        score += 15
    # SL 接近度
    current = pos.get("current", 0)
    sl = pos.get("sl", 0)
    if current > 0 and sl > 0:
        sl_dist = abs(current - sl) / current
        if sl_dist < 0.001:
            score += 25
        elif sl_dist < 0.003:
            score += 12
    # M5 反向
    if m5_ema20 > 0 and m5_ema50 > 0:
        if m5_ema20 < m5_ema50 and pos.get("type") == "BUY":
            score += 20
        elif m5_ema20 > m5_ema50 and pos.get("type") == "SELL":
            score += 20
    # 连亏
    if consec_losses >= 1:
        score += 10
    return min(100, score)


def inspect_all(consec_losses: int = 0, m5_data: Dict = None) -> List[Dict]:
    """
    巡检所有持仓, 计算 severity, 触发逃生
    m5_data: {symbol: {ema20: float, ema50: float}}
    返回需要逃生的持仓列表
    """
    positions = _load()
    if not positions:
        return []

    m5_data = m5_data or {}
    escape_list = []

    for pos in positions:
        sym = pos.get("symbol", "")
        sym_m5 = m5_data.get(sym, {})
        ema20 = sym_m5.get("ema20", 0)
        ema50 = sym_m5.get("ema50", 0)

        sev = calc_severity(pos, ema20, ema50, consec_losses)
        pos["severity"] = sev

        # severity >= 70 触发逃生
        if sev >= 70 and not pos.get("escape_alert"):
            mark_escape(pos["ticket"])
            pos["escape_alert"] = True
            escape_list.append(pos)

    _save(positions)
    return escape_list


def update_prices(price_map: Dict[str, float]):
    """更新持仓当前价格 + 重新计算 pnl"""
    positions = _load()
    if not positions:
        return
    for pos in positions:
        sym = pos.get("symbol", "")
        if sym in price_map:
            pos["current"] = price_map[sym]
            entry = pos.get("entry", 0)
            lots = pos.get("lots", 0)
            if entry > 0:
                if pos.get("type") == "BUY":
                    pos["pnl"] = round((pos["current"] - entry) * lots * 100, 2)
                else:
                    pos["pnl"] = round((entry - pos["current"]) * lots * 100, 2)
                pos["pnl_pct"] = round(pos["pnl"] / (entry * lots) * 100, 2) if entry * lots > 0 else 0
    _save(positions)


def _write_log(action: str, symbol: str, lots, sl, tp, reason: str,
               ticket: int = 0, mode: str = "", pnl: float = 0.0):
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    log_path = OUTPUTS_DIR / "trade_decisions.jsonl"
    entry = {
        "ts": _now(), "action": action, "symbol": symbol,
        "lots": lots, "sl": sl, "tp": tp, "reason": reason,
    }
    if ticket: entry["ticket"] = ticket
    if mode: entry["mode"] = mode
    if pnl: entry["pnl"] = pnl
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
