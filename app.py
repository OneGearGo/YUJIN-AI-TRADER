"""
YUJIN AI TRADER · FastAPI 入口
瘦路由 + 静态文件托管
"""
from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI(
    title="YUJIN AI TRADER",
    version="0.1.0",
    docs_url=None,
    redoc_url=None,
)

# ── 挂载静态文件 ──────────────────────────────────
STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# ── 根路由: 返回前端看板 ──────────────────────────
@app.get("/", response_class=HTMLResponse)
async def index():
    index_html = STATIC_DIR / "index.html"
    return HTMLResponse(content=index_html.read_text(encoding="utf-8"))

# ── 健康检查 ──────────────────────────────────────
@app.get("/api/health")
async def health():
    return {"ok": True, "mt5_connected": False, "ts": "DEMO"}
