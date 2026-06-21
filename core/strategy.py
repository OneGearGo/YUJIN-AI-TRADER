"""
6 道闸门策略 · 按品种类别分 3 套参数
  ─ forex:   EMA20/50 · ATR 1.5x · FVG 30 · 周一早盘过滤 ✓
  ─ index:   EMA20/50 · ATR 1.5x · FVG 30 · 周一早盘过滤 ✓
  ─ crypto:  EMA12/26 · ATR 2.5x · FVG 50 · 周一早盘过滤 ✗
"""
import pandas as pd
import numpy as np
from typing import Dict, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import logging
import core.risk as risk

logger = logging.getLogger(__name__)


# ── 品种类别策略参数 ──────────────────────────────────────────────

@dataclass(frozen=True)
class StrategyParams:
    """单类别 6 道门可调参数（冻结防误改）。"""
    # Gate 2 — EMA
    ema_fast_period: int = 20
    ema_slow_period: int = 50
    gate2_min_tf_bars: int = 50          # 每个周期最少 K 线数

    # Gate 3 — 结构
    fvg_lookback: int = 30
    sweep_lookback: int = 30

    # Gate 4 — 节奏
    atr_displacement_ratio: float = 1.5  # body > ATR * ratio
    bos_lookback: int = 20

    # Gate 1 — 避雷
    filter_monday_open: bool = True      # 周一 9:30 前过滤
    gap_max_pct_default: float = 0.3     # yml 有 gap_max_pct 时以 yml 为准

    # Gate 6 — 风控
    risk_coefficient: float = 1.0


# 三套预设
FOREX_PARAMS = StrategyParams(
    ema_fast_period=20,
    ema_slow_period=50,
    gate2_min_tf_bars=50,
    fvg_lookback=30,
    sweep_lookback=30,
    atr_displacement_ratio=1.5,
    bos_lookback=20,
    filter_monday_open=True,
    gap_max_pct_default=0.3,
    risk_coefficient=1.0,
)

INDEX_PARAMS = StrategyParams(
    ema_fast_period=20,
    ema_slow_period=50,
    gate2_min_tf_bars=50,
    fvg_lookback=30,
    sweep_lookback=30,
    atr_displacement_ratio=1.5,
    bos_lookback=20,
    filter_monday_open=True,
    gap_max_pct_default=0.3,
    risk_coefficient=1.0,
)

CRYPTO_PARAMS = StrategyParams(
    ema_fast_period=12,
    ema_slow_period=26,
    gate2_min_tf_bars=30,          # 加密周期短，少要历史
    fvg_lookback=50,               # 更大窗口过滤噪音
    sweep_lookback=50,
    atr_displacement_ratio=2.5,    # 加密波动大，提阈值防假信号
    bos_lookback=20,
    filter_monday_open=False,      # 24/7 无周一早盘概念
    gap_max_pct_default=1.0,
    risk_coefficient=0.5,
)

COMMODITY_PARAMS = StrategyParams(
    ema_fast_period=20,
    ema_slow_period=50,
    gate2_min_tf_bars=50,
    fvg_lookback=30,
    sweep_lookback=30,
    atr_displacement_ratio=1.5,
    bos_lookback=20,
    filter_monday_open=True,
    gap_max_pct_default=0.5,
    risk_coefficient=0.7,
)

# 按 category 查找参数，兜底使用 forex
STRATEGY_PARAMS: Dict[str, StrategyParams] = {
    "forex": FOREX_PARAMS,
    "index": INDEX_PARAMS,
    "crypto": CRYPTO_PARAMS,
    "commodity": COMMODITY_PARAMS,
}


# ── 公用计算 ──────────────────────────────────────────────────────

@dataclass
class ScanResult:
    symbol: str = ""
    status: str = "reject"
    died: Optional[int] = None
    verdict_v: str = "reject"
    conv: float = 0.0
    thesis: str = ""
    spread: int = 0
    gap_pct: float = 0.0
    ema_align: bool = False
    fvg: bool = False
    sweep: bool = False
    disp: bool = False
    bos: str = "none"
    atr_m5: float = 0.0
    priority: int = 0
    lots: float = 0.0
    sl: float = 0.0
    tp: list = field(default_factory=list)
    exit_plan: str = ""
    reason: str = ""


def calc_ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def calc_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    tr = pd.concat([
        df["high"] - df["low"],
        (df["high"] - df["close"].shift(1)).abs(),
        (df["low"] - df["close"].shift(1)).abs(),
    ], axis=1).max(axis=1)
    return tr.rolling(window=period).mean()


