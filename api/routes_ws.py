"""
Phase 8 v8 WebSocket 双向交易端点:

  - /api/ws — WebSocket 连接
  - Client → Server: place_order, close_position, ping
  - Server → Client: positions_update, account_update, trade_result, pong, error
  - 后台 5s 自动推送持仓 + 账户更新
  - 断连自动清理后台任务
"""
import asyncio
import json
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)
router = APIRouter(tags=["ws"])    # Track active connections for lifespan shutdown
_active_connections: list = []


async def cancel_all_ws():
    """Lifespan shutdown: close all active WebSocket connections."""
    for conn in list(_active_connections):
        try:
            await conn.close(code=1001, reason="Server shutdown")
        except Exception:
            pass
    _active_connections.clear()


@router.websocket("/api/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    _active_connections.append(websocket)
    logger.info("WebSocket client connected (total: %d)", len(_active_connections))

    from core.mt5_bridge import bridge  # module-level singleton
    from core.data_pool import get_pool
    from core.scanner import load_symbols, TIMEFRAMES

    pool = get_pool()
    loaded_symbols = load_symbols()
    push_task: asyncio.Task | None = None

    try:
        # ── Background push task: positions + account every 5s ──
        async def _push_loop():
            while True:
                try:
                    await asyncio.sleep(5)
                    # Positions
                    pos = await bridge.positions_get_async(timeout=5)
                    await websocket.send_json({
                        "type": "positions_update",
                        "ts": asyncio.get_event_loop().time(),
                        "data": [_serialize_pos(p) for p in (pos or [])],
                    })
                    # Account info
                    acct = await bridge.account_info_async(timeout=5)
                    await websocket.send_json({
                        "type": "account_update",
                        "ts": asyncio.get_event_loop().time(),
                        "data": _serialize_account(acct),
                    })
                except asyncio.CancelledError:
                    break
                except WebSocketDisconnect:
                    break
                except Exception as e:
                    logger.warning("WS push_loop error: %s", e)

        push_task = asyncio.create_task(_push_loop())

        # ── Main receive loop ──
        while True:
            raw = await websocket.receive_text()
            msg = json.loads(raw)
            mt = msg.get("type", "")

            if mt == "ping":
                await websocket.send_json({"type": "pong"})

            elif mt == "place_order":
                symbol = msg.get("symbol", "")
                side = msg.get("side", "")
                lots = float(msg.get("lots", 0.01))
                sl = float(msg.get("sl", 0.0))
                tp = float(msg.get("tp", 0.0))
                comment = msg.get("comment", "phase9")

                if not symbol or side not in ("buy", "sell"):
                    await websocket.send_json({"type": "error", "message": "symbol/side required"})
                    continue
                if lots <= 0 or lots > 10:
                    await websocket.send_json({"type": "error", "message": "lots must be 0.01-10"})
                    continue

                try:
                    import os as _os
                    # Four gates (Phase 9): LIVE_TRADING_DISABLED / data_mode / credentials
                    if _os.getenv("LIVE_TRADING_DISABLED", "true").lower() == "true":
                        await websocket.send_json({"type": "error", "message": "LIVE_TRADING_DISABLED=true"})
                        continue
                    if bridge.data_mode != "LIVE":
                        await websocket.send_json({"type": "error", "message": f"data_mode={bridge.data_mode} != LIVE"})
                        continue

                    login = int(_os.environ.get("MT5_LOGIN", "0") or "0")
                    password = _os.environ.get("MT5_PASSWORD", "") or ""
                    server = _os.environ.get("MT5_SERVER", "") or ""
                    if not login or not password or not server:
                        await websocket.send_json({"type": "error", "message": "MT5 凭据未填"})
                        continue

                    result = await bridge.execute_trade_async(
                        symbol, side, lots, sl, tp, comment,
                        login, password, server,
                    )
                    await websocket.send_json({
                        "type": "trade_result",
                        "data": _format_trade_result(result, symbol, side, lots),
                    })
                except Exception as e:
                    await websocket.send_json({"type": "error", "message": str(e)})

            elif mt == "close_position":
                ticket = msg.get("ticket", 0)
                if not ticket:
                    await websocket.send_json({"type": "error", "message": "ticket required"})
                    continue
                try:
                    result = bridge.close_position(ticket)
                    await websocket.send_json({
                        "type": "trade_result",
                        "data": {"ticket": ticket, "result": str(result)},
                    })
                except Exception as e:
                    await websocket.send_json({"type": "error", "message": str(e)})

            else:
                await websocket.send_json({"type": "error", "message": f"unknown type: {mt}"})

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except Exception as e:
        logger.exception("WebSocket error: %s", e)
    finally:
        if websocket in _active_connections:
            _active_connections.remove(websocket)
        if push_task is not None:
            push_task.cancel()


def _serialize_pos(pos) -> dict:
    """Serialize position (MTPosition namedtuple) to JSON-safe dict."""
    if pos is None:
        return {}
    if isinstance(pos, dict):
        return pos
    try:
        return {
            "ticket": int(getattr(pos, "ticket", 0)),
            "symbol": str(getattr(pos, "symbol", "")),
            "type": int(getattr(pos, "type", 0)),
            "volume": float(getattr(pos, "volume", 0.0)),
            "price_open": float(getattr(pos, "price_open", 0.0)),
            "sl": float(getattr(pos, "sl", 0.0)),
            "tp": float(getattr(pos, "tp", 0.0)),
            "profit": float(getattr(pos, "profit", 0.0)),
            "swap": float(getattr(pos, "swap", 0.0)),
            "comment": str(getattr(pos, "comment", "")),
        }
    except Exception:
        return {}


def _format_trade_result(result, symbol: str, side: str, lots: float) -> dict:
    """将 MT5 execute_trade_async 返回值格式化为前端友好结构。"""
    if result is None:
        return {"ok": False, "symbol": symbol, "side": side, "lots": lots, "error": "MT5 无回执"}
    if isinstance(result, dict):
        return {
            "ok": result.get("retcode", 0) == 10009 or result.get("ok", False),
            "symbol": symbol,
            "side": side,
            "lots": lots,
            "ticket": result.get("ticket"),
            "price": result.get("price"),
            "retcode": result.get("retcode"),
            "error": result.get("error"),
            "comment": result.get("comment", ""),
        }
    return {"ok": False, "symbol": symbol, "side": side, "lots": lots, "error": str(result)}


def _serialize_account(acct) -> dict:
    """Serialize account_info object to dict (safe for JSON)."""
    if acct is None:
        return {}
    if isinstance(acct, dict):
        return acct
    # Assume namedtuple / object with attributes
    try:
        return {
            "login": getattr(acct, "login", 0),
            "balance": float(getattr(acct, "balance", 0.0)),
            "equity": float(getattr(acct, "equity", 0.0)),
            "margin": float(getattr(acct, "margin", 0.0)),
            "margin_free": float(getattr(acct, "margin_free", 0.0)),
            "leverage": int(getattr(acct, "leverage", 0)),
            "server": getattr(acct, "server", ""),
            "currency": getattr(acct, "currency", "USD"),
        }
    except Exception:
        return {}
