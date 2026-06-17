"""
持仓管理模块 -- CRUD + outputs/positions.json 持久化
SHADOW: 只写 trade_decisions.jsonl, 不调 mt5.order_send
LIVE: 调 order_send 真发
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
    except (json.JSONDecodeError, IOError):
        return []


def _save(positions: List[Dict]):
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    with open(POSITIONS_FILE, "w", encoding="utf-8") as f:
        json.dump(positions, f, ensure_ascii=False, indent=2)


def add(ticket: int, symbol: str, direction: str, lots: float,
        entry: float, sl: float, tp: list, mode: str, reason: str = "") -> Dict:
    """添加持仓到监控列表 + 写 JSONL 日志"""
    positions = _load()
    pos = {
        "ticket": ticket,
        "symbol": symbol,
        "type": direction,
        "lots": lots,
        "entry": entry,
        "current": entry,
        "sl": sl,
        "tp": tp,
        "pnl": 0.0,
        "pnl_pct": 0.0,
        "severity": 0,
        "mode": mode,
        "open_time": _now(),
    }
    positions.append(pos)
    _save(positions)

    # 写 JSONL 日志
    _write_log("BUY", symbol, lots, sl, tp, reason, ticket=ticket, mode=mode)
    logger.info("持仓添加: ticket=%d %s %s %.2f [%s]", ticket, direction, symbol, lots, mode)
    return pos


def remove(ticket: int, reason: str = "") -> Optional[Dict]:
    """移除持仓(不真平仓) + 写 JSONL"""
    positions = _load()
    for i, pos in enumerate(positions):
        if pos["ticket"] == ticket:
            removed = positions.pop(i)
            _save(positions)
            _write_log("UNMONITOR", pos["symbol"], pos["lots"], pos["sl"], pos["tp"],
                       reason or "unmonitor", ticket=ticket)
            logger.info("持仓移除: ticket=%d %s", ticket, pos["symbol"])
            return removed
    return None


def close(ticket: int, pnl: float, reason: str = "") -> Optional[Dict]:
    """平仓后移除 + 写 JSONL"""
    positions = _load()
    for i, pos in enumerate(positions):
        if pos["ticket"] == ticket:
            closed = positions.pop(i)
            _save(positions)
            _write_log("SELL", pos["symbol"], pos["lots"], pos["sl"], pos["tp"],
                       reason or "close", ticket=ticket, pnl=pnl)
            logger.info("平仓移除: ticket=%d %s pnl=%.2f", ticket, pos["symbol"], pnl)
            return closed
    return None


def list_all() -> List[Dict]:
    """获取所有持仓"""
    return _load()


def get(ticket: int) -> Optional[Dict]:
    """按 ticket 获取单个持仓"""
    for pos in _load():
        if pos["ticket"] == ticket:
            return pos
    return None


def count() -> int:
    return len(_load())


def _write_log(action: str, symbol: str, lots: float, sl: float, tp: list,
               reason: str, ticket: int = 0, mode: str = "", pnl: float = 0.0):
    """写 JSONL 日志: {ts, action, symbol, lots, sl, tp, reason}"""
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    log_path = OUTPUTS_DIR / "trade_decisions.jsonl"
    entry = {
        "ts": _now(),
        "action": action,
        "symbol": symbol,
        "lots": lots,
        "sl": sl,
        "tp": tp,
        "reason": reason,
    }
    if ticket:
        entry["ticket"] = ticket
    if mode:
        entry["mode"] = mode
    if pnl:
        entry["pnl"] = pnl
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