def detect_fvg(df: pd.DataFrame, lookback: int = 30) -> bool:
    if len(df) < lookback:
        return False
    r = df.tail(lookback)
    for i in range(2, len(r)):
        if r["low"].iloc[i] > r["high"].iloc[i - 2]:
            return True
        if r["high"].iloc[i] < r["low"].iloc[i - 2]:
            return True
    return False


def detect_sweep(df: pd.DataFrame, lookback: int = 30) -> bool:
    if len(df) < lookback:
        return False
    r = df.tail(lookback)
    h, lo = r["high"].values, r["low"].values
    for i in range(3, len(r)):
        ph = max(h[i - 3:i])
        pl = min(lo[i - 3:i])
        if h[i] > ph and r["close"].iloc[i] < ph:
            return True
        if lo[i] < pl and r["close"].iloc[i] > pl:
            return True
    return False


def detect_displacement(df: pd.DataFrame, atr: pd.Series,
                        ratio: float = 1.5) -> bool:
    if len(df) < 2 or atr is None or len(atr) == 0:
        return False
    body = abs(df.iloc[-1]["close"] - df.iloc[-1]["open"])
    a = atr.iloc[-1]
    if pd.isna(a) or a <= 0:
        return False
    return body > a * ratio


def detect_bos(df: pd.DataFrame, lookback: int = 20) -> str:
    if len(df) < lookback + 1:
        return "none"
    r = df.tail(lookback + 1)
    lc = r["close"].iloc[-1]
    ph = r["high"].iloc[:-1].max()
    pl = r["low"].iloc[:-1].min()
    if lc > ph:
        return "bullish"
    if lc < pl:
        return "bearish"
    return "none"


# ── 6 道门（均接受 params 参数）────────────────────────────────────

def gate1_avoid(symbol, df_m5, sym_config, params: StrategyParams):
    """避雷门：点差 / 跳空 / 周一早盘（crypto 跳过早盘检查）。"""
    spread, gap = 0, 0.0
    if df_m5 is None or len(df_m5) < 2:
        return False, "M5 数据不足", spread, gap
    spread = int(df_m5["spread"].iloc[-1]) if "spread" in df_m5.columns else 0
    smax = sym_config.get("spread_max", 50)
    if spread > smax:
        return False, f"点差 {spread} > {smax}", spread, gap
    prev_p = df_m5.iloc[-2]["close"]
    if prev_p > 0:
        gap = round(abs(df_m5.iloc[-1]["open"] - prev_p) / prev_p * 100, 4)
    gap_max = sym_config.get("gap_max_pct", params.gap_max_pct_default)
    if gap > gap_max:
        return False, f"跳空 {gap:.2f}%", spread, gap
    # 周一早盘过滤 — crypto 跳过
    if params.filter_monday_open:
        now = datetime.now(timezone(timedelta(hours=8)))
        if now.weekday() == 0 and now.hour < 9 and now.minute < 30:
            return False, "周早盘异常", spread, gap
    return True, "避雷通过", spread, gap


def gate2_confluence(df_m5, df_h1, df_h4, params: StrategyParams):
    """共振门：多周期 EMA 方向一致（使用类别特化的周期）。"""
    if df_m5 is None or df_h1 is None or df_h4 is None:
        return False, "周期数据不足"
    aligns = []
    for df in [df_m5, df_h1, df_h4]:
        if len(df) < params.gate2_min_tf_bars:
            aligns.append(False)
            continue
        e_fast = calc_ema(df["close"], params.ema_fast_period).iloc[-1]
        e_slow = calc_ema(df["close"], params.ema_slow_period).iloc[-1]
        aligns.append(e_fast > e_slow)
    if not (all(aligns) or not any(aligns)):
        return False, "EMA 未对齐"
    return True, "共振通过"


def gate3_structure(df_h4, df_h1, params: StrategyParams):
    """结构门：FVG / Sweep 检测，lookback 随类别调整。"""
    fvg = (detect_fvg(df_h4, params.fvg_lookback)
           if df_h4 is not None and len(df_h4) >= params.fvg_lookback
           else False)
    swp = (detect_sweep(df_h1, params.sweep_lookback)
           if df_h1 is not None and len(df_h1) >= params.sweep_lookback
           else False)
    if fvg or swp:
        return True, "结构通过", fvg, swp
    return False, "无 FVG 且无 sweep", fvg, swp


