"""
经纪商配置路由 — Phase 11:
  · GET  /api/brokers      — 列出所有可用经纪商配置
  · POST /api/brokers/switch — 切换当前经纪商
"""
import os
import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, List


class SwitchReq(BaseModel):
    profile_id: str

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/brokers", tags=["brokers"])


@router.get("")
async def list_brokers() -> Dict[str, Any]:
    """返回所有可用经纪商配置列表 + 当前活跃配置"""
    try:
        from core.broker_profiles import list_profiles_dict, get_active_profile
        profiles = list_profiles_dict()
        active = get_active_profile()
        return {
            "profiles": profiles,
            "active_id": active.id,
            "active_name": active.name,
            "count": len(profiles),
        }
    except Exception as e:
        logger.warning("list_brokers failed: %s", e)
        return {
            "profiles": [],
            "active_id": None,
            "active_name": None,
            "count": 0,
            "error": str(e),
        }


@router.post("/switch")
async def switch_broker(req: SwitchReq) -> Dict[str, Any]:
    """切换当前经纪商配置 (当前进程生效)"""
    try:
        from core.broker_profiles import switch_profile

        profile = switch_profile(req.profile_id)

        # 记录切换
        logger.info("broker switched to '%s' (%s)", profile.id, profile.name)
        return {
            "ok": True,
            "profile_id": profile.id,
            "profile_name": profile.name,
            "symbol_count": profile.to_dict().get("symbol_count", 0),
            "message": f"已切换到 {profile.name} · 当前进程生效, 重启后需写 .env 永久保留",
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error("switch_broker failed: %s", e)
        raise HTTPException(status_code=500, detail=f"切换失败: {e}")
