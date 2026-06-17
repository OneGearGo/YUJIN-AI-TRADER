"""
交易路由 -- POST /api/buy, POST /api/sell, POST /api/unmonitor
POST /api/mode, GET /api/positions
SHADOW: 只写 JSONL + 加入监控, 不调 mt5.order_send
LIVE: 调 mt5_bridge.order_send 真发
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import os
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

# 模式状态: 重启归零到 SHADOW(铁律)
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
    """一键买入 -- SHADOW 写日志, LIVE 真发单"""
    from core import positions, risk
    from core.mt5_bridge import bridge

    mode = _app_mode

    # LIVE 模式校验
    if mode == "LIVE":
        if os.getenv("LIVE_TRADING_DISABLED", "false").lower() == "true":
            raise HTTPException(403, "实盘交易已锁定")
        ok, msg = risk.validate_buy(req.symbol, req.lots, positions.count(), 10000, 0)
        if not ok:
            raise HTTPException(400, msg)

    if mode == "LIVE":
        # LIVE: 调 mt5_bridge 真发单
        if not bridge.init_for_trade(
            login=int(os.getenv("MT5_LOGIN", "0")),
            password=os.getenv("MT5_PASSWORD", ""),
            server=os.getenv("MT5_SERVER", ""),
        ):
            raise HTTPException(503, "MT5 下单连接失败")
        try:
            result = bridge.order_send(req.symbol, "BUY", req.lots,
                                       sl=req.sl, tp=req.tp, comment=req.thesis)
        finally:
            bridge.shutdown_trade()

        if result is None or not result.get("ok"):
            err = result.get("comment", "unknown") if result else "MT5 返回空"
            raise HTTPException(500, f"下单失败: {err}")

        ticket = result["ticket"]
        positions.add(ticket, req.symbol, "BUY", req.lots,
                      result["price"], req.sl, [req.tp], mode, req.thesis)
        return {"ok": True, "ticket": ticket, "mode": mode}

    else:
        # SHADOW: 获取实时报价 + 写日志 + 加入监控
        price = 0.0
        try:
            if bridge.init_readonly():
                tick = bridge.symbol_info(req.symbol)
                # 用 copy_rates 最后一根收盘价近似
                df = bridge.copy_rates(req.symbol, "M1", 1)
                if df is not None and len(df) > 0:
                    price = float(df["close"].iloc[-1])
        except Exception:
            pass
        if price <= 0:
            price = req.sl + 12  # fallback

        import time
        ticket = int(time.time() * 1000) % 1000000
        positions.add(ticket, req.symbol, "BUY", req.lots,
                      price, req.sl, [req.tp], mode, req.thesis)
        return {"ok": True, "ticket": ticket, "mode": mode}


@router.post("/api/sell")
async def sell(req: SellRequest):
    """平仓 -- LIVE 真平, SHADOW 只移除"""
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
    """取消监控 -- 不真平仓, 只从 positions.json 移除"""
    from core import positions
    removed = positions.remove(req.ticket, req.reason or "unmonitor")
    if not removed:
        raise HTTPException(404, f"持仓未找到: ticket={req.ticket}")
    return {"ok": True, "ticket": req.ticket}


@router.post("/api/mode")
async def switch_mode(req: ModeRequest):
    """切换 SHADOW / LIVE"""
    global _app_mode
    new_mode = req.mode.upper()
    if new_mode not in ("SHADOW", "LIVE"):
        raise HTTPException(400, "模式必须是 SHADOW 或 LIVE")
    _app_mode = new_mode
    return {"ok": True, "mode": _app_mode, "trading_locked": False}


@router.get("/api/positions")
async def list_positions():
    """获取持仓列表"""
    from core import positions
    return positions.list_all()
