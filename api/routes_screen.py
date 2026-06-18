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


@router.post("/run")
async def run_scan() -> Any:
    """
    Phase 8 v5 async-jobified scan trigger:

    1. Cache hit (200) — return cached results immediately
    2. Cache miss (202) — return job_id for polling (FE: GET /api/run/status/{id})
       · dedup_key aware: same key reuses running job_id
    """
    from core.scanner import (
        scan_all_async, load_symbols, _get_cache_lock,
        _cache, TIMEFRAMES, DATA_MODE, SCAN_CACHE_TTL_S, SCAN_COUNT_DEFAULT,
    )
    from core.mt5_bridge import bridge
    from core.job_manager import jm as job_manager

    symbols = load_symbols(bridge)

    # 1. cache hit fast-path
    lock = _get_cache_lock()
    now = time.time()
    async with lock:
        if (
            _cache["data"]
            and (now - _cache["ts"]) < SCAN_CACHE_TTL_S
            and _cache["data_mode"] == DATA_MODE
        ):
            cached_results = {
                s: _cache["data"].get(s, {tf: None for tf in TIMEFRAMES})
                for s in symbols
            }
            logger.info("run_scan cache hit · %d sym · age=%.1fs",
                        len(symbols), now - _cache["ts"])
            connected = await bridge.heartbeat_ping_async(timeout=3.0)
            # Build evaluate decisions from cached market data
            decisions = _evaluate_results(cached_results)
            return {
                "data_mode": bridge.data_mode,
                "state": bridge.state.value,
                "symbol_count": len(symbols),
                "results": decisions,
                "summary": _summary(cached_results),
                "health": {
                    "heartbeat": connected,
                    "last_heartbeat": bridge.last_heartbeat,
                    "reconnect_count": bridge.reconnect_count,
                },
                "cached": True,
                "scan_async": False,
                "age_s": round(now - _cache["ts"], 1),
            }

    # 2. cache miss → enqueue scan via JobManager (dedup-aware, MUST FIX #1)
    async def _scan_closure():
        # scan_all_async internally uses asyncio.Lock for cache update safety
        return await scan_all_async(bridge, symbols, use_cache=False)

    dedup_key = (
        f"scan:nsym={len(symbols)}:mode={DATA_MODE}:cnt={SCAN_COUNT_DEFAULT}:bucket={int(now//30)}"
    )
    job_id = job_manager.create_scan_job(_scan_closure, dedup_key=dedup_key)
    job = job_manager.get(job_id)
    logger.info("run_scan enqueued job_id=%s · attach=%d · key=%s",
                job_id[:8], job.get("attach_count", 1), dedup_key[:32])
    return JSONResponse(
        status_code=202,
        content={
            "job_id": job_id,
            "state": "running",
            "deduped": job.get("attach_count", 1) > 1,
            "message": "scan job accepted · dedup to active if same dedup_key",
            "poll_url": f"/api/run/status/{job_id}",
            "symbol_count": len(symbols),
            "ts_started": job.get("ts_started"),
        },
    )


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

