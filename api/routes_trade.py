"""
交易路由 -- buy/sell/unmonitor/mode/positions + 逃生
SHADOW: 只写JSONL不调mt5.order_send
LIVE: mt5_bridge.order_send真发
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import os
import logging

logger = logging.getLogger(__name__)
router = APIRouter()
_app_mode = "SHADOW"


def get_mode() -> str:
    return _app_mode


class BuyRequest(BaseModel):
    symbol: str = "XAUUSD"
    lots: float = 0.05
    sl: float = 0.0
    tp: float = 0.0
    thesis: str = ""


class SellRequest(BaseModel):
    ticket: int
    reason: str = "close"


class ModeRequest(BaseModel):
    mode: str = "SHADOW"


@router.post("/api/buy")
async def buy(req: BuyRequest):
    from core import positions, risk
    from core.mt5_bridge import bridge
    mode = _app_mode
    if mode == "LIVE":
        if os.getenv("LIVE_TRADING_DISABLED", "false").lower() == "true":
            raise HTTPException(403, "实盘交易已锁定")
        ok, msg = risk.validate_buy(req.symbol, req.lots, positions.count(), 10000, 0)
        if not ok:
            raise HTTPException(400, msg)
    if mode == "LIVE":
        if not bridge.init_for_trade(
            login=int(os.getenv("MT5_LOGIN", "0")),
            password=os.getenv("MT5_PASSWORD", ""),
            server=os.getenv("MT5_SERVER", ""),
        ):
            raise HTTPException(503, "MT5 下单连接失败")
        try:
            result = bridge.order_send(req.symbol, "BUY", req.lots, sl=req.sl, tp=req.tp, comment=req.thesis)
        finally:
            bridge.shutdown_trade()
        if result is None or not result.get("ok"):
            err = result.get("comment", "unknown") if result else "MT5 返回空"
            raise HTTPException(500, f"下单失败: {err}")
        ticket = result["ticket"]
        positions.add(ticket, req.symbol, "BUY", req.lots, result["price"], req.sl, [req.tp], mode, req.thesis)
        return {"ok": True, "ticket": ticket, "mode": mode}
    else:
        price = 0.0
        try:
            if bridge.init_readonly():
                df = bridge.copy_rates(req.symbol, "M1", 1)
                if df is not None and len(df) > 0:
                    price = float(df["close"].iloc[-1])
        except Exception:
            pass
        if price <= 0:
            price = req.sl + 12
        import time
        ticket = int(time.time() * 1000) % 1000000
        positions.add(ticket, req.symbol, "BUY", req.lots, price, req.sl, [req.tp], mode, req.thesis)
        return {"ok": True, "ticket": ticket, "mode": mode}


@router.post("/api/sell")
async def sell(req: SellRequest):
    from core import positions
    from core.mt5_bridge import bridge
    mode = _app_mode
    pos = positions.get(req.ticket)
    if not pos:
        raise HTTPException(404, f"持仓未找到: ticket={req.ticket}")
    if mode == "LIVE":
        if not bridge.init_for_trade(
            login=int(os.getenv("MT5_LOGIN", "0")),
            password=os.getenv("MT5_PASSWORD", ""),
            server=os.getenv("MT5_SERVER", ""),
        ):
            raise HTTPException(503, "MT5 下单连接失败")
        try:
            result = bridge.close_position(req.ticket)
        finally:
            bridge.shutdown_trade()
        if result is None or not result.get("ok"):
            err = result.get("error", "unknown") if result else "MT5 返回空"
            raise HTTPException(500, f"平仓失败: {err}")
        pnl = result["pnl"]
    else:
        pnl = 0.0
    positions.close(req.ticket, pnl, req.reason)
    return {"ok": True, "pnl": pnl}


@router.post("/api/unmonitor")
async def unmonitor(req: SellRequest):
    from core import positions
    removed = positions.remove(req.ticket, req.reason or "unmonitor")
    if not removed:
        raise HTTPException(404, f"持仓未找到: ticket={req.ticket}")
    return {"ok": True, "ticket": req.ticket}


@router.post("/api/mode")
async def switch_mode(req: ModeRequest):
    global _app_mode
    new_mode = req.mode.upper()
    if new_mode not in ("SHADOW", "LIVE"):
        raise HTTPException(400, "模式必须是 SHADOW 或 LIVE")
    _app_mode = new_mode
    return {"ok": True, "mode": _app_mode, "trading_locked": False}


@router.get("/api/positions")
async def list_positions():
    """获取持仓列表 + 实时severity计算"""
    from core import positions
    pos_list = positions.list_all()
    # 每次请求重新计算severity
    positions.inspect_all(consec_losses=0, m5_data={})
    return positions.list_all()


@router.post("/api/positions/escape/{ticket}")
async def escape_position(ticket: int):
    """标记逃生"""
    from core import positions
    pos = positions.mark_escape(ticket)
    if not pos:
        raise HTTPException(404, f"持仓未找到: ticket={ticket}")
    return {"ok": True, "ticket": ticket, "severity": pos.get("severity", 0)}
