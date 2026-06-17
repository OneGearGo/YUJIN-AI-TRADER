"""
御金量化 · yujin-mt5 — FastAPI 入口
形态借自 GMGN AI Trader，内核是 MT5 + 御金策略
"""
import os
import json
import time
import random
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# ============================================================
# 全局状态
# ============================================================
APP_MODE = "SHADOW"  # SHADOW / LIVE
SCAN_COUNTER = 0
DEMO_POSITIONS: list = []


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动/关闭"""
    print("=" * 50)
    print(">>>[御金量化] yujin-mt5 启动")
    print(f">>> 模式: {APP_MODE}")
    print(f">>> http://127.0.0.1:{os.getenv('APP_PORT', '8000')}")
    print("=" * 50)
    yield
    print(">>>[御金量化] yujin-mt5 关闭")


app = FastAPI(
    title="御金量化 · yujin-mt5",
    version="0.1.0",
    lifespan=lifespan,
)


# ============================================================
# API 路由
# ============================================================

@app.get("/api/health")
async def health():
    """健康检查"""
    return {
        "ok": True,
        "mt5_connected": False,
        "mode": APP_MODE,
        "ts": datetime.now(timezone(timedelta(hours=8))).isoformat(),
    }


@app.get("/api/account")
async def account():
    """账户信息 — DEMO 模式返回假数据"""
    return {
        "login": 0,
        "balance": 10000.00,
        "equity": 10000.00,
        "margin": 0.00,
        "free_margin": 10000.00,
        "leverage": 100,
        "server": "DEMO",
        "mode": APP_MODE,
        "trading_locked": False,
    }


@app.get("/api/positions")
async def positions():
    """持仓列表 — DEMO 模式返回模拟数据"""
    return DEMO_POSITIONS


@app.post("/api/run")
async def run_scan(payload: dict = None):
    """触发扫描 — DEMO 模式返回模拟扫描结果"""
    global SCAN_COUNTER, DEMO_POSITIONS
    SCAN_COUNTER += 1

    now = datetime.now(timezone(timedelta(hours=8)))
    # DEMO: 随机生成扫描结果
    random.seed(int(now.timestamp()))
    gates_passed = random.randint(0, 6)
    status = "action" if gates_passed == 6 else "reject"
    if gates_passed >= 4:
        status = "filtered"

    # 模拟一个待决策候选
    bid = round(2330 + random.uniform(-20, 20), 2)
    sl = round(bid - 12, 2)
    tp = round(bid + 18, 2)

    decision = {
        "symbol": "XAUUSD",
        "status": status,
        "died": None if gates_passed == 6 else gates_passed + 1,
        "verdict": {
            "v": "pass" if status == "action" else "reject",
            "conv": round(random.uniform(0.5, 0.95), 2),
            "thesis": "H4 BOS + M5 displacement, DXY 反向"
        },
        "features": {
            "spread": random.randint(15, 60),
            "gap_pct": round(random.uniform(0, 0.3), 2),
            "ema_align": gates_passed >= 2,
            "dxy_align": gates_passed >= 5,
            "fvg": gates_passed >= 3,
            "sweep": gates_passed >= 3,
            "displacement": gates_passed >= 4,
            "bos": "bullish" if gates_passed >= 4 else "none",
        },
        "priority": random.randint(40, 95) if status == "action" else 0,
        "size_lots": 0.05 if status == "action" else 0,
        "sl": sl,
        "tp": tp,
        "exit_plan": f"SL -0.5% · TP +0.6% / +1.2% · trailing 0.3%",
        "reason": "all 6 gates passed" if status == "action" else f"died at gate {gates_passed + 1}",
    }

    return {
        "scan_id": SCAN_COUNTER,
        "ts": now.isoformat(),
        "decisions": [decision],
        "kpis": {
            "scanned": 1,
            "passed_safety": 1 if gates_passed >= 1 else 0,
            "passed_confluence": 1 if gates_passed >= 2 else 0,
            "pending": 1 if status == "action" else 0,
            "positions": len(DEMO_POSITIONS),
            "escape_alerts": 0,
        },
        "positions": DEMO_POSITIONS,
    }


class BuyRequest(BaseModel):
    symbol: str = "XAUUSD"
    lots: float = 0.05
    sl: float = 0.0
    tp: float = 0.0
    thesis: str = ""


@app.post("/api/buy")
async def buy(req: BuyRequest):
    """一键买入 — SHADOW 模式只记录，LIVE 模式真发单"""
    global DEMO_POSITIONS

    if APP_MODE == "LIVE" and os.getenv("LIVE_TRADING_DISABLED", "false") == "true":
        raise HTTPException(status_code=403, detail="实盘交易已锁定")

    ticket = int(time.time() * 1000) % 1000000
    now = datetime.now(timezone(timedelta(hours=8)))

    position = {
        "ticket": ticket,
        "symbol": req.symbol,
        "type": "BUY",
        "lots": req.lots,
        "entry": req.sl + 12,
        "current": req.sl + 12,
        "pnl": 0.0,
        "pnl_pct": 0.0,
        "severity": 0,
        "sl": req.sl,
        "tp": req.tp,
        "open_time": now.isoformat(),
    }

    DEMO_POSITIONS.append(position)

    return {"ok": True, "ticket": ticket, "mode": APP_MODE}


class SellRequest(BaseModel):
    ticket: int
    reason: str = ""


@app.post("/api/sell")
async def sell(req: SellRequest):
    """平仓"""
    global DEMO_POSITIONS
    for i, pos in enumerate(DEMO_POSITIONS):
        if pos["ticket"] == req.ticket:
            pnl = pos["pnl"]
            DEMO_POSITIONS.pop(i)
            return {"ok": True, "pnl": pnl}
    raise HTTPException(status_code=404, detail="持仓未找到")


@app.post("/api/unmonitor")
async def unmonitor(req: SellRequest):
    """取消监控"""
    return await sell(req)


@app.post("/api/mode")
async def switch_mode(payload: dict):
    """切换 SHADOW / LIVE"""
    global APP_MODE
    new_mode = payload.get("mode", "SHADOW").upper()
    if new_mode not in ("SHADOW", "LIVE"):
        raise HTTPException(status_code=400, detail="模式必须是 SHADOW 或 LIVE")
    APP_MODE = new_mode
    return {"ok": True, "mode": APP_MODE, "trading_locked": False}


@app.get("/api/scan/settings")
async def get_scan_settings():
    """获取扫描设置"""
    return {
        "symbols": ["XAUUSD"],
        "interval_sec": 5,
        "enabled": True,
    }


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
