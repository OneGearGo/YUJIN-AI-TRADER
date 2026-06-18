"""
交易路由 · Phase 8 v4 · 救命药一:

  · /api/buy 、/api/sell   await bridge.execute_trade_async 单 executor 调 ·
  ·  · 拆 init/order/shutdown  心跳  插入串 上下文乱
  · LIVE_TRADING_DISABLED 双  四门控 · HTTP 423/409/502/400
"""
import os
from fastapi import APIRouter, HTTPException
from typing import Dict, Any

router = APIRouter(prefix="/api", tags=["trade"])


@router.post("/buy")
async def buy(symbol: str, lots: float = 0.01, sl: float = 0.0, tp: float = 0.0) -> Dict[str, Any]:
    """买入 — Phase 8 v4:atomic execute_trade_async ·  event loop ·  卖给·"""
    return await _send(symbol, "BUY", lots, sl, tp)


@router.post("/sell")
async def sell(symbol: str, lots: float = 0.01, sl: float = 0.0, tp: float = 0.0) -> Dict[str, Any]:
    """卖出 — 同上"""
    return await _send(symbol, "SELL", lots, sl, tp)


@router.post("/unmonitor")
async def unmonitor(symbol: str) -> Dict[str, Any]:
    """从监控池移除 — Phase 10 引入 · 返 占位"""
    return {"ok": True, "symbol": symbol, "note": "Phase 10 implements"}


async def _send(symbol: str, side: str, lots: float, sl: float, tp: float) -> Dict[str, Any]:
    """下单内部:四门控 → atomic execute_trade_async"""
    if os.getenv("LIVE_TRADING_DISABLED", "true").lower() == "true":
        raise HTTPException(status_code=423, detail="LIVE_TRADING_DISABLED=true · 悟空授权切 LIVE 后再下单")
    from core.mt5_bridge import bridge
    if bridge.data_mode != "LIVE":
        raise HTTPException(status_code=409, detail=f"data_mode={bridge.data_mode} ≠ LIVE · 不下单")
    login = int(os.getenv("MT5_LOGIN", "0"))
    password = os.getenv("MT5_PASSWORD", "")
    server = os.getenv("MT5_SERVER", "")
    if not login or not password or not server:
        raise HTTPException(status_code=400, detail="MT5 凭据未填 .env")
    try:
        result = await bridge.execute_trade_async(
            symbol=symbol, side=side, lots=lots, sl=sl, tp=tp,
            comment=f"phase8 {side}",
            login=login, password=password, server=server,
            timeout=30.0,
        )
        return _format_order(result, symbol, side, lots)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"MT5 trade 执行异常: {e}")


def _format_order(result, symbol, side, lots) -> Dict[str, Any]:
    if result is None:
        return {"ok": False, "symbol": symbol, "side": side, "lots": lots, "error": "MT5 无回执"}
    return {
        "ok": result.get("ok", False),
        "symbol": symbol,
        "side": side,
        "lots": lots,
        "ticket": result.get("ticket"),
        "price": result.get("price"),
        "retcode": result.get("retcode"),
        "error": result.get("error"),
        "comment": result.get("comment"),
    }
