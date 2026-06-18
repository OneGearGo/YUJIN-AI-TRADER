"""
账户路由 · Phase 8:+ /api/health/mt5 状态探针
"""
import os
from fastapi import APIRouter

router = APIRouter(prefix="/api", tags=["account"])


@router.get("/health")
async def health():
    """通用健康检查"""
    return {
        "status": "ok",
        "service": "yujin-mt5",
        "version": "v0.3.0",
        "data_mode": os.getenv("MT5_DATA_MODE", "SHADOW"),
    }


@router.get("/health/mt5")
async def health_mt5():
    """MT5 连接状态探针 — Phase 8 返回 bridge state + last_heartbeat + reconnect_count"""
    try:
        from core.mt5_bridge import bridge
        return {
            "mode": bridge.data_mode,
            "state": bridge.state.value,
            "connected": bridge.heartbeat_ping(),
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
    """运行切 MT5_DATA_MODE — Phase 8 仅建议接口(实际生效由悟空重启进程)"""
    valid = ("SHADOW", "LIVE_DRY_RUN", "LIVE")
    mode = mode.upper()
    if mode not in valid:
        return {"ok": False, "error": f"invalid mode: {mode}"}
    return {
        "ok": True,
        "instruction": f"将 MT5_DATA_MODE={mode} 写入 .env 并重启进程生效",
    }
