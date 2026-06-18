"""
YUJIN AI TRADER — FastAPI 入口 · Phase 8 v4 · 救命药一:

  lifespan:
    · asyncio.wait_for(bridge.init_readonly_async, timeout=10)  · 卡 启
    · asyncio.wait_for(warm_cache_async, timeout=10)  warm 交   do  降级
    · 启 heartbeat (daemon thread ·  异步  ·  -- 独 thread  heart 诚    loop  ts)
    · shutdown: stop_heartbeat + shutdown_all_async

  · 启动  hanging(lifespan  卡 心跳_mt5_executor  雪崩)·
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
    """应用生命周期 — Phase 8 v4:asyncio.wait_for 全包 +  启 heartbeat daemon"""
    print("=" * 50)
    print(">>>[YUJIN AI TRADER] yujin-mt5 v0.4.0 启动 (Phase 8 v4 · 救命药一)")
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
                logger.warning("MT5 init_readonly_async 超时 10s · 降级 启( 后台 reconnect)")
            except Exception as e:
                logger.error("MT5 init_readonly_async 异常: %s · 降级 启", e)

        bridge.start_heartbeat()
        if mt5_init_ok:
            logger.info("MT5 readonly init + heartbeat OK state=%s", bridge.state.value)
        else:
            logger.warning("MT5 readonly init 未完成 · heartbeat 心跳 reconnect 补")

        # warm cache · 降级
        try:
            from core.scanner import warm_cache_async
            syms = await asyncio.wait_for(
                warm_cache_async(bridge, timeout=10.0),
                timeout=11.0,
            )
            logger.info("warm_cache ok sym=%d", syms)
        except (asyncio.TimeoutError, TimeoutError):
            logger.warning("warm_cache_async 超时 · 降级 冷却启  · 首次 /api/run 会 数据慢")
        except Exception as e:
            logger.error("warm_cache_async 异常: %s · 降", e)

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
    print(">>>[YUJIN AI TRADER] yujin-mt5 关闭")


app = FastAPI(
    title="YUJIN AI TRADER",
    version="0.4.0",
    lifespan=lifespan,
)

# ============================================================
# 路由注册
# ============================================================
from api.routes_account import router as account_router
from api.routes_screen import router as screen_router
from api.routes_trade import router as trade_router

app.include_router(account_router)
app.include_router(screen_router)
app.include_router(trade_router)

# ============================================================
# 静态文件托管
# ============================================================
static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/")
async def index():
    """首页 — 返回前端看板"""
    return FileResponse(str(static_dir / "index.html"))


# ============================================================
# 启动入口
# ============================================================
if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("APP_PORT", "8000"))
    host = os.getenv("APP_HOST", "127.0.0.1")
    uvicorn.run("app:app", host=host, port=port, reload=False)
