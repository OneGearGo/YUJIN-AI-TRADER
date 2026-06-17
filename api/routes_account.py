"""
账户路由 -- GET /api/account, GET /api/health
"""
from fastapi import APIRouter
from datetime import datetime, timedelta, timezone
import os
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

# 启动时检查 .env
_env_file = os.path.join(os.path.dirname(__file__), '..', '.env')
if not os.path.exists(_env_file):
    logger.warning(".env 文件不存在, MT5 连接将使用默认值")


@router.get("/api/account")
async def get_account():
    """获取账户信息 -- 先尝试 MT5 只读连接"""
    try:
        from core.mt5_bridge import bridge
        info = bridge.account_info()
        if info:
            return {
                **info,
                "mode": os.getenv("APP_MODE", "SHADOW"),
                "trading_locked": os.getenv("LIVE_TRADING_DISABLED", "false").lower() == "true",
            }
    except Exception:
        pass
    return {
        "login": 0, "balance": 10000.0, "equity": 10000.0,
        "margin": 0.0, "free_margin": 10000.0, "leverage": 100,
        "server": "DEMO", "mode": os.getenv("APP_MODE", "SHADOW"),
        "trading_locked": False,
    }


@router.get("/api/health")
async def health():
    """健康检查"""
    mt5_ok = False
    try:
        from core.mt5_bridge import bridge
        mt5_ok = bridge.is_connected
        if mt5_ok:
            mt5_ok = bridge.account_info() is not None
    except Exception:
        pass
    return {
        "ok": True, "mt5_connected": mt5_ok,
        "mode": os.getenv("APP_MODE", "SHADOW"),
        "ts": datetime.now(timezone(timedelta(hours=8))).isoformat(),
    }
