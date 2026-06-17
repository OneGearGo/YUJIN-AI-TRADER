"""
御金量化 · yujin-mt5 — FastAPI 入口
形态借自 GMGN AI Trader，内核是 MT5 + 御金策略
"""
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from dotenv import load_dotenv

load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动/关闭"""
    print("=" * 50)
    print(">>>[御金量化] yujin-mt5 v0.2.0 启动")
    print(f">>> http://127.0.0.1:{os.getenv('APP_PORT', '8000')}")
    print("=" * 50)
    yield
    print(">>>[御金量化] yujin-mt5 关闭")


app = FastAPI(
    title="御金量化 · yujin-mt5",
    version="0.2.0",
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
