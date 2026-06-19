"""
经纪商配置路由 — Phase 11:
  · GET  /api/brokers      — 列出所有可用经纪商配置
  · POST /api/brokers/switch — 切换当前经纪商
"""
import os
import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, List, Optional


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


def _unknown_profile_detail(
    profile_id: str,
    available_ids: List[str],
    message: Optional[str] = None,
) -> Dict[str, Any]:
    """Build the typed-404 detail dict for unknown-profile errors.

    Funnels the pre-validation guard (inside try) and the defense-in-depth
    `except ValueError` arm through one construction point so both arms stay
    in sync: {error, profile_id, available} + optional `message` when the
    downstream layer raised ValueError.

    Polish #5.5 hoist: prior Polish #5.3 inline-duplicated this dict in two
    arms; collapse to a single helper.

    Polish #5.4 contract: frontend `switchBroker()` in static/index.html
    must read detail.error / .available; the helper is the source of truth
    for that contract.
    """
    d: Dict[str, Any] = {
        "error": "unknown_profile",
        "profile_id": profile_id,
        "available": available_ids,
    }
    if message is not None:
        d["message"] = message
    return d


@router.post("/switch")
async def switch_broker(req: SwitchReq) -> Dict[str, Any]:
    """切换当前经纪商配置 (当前进程生效)

    On unknown profile_id: typed 404 with structured detail
    {"error":"unknown_profile","profile_id":...,"available":[sorted ids]}
    so the frontend switchBroker() can render cleanly without KeyError
    surfacing as 500.

    Polish #5.4 follow-up: frontend `switchBroker()` in static/index.html
    must read response.detail.error / .available instead of treating
    detail as a string (see Polish #5.3 code-review carry-over).
    """
    try:
        from core.broker_profiles import list_profiles, switch_profile

        # Pre-validate profile_id against the loaded set BEFORE delegating
        # so we return typed 404 detail instead of relying on ValueError.
        available_ids = sorted(p.id for p in list_profiles())
        if req.profile_id not in available_ids:
            raise HTTPException(
                status_code=404,
                detail=_unknown_profile_detail(req.profile_id, available_ids),
            )

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
    except HTTPException:
        # Re-raise typed 404 from the pre-validation guard unchanged.
        raise
    except ValueError as e:
        # Defence-in-depth: race between list_profiles() and switch_profile()
        available_ids = sorted(p.id for p in list_profiles())
        raise HTTPException(
            status_code=404,
            detail=_unknown_profile_detail(
                req.profile_id, available_ids, message=str(e),
            ),
        )
    except Exception as e:
        logger.error("switch_broker failed: %s", e)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "switch_failed",
                "profile_id": req.profile_id,
                "message": str(e),
            },
        )
