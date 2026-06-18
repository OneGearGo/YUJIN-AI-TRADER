"""
YUJIN AI TRADER — FastAPI 入口 · 加 Phase 8:lifespan MT5 safe init + heartbeat
"""
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from contextlib import asynccontextmanager
import logging

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
    """应用生命周期 — Phase 8:启动 MT5 safe init + heartbeat · 关闭 heartbeat + 全关"""
    print("=" * 50)
    print(">>>[YUJIN AI TRADER] yujin-mt5 v0.3.0 启动 (Phase 8 scaffolding)")
    print(f">>> http://127.0.0.1:{os.getenv('APP_PORT', '8000')}")
    print(f">>> MT5_DATA_MODE = {os.getenv('MT5_DATA_MODE', 'SHADOW')}")
    print("=" * 50)
    try:
        from core.mt5_bridge import bridge
        mode = bridge.data_mode
        if mode == "SHADOW":
            logger.info("SHADOW mode · 不连 MT5 · 数据走扫描器种子")
        else:
            if bridge.init_readonly():
                bridge.start_heartbeat()
                logger.info("MT5 readonly init + heartbeat OK state=%s", bridge.state.value)
            else:
                logger.warning("MT5 readonly init 失败 · heartbeat 仍启动 · 由后台重连")
                bridge.start_heartbeat()
    except Exception as e:
        logger.error("Lifespan MT5 init 异常: %s", e)
    yield
    try:
        from core.mt5_bridge import bridge
        bridge.shutdown_all()
        logger.info("MT5 shutdown_all OK")
    except Exception as e:
        logger.error("MT5 shutdown 异常: %s", e)
    print(">>>[YUJIN AI TRADER] yujin-mt5 关闭")


app = FastAPI(
    title="YUJIN AI TRADER",
    version="0.3.0",
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
    uvicorn.run("app:app", host=host, port=port, reload=True)
