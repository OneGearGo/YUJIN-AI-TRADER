"""
实时行情 SSE 流端点 — Phase 8 v7:

  · 5s tick (data_pool updates + health snapshot)
  · 10s heartbeat ping (keep-alive 防 6min proxy timeout)
  · 初始 返 event: snapshot · 后续 event: tick + event: ping
  · disconnect 检测: await request.is_disconnected()
  · GIL 解耦: data_pool.aggregate 走 asyncio.to_thread 不  block event loop
"""
import asyncio
import json
import logging
import time
from typing import AsyncIterator, Dict, Any
from sse_starlette.sse import EventSourceResponse, ServerSentEvent
from fastapi import APIRouter, Request

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["stream"])

TICK_INTERVAL_S = 5.0
HEARTBEAT_INTERVAL_S = 10.0

# cycle registry  · lifespan shutdown  中  一一 cancel 防 cos   leak
_active_streams: list = []


def _register_task(task: asyncio.Task):
    """lifespan shutdown  ref-track active SSE generator  ·  全 cancel"""
    _active_streams.append(task)


def _unregister_task(task: asyncio.Task):
    if task in _active_streams:
        _active_streams.remove(task)


async def cancel_all_streams():
    """lifespan shutdown 中  restart cancel all active SSE streams"""
    for task in list(_active_streams):
        try:
            task.cancel()
        except Exception:
            pass
    if _active_streams:
        await asyncio.gather(*_active_streams, return_exceptions=True)
    _active_streams.clear()


@router.get("/stream")
async def stream_live_data(request: Request):
    """
    Server-Sent Events endpoint for live market data.

    Initial yield: event: snapshot (full data_pool aggregate + health)
    Subsequent: event: tick (5s interval, health + updates) OR event: ping (heartbeat only)

    Format:
      event: snapshot | data: {"health": ..., "data": {sym: {tf: {rows, ...}}}
      event: tick | data: {"ts": ..., "health": ..., "updates": {...}}
      event: ping | data: {"ts": ..., "up": true}

    Auto-sends `retry: 3000` hint on first message for 3s reconnect interval.
    """
    from core.data_pool import get_pool
    from core.scanner import load_symbols, TIMEFRAMES

    pool = get_pool()
    loaded_symbols = load_symbols()

    async def event_generator() -> AsyncIterator[ServerSentEvent]:
        task = asyncio.current_task()
        if task is not None:
            _register_task(task)

        try:
            # 1. Initial snapshot
            if pool is not None and pool.is_ready():
                snapshot = await asyncio.to_thread(pool.aggregate, loaded_symbols, TIMEFRAMES)
                health = await asyncio.to_thread(pool.health)
            else:
                snapshot = {s: {tf: {"rows": [], "valid": False, "age_s": None, "last_kline_time": None}
                                 for tf in TIMEFRAMES} for s in loaded_symbols}
                health = {"is_ready": False, "cache_size": 0}
            yield ServerSentEvent(
                event="snapshot",
                data=json.dumps(
                    {"health": health, "data": snapshot, "ts": time.time()},
                    default=str,
                ),
                retry=3000,
            )
            logger.info("SSE snapshot sent: cache_size=%d", health.get("cache_size", 0))

            # 2. Tick loop with time-based heartbeat (fix v7.0.1: ping was gated
            # behind `x-front-stream-ping` header which no client ever sends;
            # result: ping NEVER fired → 60s nginx / 30s K8s ingress idle drops).
            last_ping_at = time.time()
            while True:
                # Disconnect detection
                if await request.is_disconnected():
                    logger.info("SSE client disconnected (clean exit)")
                    break
                await asyncio.sleep(TICK_INTERVAL_S)

                # Re-check disconnect (gracefully handles abort)
                if await request.is_disconnected():
                    break

                # Tick payload (5s cadence)
                if pool is not None and pool.is_ready():
                    try:
                        update = await asyncio.to_thread(pool.aggregate, loaded_symbols, TIMEFRAMES)
                        tick_health = await asyncio.to_thread(pool.health)
                    except Exception as e:
                        logger.exception("SSE tick aggregate exception: %s", e)
                        update = {}
                        tick_health = {"is_ready": False, "error": str(e)}
                else:
                    update = {}
                    tick_health = {"is_ready": False, "cache_size": 0}

                now = time.time()
                yield ServerSentEvent(
                    event="tick",
                    data=json.dumps(
                        {
                            "ts": now,
                            "health": tick_health,
                            "updates": update,
                            "symbol_count": len(loaded_symbols),
                        },
                        default=str,
                    ),
                )

                # Time-based heartbeat ping — 每 HEARTBEAT_INTERVAL_S 发一次,
                # 不依赖任何 header  · 防 proxy idle drop · 即使 tick payload 空
                # (pool dead / cold start) keeps connection alive
                if (now - last_ping_at) >= HEARTBEAT_INTERVAL_S:
                    yield ServerSentEvent(
                        event="ping",
                        data=json.dumps({"ts": now, "up": True, "tick_interval_s": TICK_INTERVAL_S}),
                    )
                    last_ping_at = now
        except asyncio.CancelledError:
            logger.info("SSE cancelled (server shutdown)")
            raise
        except Exception as e:
            logger.exception("SSE generator exception: %s", e)
        finally:
            if task is not None:
                _unregister_task(task)

    return EventSourceResponse(event_generator())
