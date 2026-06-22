"""
YUJIN AI TRADER — FastAPI 入口 · ZMQ 架构:

  lifespan:
    · asyncio.wait_for(bridge.init_readonly_async, 10) + heartbeat 启  · 与  v4 同
    · shutdown: stop_heartbeat + shutdown_all_async
"""
import os
import asyncio
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(
    level=os.getenv("MT5_LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期 — bridge init + heartbeat + graceful degrade."""
    print("=" * 50)
    print(">>>[YUJIN AI TRADER] yujin-mt5 v0.6.0 启动 (ZMQ架构)")
    print(f">>> http://127.0.0.1:{os.getenv('APP_PORT', '8000')}")
    print(f">>> MT5_DATA_MODE = {os.getenv('MT5_DATA_MODE', 'SHADOW')}")
    print("=" * 50)

    mt5_init_ok = False
    try:
        from core.mt5_bridge import bridge
        mode = bridge.data_mode
        if mode == "SHADOW":
            logger.info("SHADOW mode · 不连 MT5 · 数据走扫描器种子")
        else:
            try:
                mt5_init_ok = await asyncio.wait_for(
                    bridge.init_readonly_async(),
                    timeout=10.0,
                )
            except (asyncio.TimeoutError, TimeoutError):
                logger.warning("MT5 init_readonly_async 超时 10s · 降级启")
            except Exception as e:
                logger.error("MT5 init_readonly_async 异常: %s · 降级", e)

        bridge.start_heartbeat()
        if mt5_init_ok:
            logger.info("MT5 readonly init + heartbeat OK state=%s", bridge.state.value)
        else:
            logger.warning("MT5 readonly init 未完成 · heartbeat 心跳 reconnect 补")

        # ZMQ subscriber — EA push → data_pool cache
        try:
            from core.data_pool import get_pool
            from core.zmq_subscriber import start_subscriber
            pool = get_pool()
            start_subscriber(pool)
            logger.info("[ZMQ] Subscriber started")
        except Exception as e:
            logger.error("[ZMQ] Subscriber start 异常: %s · 降级", e)

    except Exception as e:
        logger.error("Lifespan MT5 init 总异常: %s · 继续 启", e)

    yield

    try:
        from core.mt5_bridge import bridge
        bridge.stop_heartbeat()
        await bridge.shutdown_all_async()
        logger.info("MT5 shutdown_all OK")
    except Exception as e:
        logger.error("MT5 shutdown 异常: %s", e)

    try:
        from core.zmq_subscriber import stop_subscriber
        await stop_subscriber()
        logger.info("[ZMQ] Subscriber stopped")
    except Exception as e:
        logger.error("[ZMQ] Subscriber stop 异常: %s", e)

    try:
        # v7: cancel all active SSE streams
        from api.routes_stream import cancel_all_streams
        await cancel_all_streams()
        logger.info("SSE streams cancelled OK")
        # v8: cancel all active WS connections
        from api.routes_ws import cancel_all_ws
        await cancel_all_ws()
        logger.info("WS connections closed OK")
    except Exception as e:
        logger.error("SSE streams cancel 异常: %s", e)

    print(">>>[YUJIN AI TRADER] yujin-mt5 关闭")


app = FastAPI(
    title="YUJIN AI TRADER",
    version="0.6.0",
    lifespan=lifespan,
)

from api.routes_account import router as account_router
from api.routes_screen import router as screen_router
from api.routes_trade import router as trade_router
from api.routes_broker import router as broker_router
from api.routes_stream import router as stream_router
from api.routes_ws import router as ws_router
from api.routes_ws import cancel_all_ws



app.include_router(account_router)
app.include_router(screen_router)
app.include_router(trade_router)
app.include_router(broker_router)
app.include_router(stream_router)
app.include_router(ws_router)

static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/")
async def index():
    return FileResponse(str(static_dir / "index.html"))


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("APP_PORT", "8000"))
    host = os.getenv("APP_HOST", "127.0.0.1")
    uvicorn.run("app:app", host=host, port=port, reload=False)
