"""
经纪商配置管理模块 — Phase 11:
  · 加载 config/profiles/*.yaml 多经纪商配置
  · symbol mapping: canonical -> broker_symbol
  · 活跃 profile 切换 (env + session)
  · 提供给 scanner / bridge / routes 使用
"""
import os
import yaml
import logging
from pathlib import Path
from typing import Dict, Optional, List, Any

logger = logging.getLogger(__name__)

PROFILES_DIR = Path(__file__).resolve().parent.parent / "config" / "profiles"
_ENV_PROFILE_KEY = "YUJIN_BROKER_PROFILE"


# ============================================================
# 数据模型
# ============================================================

class BrokerProfile:
    """单个经纪商配置"""

    def __init__(self, raw: dict):
        self.id: str = raw.get("id", "unknown")
        self.name: str = raw.get("name", self.id)
        self.description: str = raw.get("description", "")
        self.default: bool = raw.get("default", False)
        self.server: str = raw.get("server", "")
        self.path: str = raw.get("path", "")

        # symbol_map: canonical -> broker_symbol
        raw_map: Dict[str, str] = raw.get("symbol_map", {}) or {}
        self._symbol_map: Dict[str, str] = {}
        for canonical, broker_sym in raw_map.items():
            c = canonical.upper()
            b = (broker_sym or canonical).upper()
            self._symbol_map[c] = b

        # 反向映射: broker_symbol -> canonical (用于 MT5 动态拉取时反向)
        self._reverse_map: Dict[str, str] = {b: c for c, b in self._symbol_map.items()}

        # symbol_overrides: canonical -> {param: value}
        self.symbol_overrides: Dict[str, dict] = raw.get("symbol_overrides", {}) or {}

    def to_broker_symbol(self, canonical: str) -> str:
        """将标准化品种名映射为经纪商实际品种名"""
        c = canonical.upper()
        if c in self._symbol_map:
            return self._symbol_map[c]
        # 无映射时默认用原名称
        return canonical

    def to_canonical(self, broker_symbol: str) -> str:
        """将经纪商品种名反向映射为标准化品种名"""
        b = broker_symbol.upper()
        if b in self._reverse_map:
            return self._reverse_map[b]
        # 无反向映射时返回原名称
        return broker_symbol

    def get_canonical_symbols(self) -> List[str]:
        """返回该 profile 支持的所有标准化品种列表 (按 symbols.yaml 顺序)"""
        # 从 symbol_map 的 key 提取 canonical 名, 保留顺序
        return list(self._symbol_map.keys())

    def get_broker_symbols(self) -> List[str]:
        """返回该 profile 在经纪商终端中的实际品种名列表"""
        return list(set(self._symbol_map.values()))

    def get_override(self, canonical: str, param: str, default=None):
        """获取品种参数覆盖值"""
        overrides = self.symbol_overrides.get(canonical, {})
        return overrides.get(param, default)

    def to_dict(self) -> dict:
        """序列化为 API 可用的 dict"""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "default": self.default,
            "server": self.server,
            "symbol_count": len(self._symbol_map),
            "canonical_symbols": self.get_canonical_symbols(),
        }


# ============================================================
# 加载 & 缓存
# ============================================================

_profiles: Dict[str, BrokerProfile] = {}
_loaded = False


def _load_all() -> Dict[str, BrokerProfile]:
    """扫描 config/profiles/*.yaml 加载所有经纪商配置"""
    global _loaded
    if _loaded:
        return _profiles

    if not PROFILES_DIR.exists():
        logger.warning("profiles dir not found: %s", PROFILES_DIR)
        _loaded = True
        return _profiles

    found = 0
    for yaml_path in sorted(PROFILES_DIR.glob("*.yaml")):
        try:
            with open(yaml_path, "r", encoding="utf-8") as f:
                raw = yaml.safe_load(f)
            if not raw or "id" not in raw:
                logger.warning("skip invalid profile: %s", yaml_path.name)
                continue
            profile = BrokerProfile(raw)
            _profiles[profile.id] = profile
            found += 1
            logger.info("loaded broker profile '%s' (%s)", profile.id, yaml_path.name)
        except Exception as e:
            logger.warning("failed to load profile %s: %s", yaml_path.name, e)

    _loaded = True
    logger.info("loaded %d broker profiles from %s", found, PROFILES_DIR)
    return _profiles


def get_profile(profile_id: Optional[str] = None) -> BrokerProfile:
    """
    获取指定或当前活跃的经纪商配置。
    优先级:
      1. 传入 profile_id
      2. 环境变量 YUJIN_BROKER_PROFILE
      3. 默认 profile (default: true)
      4. 第一个可用的 profile
    """
    profiles = _load_all()
    if not profiles:
        raise RuntimeError("no broker profiles found in config/profiles/")

    # 1. 按传入 ID
    if profile_id and profile_id in profiles:
        return profiles[profile_id]

    # 2. 按环境变量
    env_id = os.getenv(_ENV_PROFILE_KEY)
    if env_id and env_id in profiles:
        return profiles[env_id]

    # 3. 找 default profile
    for p in profiles.values():
        if p.default:
            return p

    # 4. 第一个
    return next(iter(profiles.values()))


def list_profiles() -> List[BrokerProfile]:
    """列出所有可用经纪商"""
    profiles = _load_all()
    return list(profiles.values())


def list_profiles_dict() -> List[dict]:
    """列出所有可用经纪商 (dict 格式供 API)"""
    return [p.to_dict() for p in list_profiles()]


def switch_profile(profile_id: str) -> BrokerProfile:
    """切换当前经纪商 (写入环境变量, 重启后仍保留需写入 .env)"""
    profiles = _load_all()
    if profile_id not in profiles:
        raise ValueError(f"unknown broker profile: {profile_id}")

    profile = profiles[profile_id]
    # 设置环境变量 (当前进程生效)
    os.environ[_ENV_PROFILE_KEY] = profile_id
    logger.info("switched to broker profile '%s' (%s)", profile_id, profile.name)
    return profile


def get_active_profile() -> BrokerProfile:
    """获取当前活跃 profile (简写)"""
    return get_profile()


def reload_profiles():
    """强制重新加载 (开发/调试用)"""
    global _loaded, _profiles
    _loaded = False
    _profiles = {}
    return _load_all()


def profile_to_broker_symbol(canonical: str, profile_id: Optional[str] = None) -> str:
    """工具函数: 将标准化品种名转为经纪商品种名"""
    profile = get_profile(profile_id)
    return profile.to_broker_symbol(canonical)


def profile_to_canonical(broker_symbol: str, profile_id: Optional[str] = None) -> str:
    """工具函数: 将经纪商品种名转为标准化品种名"""
    profile = get_profile(profile_id)
    return profile.to_canonical(broker_symbol)
