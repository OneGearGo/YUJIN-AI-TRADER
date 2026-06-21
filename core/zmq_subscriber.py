"""
ZMQ Subscriber — Phase 3:
async task 连 EA ZMQ PUB/SUB · 收 tick/bar → 更新 data_pool 缓存。

铁律: C5 — PUB/SUB 会丢消息，不加重传
铁律: B2 — 不在 async 里阻塞，用 zmq.asyncio
"""
import asyncio
import json
import logging
from typing import Optional

import zmq
import zmq.asyncio

logger = logging.getLogger(__name__)

ZMQ_ENDPOINT = "tcp://127.0.0.1:5555"

_subscriber_task: Optional[asyncio.Task] = None


async def _zmq_loop(pool):
    """ZMQ SUB 主循环 · 收一条处理一条"""
    ctx = zmq.asyncio.Context()
    sock = ctx.socket(zmq.SUB)
    sock.connect(ZMQ_ENDPOINT)
    sock.setsockopt(zmq.SUBSCRIBE, b"")
    logger.info("[ZMQ] Subscriber connected → %s", ZMQ_ENDPOINT)

    try:
        while True:
            try:
                raw = await sock.recv_string()
                msg = json.loads(raw)
                msg_type = msg.get("type")

                if msg_type == "tick":
                    sym = msg.get("symbol")
                    bid = msg.get("bid")
                    ask = msg.get("ask")
                    if sym and bid is not None and ask is not None:
                        pool.update_tick(sym, bid, ask, msg.get("time", ""), msg.get("spread", 0))

                elif msg_type == "bar":
                    sym = msg.get("symbol")
                    tf = msg.get("tf")
                    if sym and tf:
                        bar = {
                            "time": msg.get("time", ""),
                            "open": msg.get("o"),
                            "high": msg.get("h"),
                            "low": msg.get("l"),
                            "close": msg.get("c"),
                            "volume": 0,
                        }
                        pool.update_bar(sym, tf, bar)

            except zmq.Again:
                continue
            except json.JSONDecodeError as e:
                logger.warning("[ZMQ] JSON decode error: %s", e)
            except Exception as e:
                logger.error("[ZMQ] Message handler error: %s", e)
    except asyncio.CancelledError:
        logger.info("[ZMQ] Subscriber cancelled")
    finally:
        sock.close()
        ctx.term()
        logger.info("[ZMQ] Subscriber closed")


def start_subscriber(pool):
    """lifespan startup 调 · 创建 asyncio Task"""
    global _subscriber_task
    if _subscriber_task is not None and not _subscriber_task.done():
        logger.info("[ZMQ] Subscriber already running")
        return
    loop = asyncio.get_running_loop()
    _subscriber_task = loop.create_task(_zmq_loop(pool))
    logger.info("[ZMQ] Subscriber task created")


async def stop_subscriber():
    """lifespan shutdown 调 · cancel + await"""
    global _subscriber_task
    if _subscriber_task is not None and not _subscriber_task.done():
        _subscriber_task.cancel()
        try:
            await _subscriber_task
        except asyncio.CancelledError:
            pass
        _subscriber_task = None
