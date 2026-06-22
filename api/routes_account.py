"""
账户路由 · Phase 8 v4 · 救命药一:

  · /api/health/mt5   await bridge.heartbeat_ping_async  · 卡 event loop ·
  · 返 mode/state/connected/last_heartbeat/reconnect_count
"""
import os
from fastapi import APIRouter

router = APIRouter(prefix="/api", tags=["account"])


@router.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "yujin-mt5",
        "version": "v0.4.0",
        "data_mode": os.getenv("MT5_DATA_MODE", "SHADOW"),
    }


@router.get("/status")
async def status():
    """前端autoConnect检测端点的状态"""
    from core.mt5_bridge import bridge
    return {
        "has_key": True,
        "trading_locked": os.getenv("LIVE_TRADING_DISABLED", "true").lower() == "true",
        "public_demo": False,
        "mode": bridge.data_mode,
        "chain": "forex",
    }


@router.get("/health/mt5")
async def health_mt5():
    """MT5 连接状态探针 — Phase 8 v4:async heartbeat_ping_async · 卡 event loop"""
    try:
        from core.mt5_bridge import bridge
        connected = await bridge.heartbeat_ping_async(timeout=3.0)
        return {
            "mode": bridge.data_mode,
            "state": bridge.state.value,
            "connected": connected,
            "last_heartbeat": bridge.last_heartbeat,
            "reconnect_count": bridge.reconnect_count,
        }
    except Exception as e:
        return {
            "mode": "UNKNOWN",
            "state": "ERROR",
            "connected": False,
            "last_heartbeat": None,
            "reconnect_count": 0,
            "error": str(e),
        }


@router.post("/mode")
async def set_mode(mode: str):
    valid = ("SHADOW", "LIVE_DRY_RUN", "LIVE")
    mode = mode.upper()
    if mode not in valid:
        return {"ok": False, "error": f"invalid mode: {mode}"}
    return {
        "ok": True,
        "instruction": f"将 MT5_DATA_MODE={mode} 写入 .env 并重启进程生效",
    }
