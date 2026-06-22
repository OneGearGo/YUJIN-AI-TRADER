"""
扫描路由 · Phase 8 v5.1 · 救命药二 (post-review fix):

 · POST /api/run →
    · cache hit(200 + result + cached=True)
    · cache miss → jm.create_scan_job(_scan_closure, dedup_key=...) → 202 + job_id
 · GET /api/run/status/{job_id} → polling
 · GET /api/jobs → admin
 · GET /api/symbols unchanged
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
import time
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["screen"])

# ── Evaluation cache: avoid re-running strategy.evaluate() on every poll ──
_EVAL_CACHE: Dict[str, dict] = {}      # {symbol: entry_dict}
_EVAL_CACHE_TS: float = 0.0            # timestamp of last full evaluation
_EVAL_CACHE_TTL: float = 30.0          # seconds before cache is considered stale


def _get_eval_cache() -> Dict[str, dict]:
    """Return evaluation cache if fresh, empty dict otherwise."""
    if time.time() - _EVAL_CACHE_TS < _EVAL_CACHE_TTL:
        return _EVAL_CACHE
    return {}


@router.post("/run")
async def run_scan() -> Any:
    from core.mt5_bridge import bridge
    from core.data_pool import get_pool
    from core.scanner import load_symbols

    symbols = load_symbols(bridge)
    pool = get_pool()

    import pandas as pd
    from core.strategy import evaluate as _eval_fn
    sym_configs = _load_sym_configs()

    # Check if we can reuse cached evaluation results (avoid re-running every poll)
    cached = _get_eval_cache()
    need_reeval = not cached
    if need_reeval:
        logger.info("eval cache stale — running strategy.evaluate() for %d symbols", len(symbols))

    decisions = []
    bridge_connected = bridge.state.value == "CONNECTED"
    has_any_real_score = False

    for sym in symbols:
        bid = (pool._ticks.get(sym) or {}).get("bid", 0)
        ask = (pool._ticks.get(sym) or {}).get("ask", 0)
        spread = (pool._ticks.get(sym) or {}).get("spread", 0)
        has_tick = bool(bid > 0)

        # Start with cached evaluation results if available
        cached_entry = cached.get(sym, {})

        # Build eval_data only when cache is stale (avoid per-poll overhead)
        eval_data = {}
        if need_reeval:
            for tf in ["M5", "H1", "H4"]:
                rows = pool.get_rows_for_routes(sym, tf)
                if rows:
                    eval_data[tf] = pd.DataFrame(rows)
            # Fallback: bridge.copy_rates() when pool has no OHLC AND bridge is connected
            if not eval_data and bridge_connected:
                try:
                    for tf, count in [("M5", 200), ("H1", 200), ("H4", 200)]:
                        df = bridge.copy_rates(sym, tf, count)
                        if df is not None and len(df) > 0:
                            eval_data[tf] = df
                except Exception:
                    pass

        has_ohlc = bool(eval_data)

        # Use cached status/conv/pri if available, else derive from tick/ohlc
        _has_real = has_tick or has_ohlc or (
            cached_entry.get("ema_score", 0) > 0 or
            cached_entry.get("dxy_score", 0) > 0 or
            cached_entry.get("fvg_score", 0) > 0
        )
        entry = {
            "symbol": sym,
            "status": cached_entry.get("status") or ("action" if _has_real else "watch"),
            "conv": cached_entry.get("conv") or (0.5 if _has_real else 0),
            "pri": cached_entry.get("pri") or (50 if _has_real else 0),
            "spread": spread,
            "bid": bid,
            "ask": ask,
            "ema_score": cached_entry.get("ema_score", 0.0),
            "dxy_score": cached_entry.get("dxy_score", 0.0),
            "fvg_score": cached_entry.get("fvg_score", 0.0),
            "thesis": cached_entry.get("thesis", ""),
            "reason": cached_entry.get("reason", ""),
        }

        # Run evaluate when cache is stale AND we have OHLC data
        if need_reeval and has_ohlc:
            try:
                cfg = sym_configs.get(sym, {})
                sym_config = {
                    "spread_max": cfg.get("spread_max", 20),
                    "gap_max_pct": cfg.get("gap_max_pct", 0.5),
                    "pip_value": cfg.get("pip_value", 0.0001),
                    "lot_step": cfg.get("lot_step", 0.01),
                    "decimals": cfg.get("decimals", 5),
                    "category": cfg.get("category", "forex"),
                }
                result = _eval_fn(sym, eval_data, sym_config)
                if result:
                    entry["status"] = getattr(result, "status", entry["status"])
                    entry["conv"] = getattr(result, "conv", entry["conv"])
                    entry["pri"] = getattr(result, "priority", entry["pri"])
                    entry["ema_score"] = getattr(result, "ema_score", 0.0)
                    entry["dxy_score"] = getattr(result, "dxy_score", 0.0)
                    entry["fvg_score"] = getattr(result, "fvg_score", 0.0)
                    entry["thesis"] = getattr(result, "thesis", "")
                    entry["reason"] = getattr(result, "reason", "")
            except Exception as e:
                logger.warning("evaluate(%s) failed: %s", sym, e)
                entry["reason"] = str(e)

        if entry["ema_score"] > 0 or entry["dxy_score"] > 0 or entry["fvg_score"] > 0:
            has_any_real_score = True

        decisions.append(entry)

    # Update evaluation cache after re-evaluation:
    # - Always refresh TTL so we don't re-evaluate on next poll
    # - Only populate cache entries with real scores (skip zeros so they re-evaluate next cycle)
    if need_reeval:
        global _EVAL_CACHE, _EVAL_CACHE_TS
        if has_any_real_score:
            # Merge: keep entries with scores, update entries that got new scores
            for d in decisions:
                if d["ema_score"] > 0 or d["dxy_score"] > 0 or d["fvg_score"] > 0:
                    _EVAL_CACHE[d["symbol"]] = d
        # Always refresh TTL — prevents hammering evaluate() when bridge is disconnected
        _EVAL_CACHE_TS = time.time()

    return {
        "data_mode": bridge.data_mode,
        "symbol_count": len(decisions),
        "decisions": decisions,
        "portfolio": {},
        "positions": [],
        "cached": not need_reeval,
    }


@router.get("/run/status/{job_id}")
async def get_run_status(job_id: str) -> Any:
    """polling endpoint — returns status of job_id (running/done/failed)."""
    from core.job_manager import jm as job_manager
    from core.mt5_bridge import bridge

    job = job_manager.get(job_id)
    if not job:
        raise HTTPException(
            status_code=404,
            detail=f"job_id {job_id} not found (already GC'd or never existed)",
        )

    state = job.get("state")
    # Strip internal keys (e.g. _task asyncio.Task) — JSONResponse cannot serialize them.
    job_clean = {k: v for k, v in job.items() if k != "_task"}
    if state == "done":
        results = job.get("result") or {}
        connected = await bridge.heartbeat_ping_async(timeout=3.0)
        # Run strategy evaluate on scanned data
        decisions = _evaluate_results(results)
        return {
            "job_id": job_id,
            "state": "done",
            "data_mode": bridge.data_mode,
            "bridge_state": bridge.state.value,
            "symbol_count": len(results),
            "results": decisions,
            "summary": _summary(results),
            "health": {
                "heartbeat": connected,
                "last_heartbeat": bridge.last_heartbeat,
                "reconnect_count": bridge.reconnect_count,
            },
            "ts_started": job.get("ts_started"),
            "ts_finished": job.get("ts_finished"),
            "duration_s": round(
                (job.get("ts_finished", time.time()) - job.get("ts_started", time.time())),
                2,
            ),
            "attach_count": job.get("attach_count", 1),
        }
    elif state == "failed":
        return JSONResponse(
            status_code=500,
            content={
                "job_id": job_id,
                "state": "failed",
                "error": job_clean.get("error"),
                "ts_started": job_clean.get("ts_started"),
                "ts_finished": job_clean.get("ts_finished"),
            },
        )
    elif state == "running":
        return {
            "job_id": job_id,
            "state": "running",
            "ts_started": job_clean.get("ts_started"),
            "attach_count": job_clean.get("attach_count", 1),
            "elapsed_s": round(time.time() - job_clean.get("ts_started", time.time()), 1),
        }
    return {"job_id": job_id, "state": state}


@router.get("/jobs")
async def list_jobs(limit: int = 20) -> Dict[str, Any]:
    """admin/debug — recent jobs list."""
    from core.job_manager import jm as job_manager
    jobs = job_manager.list_recent(limit=min(limit, 100))
    return {
        "count": len(jobs),
        "active_id": job_manager._active_scan_job_id,
        "jobs": jobs,
    }


@router.get("/symbols")
async def get_symbols() -> Dict[str, Any]:
    from core.scanner import load_symbols
    from core.mt5_bridge import bridge
    syms = load_symbols(bridge)
    return {"count": len(syms), "symbols": syms}


def _summary(results) -> Dict[str, Dict[str, int]]:
    """Backward-compat: returns K-line counts per symbol/timeframe."""
    out: Dict[str, Dict[str, int]] = {}
    for sym, tfs in (results or {}).items():
        out[sym] = {tf: (0 if df is None else len(df)) for tf, df in tfs.items()}
    return out


_SYM_CONFIG_CACHE: Dict[str, dict] | None = None

def _load_sym_configs() -> Dict[str, dict]:
    """
    Load per-symbol configuration from config/symbols.yaml.
    Returns {symbol: {spread_max, pip_value, lot_step, decimals, category, ...}}
    Cached after first load.
    """
    global _SYM_CONFIG_CACHE
    if _SYM_CONFIG_CACHE is not None:
        return _SYM_CONFIG_CACHE

    from pathlib import Path
    import yaml
    p = Path(__file__).resolve().parent.parent / "config" / "symbols.yaml"
    if not p.exists():
        logger.warning("symbols.yaml not found at %s, using fallback defaults", p)
        _SYM_CONFIG_CACHE = {}
        return _SYM_CONFIG_CACHE

    with open(p, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    configs: Dict[str, dict] = {}
    for entry in raw.get("symbols", []):
        sym = entry.get("symbol") or entry.get("sym")
        if sym:
            configs[sym] = {
                "spread_max": entry.get("spread_max", 50),
                "gap_max_pct": entry.get("gap_max_pct", 0.5),
                "pip_value": entry.get("pip_value", 0.1),
                "lot_step": entry.get("lot_step", 0.01),
                "decimals": entry.get("decimals", 2),
                "category": entry.get("category", "forex"),
                "trading_hours": entry.get("trading_hours", ""),
                "dxy_corr": entry.get("dxy_corr", False),
            }

    _SYM_CONFIG_CACHE = configs
    logger.info("loaded %d symbol configs from symbols.yaml", len(configs))
    return configs


def _evaluate_results(results) -> Dict[str, dict]:
    """
    Run strategy.evaluate() on each symbol's scanned data.
    Loads per-symbol config from symbols.yaml.
    Returns {symbol: {status, died, conv, priority, spread, ema_align,
                       fvg, bos, dxy_align, size_lots, sl, tp, ...}}
    """
    from core.strategy import evaluate

    sym_configs = _load_sym_configs()
    out: Dict[str, dict] = {}

    for sym, tfs in (results or {}).items():
        try:
            # Get per-symbol config or fall back to defaults
            sym_config = sym_configs.get(sym, {
                "spread_max": 50,
                "gap_max_pct": 0.5,
                "pip_value": 0.1,
                "lot_step": 0.01,
                "decimals": 2,
                "category": "forex",
            })

            # Build data dict with only the timeframes evaluate() needs
            eval_data = {}
            for tf in ["M5", "H1", "H4"]:
                df = tfs.get(tf)
                eval_data[tf] = df

            result = evaluate(sym, eval_data, sym_config)
            if result is not None:
                entry = {
                    "sym": sym,
                    "category": sym_config.get("category", "forex"),
                    "status": result.status,
                    "died": result.died,
                    "conv": getattr(result, "conv", 0),
                    "priority": getattr(result, "priority", 0),
                    "spread": getattr(result, "spread", 0),
                    "gap_pct": getattr(result, "gap_pct", 0),
                    "ema_align": getattr(result, "ema_align", False),
                    "fvg": getattr(result, "fvg", False),
                    "sweep": getattr(result, "sweep", False),
                    "bos": getattr(result, "bos", "none"),
                    "ema_score": getattr(result, "ema_score", 0.0),
                    "dxy_score": getattr(result, "dxy_score", 0.0),
                    "fvg_score": getattr(result, "fvg_score", 0.0),
                    "lots": getattr(result, "lots", 0),
                    "sl": getattr(result, "sl", 0),
                    "tp": getattr(result, "tp", [])[0] if getattr(result, "tp", None) else 0,
                    "exit_plan": getattr(result, "exit_plan", ""),
                    "thesis": getattr(result, "thesis", ""),
                    "reason": getattr(result, "reason", ""),
                }
                out[sym] = entry
        except Exception as exc:
            logger.warning("evaluate(%s) failed: %s", sym, exc)
            out[sym] = {
                "sym": sym,
                "status": "error",
                "died": None,
                "conv": 0,
                "priority": 0,
                "spread": 0,
                "reason": f"evaluate error: {exc}",
            }
    return out