def gate4_rhythm(df_m5, params: StrategyParams):
    """节奏门：ATR displacement + BOS，阈值随类别调整。"""
    if df_m5 is None or len(df_m5) < 20:
        return False, "M5 数据不足", 0.0, "none"
    atr = calc_atr(df_m5, 14)
    if len(atr) == 0 or pd.isna(atr.iloc[-1]):
        return False, "ATR 失败", 0.0, "none"
    atr_val = float(atr.iloc[-1])
    disp = detect_displacement(df_m5, atr, params.atr_displacement_ratio)
    bos = detect_bos(df_m5, params.bos_lookback)
    if disp or bos != "none":
        return True, "节奏通过", atr_val, bos
    return False, "节奏不足", atr_val, bos


def gate5_context():
    """上下文门（占位）。"""
    return True, "上下文通过(占位)"


def gate6_risk(symbol, price, atr_val, params: StrategyParams,
               direction="BUY"):
    """风控门：SL/TP/手数计算，使用类别风险系数。"""
    atr = atr_val if atr_val and atr_val > 0 else price * 0.005
    sl_dist = atr * 1.5
    if direction == "BUY":
        sl = round(price - sl_dist, 2)
        tps = [round(price + sl_dist * 1.2, 2),
               round(price + sl_dist * 2.0, 2)]
    else:
        sl = round(price + sl_dist, 2)
        tps = [round(price - sl_dist * 1.2, 2),
               round(price - sl_dist * 2.0, 2)]
    # 手数计算已内置 category_risk_coefficient（通过 risk.py 读 yml）
    # params.risk_coefficient 仅用于 thesis 展示，不重复施加
    lots = risk.calculate_lot(symbol, price, sl)
    return True, "风控完成", {"sl": sl, "tp": tps, "lots": lots,
                            "sl_dist": round(sl_dist, 2)}


# ── 主入口 ────────────────────────────────────────────────────────

def evaluate(symbol, data, sym_config):
    """
    按品种 category 选择策略参数，串 6 道门。
    sym_config: 来自 routes_screen._load_sym_configs() 的每个品种配置。
    """
    category = sym_config.get("category", "forex")
    params = STRATEGY_PARAMS.get(category, FOREX_PARAMS)

    d = ScanResult(symbol=symbol)
    df_m5 = data.get("M5")
    df_h1 = data.get("H1")
    df_h4 = data.get("H4")
    price = float(df_m5["close"].iloc[-1]) if df_m5 is not None and len(df_m5) > 0 else 0

    # Gate 1
    ok, reason, sp, gp = gate1_avoid(symbol, df_m5, sym_config, params)
    d.spread, d.gap_pct = sp, gp
    if not ok:
        d.status, d.died, d.reason = "reject", 1, reason
        d.thesis = reason
        return d

    # Gate 2
    ok, reason = gate2_confluence(df_m5, df_h1, df_h4, params)
    d.ema_align = ok
    if not ok:
        d.status, d.died, d.reason = "reject", 2, reason
        d.conv, d.thesis = 0.2, reason
        return d

    # Gate 3
    ok, reason, fvg, swp = gate3_structure(df_h4, df_h1, params)
    d.fvg, d.sweep = fvg, swp
    if not ok:
        d.status, d.died, d.reason = "reject", 3, reason
        d.conv, d.thesis = 0.4, reason
        return d

    # Gate 4
    ok, reason, atr_v, bos = gate4_rhythm(df_m5, params)
    d.disp, d.bos, d.atr_m5 = ok, bos, atr_v
    if not ok:
        d.status, d.died, d.reason = "reject", 4, reason
        d.conv, d.thesis = 0.5, reason
        return d

    # Gate 5
    ok, reason = gate5_context()
    if not ok:
        d.status, d.died, d.reason = "reject", 5, reason
        d.conv, d.thesis = 0.6, reason
        return d

    # Gate 6
    ok, reason, ri = gate6_risk(symbol, price, d.atr_m5, params)
    if not ok:
        d.status, d.died, d.reason = "reject", 6, reason
        d.conv, d.thesis = 0.7, reason
        return d

    # ALL PASSED
    d.status = "action"
    d.lots, d.sl, d.tp = ri["lots"], ri["sl"], ri["tp"]
    d.priority = 78
    d.exit_plan = f"SL {ri['sl_dist']}p TP1 {ri['tp'][0]} TP2 {ri['tp'][1]}"
    d.verdict_v, d.conv = "pass", 0.85
    d.thesis = (
        f"6门全过 [{category}]: {bos} BOS "
        f"disp={ok} fvg={fvg} swp={swp} "
        f"risk_coeff={params.risk_coefficient}"
    )
    d.reason = "all 6 gates passed"
    return d
