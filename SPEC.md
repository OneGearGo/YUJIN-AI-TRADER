# YUJIN AI TRADER · 需求规格说明书 (SPEC)

**仓库**:`YUJIN-AI-TRADER`(公开 · MIT)
**品牌**:YUJIN AI TRADER
**项目目录**:`F:\yujin-mt5\`(已落)
**版本**:v0.1(铸峰开工基线)
**更新日期**:2026-06-17

> 给铸峰、新接手者、AI 协作者的单文件上下文。读完这份 = 知道要做什么、为什么这么设计、当前进度、哪里要继续写。

---

## 1. 一句话定义

**形态借自 GMGN AI Trader 看板,内核是 MT5 行情 + 自己的交易策略。** 把"机器筛、人按成交"的人机分工套到 MT5 品种(**23 个核心品种起步**,架构按 60+ 配置驱动)上:外汇 7 + 交叉 3 + 指数 4 + 商品 3 + 加密 3 + 股票 3,覆盖 5 大类目;确定性规则抓全 → 结构/动量评分砍狠 → LLM 解释幸存者(可选)→ 用户一键下 MT5 单;同时实时监控持仓的逃生信号。

- **形态**:本地 Web 应用(FastAPI 后端 + 单页 HTML 前端,后端同源托管前端)。
- **用户**:自用 + 信任的少数人。各自本机跑、配自己的 MT5 账户。
- **支持账户**:FTMO 考核 / FTMO 实盘 / 模拟账户,右上角 MODE 切换 SHADOW(只记录)/ LIVE(真发单)。
- **风险声明**:纯交易工具,盈亏自负;不构成投资建议。

---

## 2. 核心定位决策(已拍)

- **人在环**:流水线只产出候选,不自动下单;通过全部闸门的候选带仓位摆在看板上等用户点"一键买入"。
- **形态可借,策略不可借**:借的是 UI/UX 形态(暗色看板、6 道闸门图标、severity 监控);策略逻辑、闸门定义、风险参数都是御金体系的内部物,跟 GMGN 没有业务关系。
- **借形态不是抄代码**:`static/index.html` 自己重写,不复用原站 JS/CSS(规避 LICENSE + 风格升级),只对照交互与组件。
- **配色彻底换**:不用原站柠檬黄+橙红+琥珀的 memetoken 配色,采用 A 极光深空(主推),详见 §8.2。

---

## 3. 铁律(铸峰红线,违反任意一条 = 打回)

### 3.1 来自用户/御金体系的红线
- **V4.5/御金Pro EA 一行不碰** — 那是独立项目,本项目完全自包含。代码、SET 文件、参数都不引用。
- **C 盘禁存** — 工具/数据/代码一律放 F 盘。本项目根目录:`F:\yujin-mt5\`(待悟空最终拍板,可能是 `F:\guanlan-mt5\` 或其他)。**桌面 yylzyh 文件夹是需求文档草稿位,不是项目根**。
- **MT5 终端用 `mt5.initialize(path=...)` 只读拉数据,不传 login/password** — 否则会把悟空从 GUI 踢出。流程:行情扫描用只读 init(不传凭据)→ 用户按"买入"时单独 init(传凭据)→ 下完单立刻 `mt5.shutdown()`。
- **多品种扩展:策略闸门写成"按品种配置驱动",不要 hardcode XAUUSD** — 第一版即使只跑 XAUUSD,代码组织也要按 6 品种预留。
- **JSONL 日志格式对齐原站**:`{ts, action, symbol, reason, ...}` 一行一事件,方便后续回测统计。

### 3.2 来自本项目的新红线
- **凭据不入仓不入库**:`.env` 文件加 `.gitignore`;仓库只放 `.env.example`(只留字段名,值留空)。
- **真账号字符串不入仓**:代码、注释、文档里出现的 MT5 账号(`1513619224`)、密码、服务器地址(FTMO-Demo / Pepperstone-Demo),全部替换成占位符 `YOUR_LOGIN` / `YOUR_PASSWORD` / `YOUR_SERVER`。
- **LLM 闸门第一版占位**:`core/llm_explainer.py` 第一版返回固定字符串(沿用御金启发式),但接口预留,接 LLM 时只改这个文件,不动其它。
- **MT5 终端状态不可破坏**:`mt5.shutdown()` 只在"买入单独 init"那个调用链上用,主进程的长连接行情扫描不调 shutdown。悟空的持仓依赖 MT5 GUI 在前台运行。

---

## 4. 流水线(严格顺序,前道不过不进后道)

```
MT5 终端(悟空机器后台跑)
   │
   ▼
mt5_bridge.copy_rates(symbol, M5|M15|H1|H4|D1)   ← 只读 init,5s 一轮
   │
   ▼
scanner.py  ── 预筛:流动性/点差/价格跳空/开盘异常
   │  ↓ 通过
strategy.py 6 道闸门
   │  ├ 闸门1 避雷  ── 点差/跳空/事件/周早盘异常
   │  ├ 闸门2 共振  ── M5/H1/H4 趋势同向(EMA20/50)
   │  ├ 闸门3 结构  ── H4 是否在 FVG 内 / 是否有 liquidity sweep
   │  ├ 闸门4 节奏  ── M5 是否有 displacement / BOS
   │  ├ 闸门5 上下文 ── DXY 反向 / 重大事件窗口(留接口)
   │  └ 闸门6 待决策 ── 通过前 5 关 → risk.py 算 LOT/SL/TP
   │
   ▼
api/routes_screen.py  ──  POST /api/run  →  前端
   │
   ▼
前端看板(renderRows / renderKpis / renderPositions)

用户点「一键买入」
   │
   ▼
api/routes_trade.py → risk.py 校验(并发/敞口/日亏)
   │
   ▼
mt5_bridge.order_send()  ← SHADOW: 写 trade_decisions.jsonl / LIVE: 真发单
   │
   ▼
positions.py  ──  持仓加入监控,5s 巡检,severity 计算,触发逃生即提示平仓
```

---

## 5. 6 道闸门(每道有默认值,可在 `core/strategy.py` 改)

| # | 闸门 | 字段 | 默认阈值 | 含义 |
|---|---|---|---|---|
| 1 | 避雷 | spread | XAUUSD > 50 跳 | 流动性异常 |
| 1 | 避雷 | gap | M5 跳空 > 0.5% | 价格跳空 |
| 1 | 避雷 | open_window | 周一前 30min 标记 | 周早盘异常 |
| 2 | 共振 | ema_align | M5/H1/H4 EMA20 > EMA50 同向 | 趋势对齐 |
| 2 | 共振 | dxy_check | XAUUSD 时 DXY 反向 ≥ 0.3% | 美元反向验证 |
| 3 | 结构 | fvg | H4 30 根内有 FVG | 公平价值缺口 |
| 3 | 结构 | sweep | H1 30 根内有 liquidity sweep | 流动性扫荡 |
| 4 | 节奏 | displacement | M5 单根实体 > ATR(M5)*1.5 | 位移 |
| 4 | 节奏 | bos | M5 BOS 突破前高/前低 | 突破结构 |
| 5 | 上下文 | event_window | 按类目配:外汇=NFP/ECB/Fed,指数=earnings,加密=FOMC/ETF 流入,商品=OPEC,股票=财报 | 消息面 |
| 6 | 待决策 | risk | RiskAmount=$50,SL=0.5% | 风控算 LOT |

> 阈值都是**起点**,铸峰先按默认值跑出基线,悟空+观澜用回测数据再调。
> 闸门5(事件窗口)第一版可以返回 True(无事件数据),留接口后续接财经日历 API。

---

## 6. 技术栈与目录结构

### 6.1 技术栈

| 层 | 选型 | 说明 |
|---|---|---|
| 后端 | Python 3.11+ | 御金/V4.5 体系沿用 |
| Web 框架 | FastAPI + uvicorn[standard] | 与原站对齐 |
| MT5 桥 | MetaTrader5(官方包) | Windows-only,Linux 无效 |
| 数据 | pandas + numpy | 多周期 K 线处理 |
| 配置 | python-dotenv | .env 读取 |
| 数据校验 | pydantic v2 | API 入参/出参 |
| 前端 | 单页 HTML(原生,无框架) | 与原站对齐;CSS 变量 + Vanilla JS |
| 字体 | Geist + Geist Mono | Vercel 开源,免费;比原站 Bricolage + Plex 更现代 |
| 部署 | 127.0.0.1:8000 | 不上公网 |

### 6.2 目录结构

```
F:\yujin-mt5\                        ← 项目根(待悟空拍,可能是其他位置)
├── app.py                          # FastAPI 入口,瘦,只路由
├── core/
│   ├── mt5_bridge.py               # MT5 Python SDK 封装
│   ├── scanner.py                  # 多周期扫描器(5s 一轮)
│   ├── strategy.py                 # 6 道闸门逻辑(按品种配置驱动)
│   ├── risk.py                     # 风控(SL/TP/日亏/连亏 kill · 按类目系数)
│   ├── positions.py                # 持仓监控(severity 评分)
│   └── llm_explainer.py            # LLM 解释器(v0.1 占位,延后)
├── api/
│   ├── routes_screen.py            # /api/run, /api/scan/settings
│   ├── routes_trade.py             # /api/buy, /api/sell, /api/unmonitor
│   └── routes_account.py           # /api/positions, /api/account, /api/mode
├── static/
│   └── index.html                  # 前端(自己重写,不复用原站代码)
├── docs/
│   └── index.html                  # GitHub Pages 副本(只读 DEMO 模式)
├── outputs/                        # 运行时数据(全部 .gitignore)
│   ├── trade_decisions.jsonl
│   ├── positions.json
│   └── scan_settings.json
├── .env.example                    # 凭据模板(留空值,真值在本地 .env)
├── .gitignore
├── requirements.txt
├── SPEC.md                         # 本文档
├── README.md
└── LICENSE                         # MIT
```

---

## 7. API 契约(铸峰照着写)

### 7.1 `GET /api/account`
```json
{
  "login": 0,
  "balance": 0.0,
  "equity": 0.0,
  "margin": 0.0,
  "free_margin": 0.0,
  "leverage": 0,
  "server": "YOUR_SERVER",
  "mode": "SHADOW",
  "trading_locked": false
}
```

### 7.2 `GET /api/positions`
```json
[
  {
    "ticket": 12345,
    "symbol": "XAUUSD",
    "type": "BUY",
    "lots": 0.5,
    "entry": 2345.6,
    "current": 2350.1,
    "pnl": 22.5,
    "pnl_pct": 0.96,
    "severity": 18,
    "sl": 2340.0,
    "tp": 2360.0,
    "open_time": "2026-06-17T08:30:00+08:00"
  }
]
```

### 7.3 `POST /api/run`  (扫描)
**入参**:
```json
{ "symbols": ["XAUUSD"] }
```
**出参**:
```json
{
  "scan_id": 1,
  "ts": "2026-06-17T08:30:00+08:00",
  "decisions": [
    {
      "symbol": "XAUUSD",
      "status": "action",
      "died": null,
      "verdict": { "v": "pass", "conv": 0.85, "thesis": "..." },
      "features": {
        "spread": 22, "gap_pct": 0.0,
        "ema_align": true, "dxy_align": true,
        "fvg": true, "sweep": false,
        "displacement": true, "bos": "bullish"
      },
      "priority": 78,
      "size_lots": 0.05,
      "sl": 2340.0, "tp": 2360.0,
      "exit_plan": "SL -0.5% · TP +0.6% / +1.2% · trailing 0.3%",
      "reason": "all 6 gates passed"
    }
  ],
  "kpis": {
    "scanned": 1, "passed_safety": 1, "passed_confluence": 1,
    "pending": 1, "positions": 0, "escape_alerts": 0
  },
  "positions": []
}
```

### 7.4 `POST /api/buy`
**入参**:
```json
{
  "symbol": "XAUUSD",
  "lots": 0.05,
  "sl": 2340.0,
  "tp": 2360.0,
  "thesis": "H4 BOS + M5 displacement, DXY 反向"
}
```
**出参**:
```json
{ "ok": true, "ticket": 12346, "mode": "SHADOW" }
```
> SHADOW:写 `trade_decisions.jsonl` + 加入监控列表,不真下单
> LIVE:调 `mt5.order_send` 真发,带 SL/TP

### 7.5 `POST /api/sell`
**入参**:
```json
{ "ticket": 12345, "reason": "escape" }
```
**出参**:
```json
{ "ok": true, "pnl": 22.5 }
```

### 7.6 `POST /api/mode`  (切 SHADOW/LIVE)
**入参**:
```json
{ "mode": "LIVE" }
```
**出参**:
```json
{ "ok": true, "mode": "LIVE", "trading_locked": false }
```

### 7.7 `GET /api/positions` 返回结构同 §7.2,定时(每 5s)前端轮询。

### 7.8 `GET /api/health`
**出参**:
```json
{ "ok": true, "mt5_connected": true, "ts": "..." }
```

---

## 8. 前端看板(配色 + 字体 + 粒子 + 组件)

### 8.1 配色方案: A 极光深空(主推,待悟空最终拍)

| 元素 | Token | Hex | 用途 |
|---|---|---|---|
| 背景 | `--ink` | `#020617` | 全局深空底 |
| 卡片1 | `--panel` | `#0a0f1f` | 卡片底色(主) |
| 卡片2 | `--panel-2` | `#0e1428` | 卡片底色(次) |
| 抬升 | `--raise` | `#131a30` | 抬升元素 |
| 边框 | `--line` | `#1e293b` | 卡片/分隔线 |
| 边框弱 | `--line-2` | `#1e293b80` | 半透明边框 |
| 文字主 | `--paper` | `#f1f5f9` | 主文字 |
| 文字次 | `--paper-2` | `#cbd5e1` | 次文字 |
| 文字弱 | `--dim` | `#64748b` | 标签/提示 |
| 文字极弱 | `--dim-2` | `#475569` | 极弱提示 |
| **主强调** | `--cyan` | `#22d3ee` | 通过/健康 |
| **次强调** | `--violet` | `#a78bfa` | 优先级/亮状态 |
| 警示 | `--amber` | `#fbbf24` | 留意/止损 |
| 危险 | `--crimson` | `#f43f5e` | 逃生/REJECT |
| 信息 | `--teal` | `#2dd4bf` | 信息提示 |

**对比原站**:原站是墨底+柠檬黄+橙红+琥珀,偏"meme 街机";A 方案是深空+极光青紫+琥珀+番茄,偏"机构交易台"。气质彻底换,但都是暗色调,改造阻力小。

**备选 B / C**:文档暂时锁定 A,悟空不喜欢可换 B(量子紫翡翠)或 C(终端钛银),在 SPEC §15 标注。

### 8.2 字体(也升级,跟原站告别)

| 用途 | 字体 | 备选 | 加载 |
|---|---|---|---|
| 标题 | Geist | Inter Display / Plus Jakarta Sans | Google Fonts |
| 数据 | Geist Mono | JetBrains Mono / Berkeley Mono | Google Fonts |

> 原站 Bricolage Grotesque + IBM Plex Mono 偏"插画风";Geist 系列偏"现代商业",跟 A 极光深空是一对。

### 8.3 粒子背景(替代原站静态颗粒)

- **形态**:极光渐变层,2-3 个 `radial-gradient` 叠加,主色 `--cyan` → `--violet`,8s 缓动呼吸
- **粒度**:`<div class="grain">` 用 SVG 噪点贴图(沿用原站实现,改透明度到 0.03)
- **性能**:CSS 变量驱动,不动 JS,Chrome/Firefox 60fps
- **设计意图**:3 秒内有视觉高潮(极光流动),1 秒内出主体(深空背景),结尾停在好看画面(深空+极光微动)

### 8.4 组件清单(沿用原站 8 个,内部配色/字体/动效全部换)

1. **顶栏** — Logo / 时钟 / MT5 状态 / 品种选择 / SOURCE 切换 / 齿轮 / 语言
2. **6 个 KPI 卡** — 累计扫描 / 过避雷门 / 过共振门 / 待决策 / 持仓 / 逃生预警(原站 7 个,合并掉 1 个)
3. **筛选流水线表** — 6 道闸门图标 + 字段(SAFE/SPREAD/GAP/CONFLUENCE/DXY/STRUCT/TIMING/EXIT/PRIORITY/DECISION)
4. **持仓逃生监控** — 卡片:severity 进度条、信号列表、立即平仓按钮
5. **闸门漏斗** — 6 道门各一条进度条 + 砍掉数
6. **风险迷你条** — 并发持仓 / 总敞口 / 当日亏损 / 连亏
7. **实时决策日志 feed** — 滚动显示 SCREEN / FILTER / BUY / SELL
8. **弹窗 × 4** — 凭据配置 / 筛选设置 / 一键买入 / 二次确认

### 8.5 动效清单(GSAP 精调)

- 顶栏 logo:呼吸光晕(2.6s loop)
- KPI 数值:刷新时 flash(0.6s)
- 表格行:扫描时顺序 ping(90ms 间隔,7 行)
- 持仓卡片:severity 进度条平滑过渡(0.8s cubic-bezier)
- 逃生信号触发:全卡红框闪烁(0.9s ease-out,只闪一次)
- 弹窗:scrim 淡入 + 卡片 0.2s 缩放
- 粒子呼吸:8s ease-in-out 循环

---

## 9. 风控与安全(不可破)

### 9.1 仓位与日亏
- **RiskAmount 基线** = $50 / 单(悟空拍的节奏:FTMO 一阶段日亏上限 $300 = 一天能亏 6 次)
- **按类目系数**(防加密/小盘股爆仓):
  - 外汇:×1.0 → $50/单
  - 指数:×1.0 → $50/单
  - 商品:×0.7 → $35/单
  - 加密:×0.5 → $25/单
  - 股票 CFD:×0.5 → $25/单
- **LOT 计算**:`lots = risk_amount × 类目系数 / (sl_pips × pip_value)`(品种配置里给 pip_value)
- **当日累计亏损** > $300 → 强制 SHADOW 模式,拒绝所有 LIVE 买入
- **连亏** ≥ 3 → kill-switch 触发,前端红色告警 + 锁住所有 LIVE 操作

### 9.1.1 跨品种相关性
- 同向高相关(>0.7)品种不能同时持仓:开 EURUSD 后 GBPUSD 同向不能再开(相关性 0.85)
- 配置在 `config/symbols.yaml` 的 `correlation` 字段

### 9.2 并发与敞口
- **最大并发持仓** = 3
- **总敞口** ≤ 账户净值 30%
- **单品种最大持仓** = 1 笔(同方向不重仓)

### 9.3 模式与锁定
- **SHADOW**(默认):不调 `mt5.order_send`,只写 `trade_decisions.jsonl`
- **LIVE**:`mt5.order_send` 真发单,带 SL/TP
- **trading_locked**:`core/risk.py` 顶部 `LIVE_TRADING_DISABLED = False`(可一键锁回 True,锁住后所有 LIVE 请求被拒)
- **重启后 mode 归零**:后端进程重启后 mode 自动回 SHADOW,需用户主动切 LIVE(防意外续跑)

### 9.4 凭据安全
- `.env` 权限 600,放项目根不入仓
- API 接收凭据只在初始化时,不写日志不持久化
- 凭据变更需要重启后端,前端不存凭据

---

## 10. 关键数据结构(实现参考)

### 10.1 扫描结果(单品种)
```python
@dataclass
class ScanDecision:
    symbol: str
    status: Literal["action", "reject", "filtered"]
    died: Optional[int]  # 1-6,阵亡于哪道闸门;None = 全过
    verdict: Verdict  # v: pass/watch/reject, conv: float
    features: Features  # spread, gap, ema_align, ...
    priority: int  # 0-99
    size_lots: float
    sl: float
    tp: List[float]  # 阶梯 TP
    exit_plan: str
    reason: str  # 中文,悟空偏好
    ts: datetime
```

### 10.2 持仓
```python
@dataclass
class Position:
    ticket: int
    symbol: str
    type: Literal["BUY", "SELL"]
    lots: float
    entry: float
    current: float
    sl: float
    tp: List[float]
    pnl: float
    pnl_pct: float
    severity: int  # 0-100
    signals: List[Signal]
    open_time: datetime
```

### 10.3 Severity 评分(0-100)
```python
def calc_severity(pos, m5_data, h1_data):
    score = 0
    # 浮亏
    if pos.pnl_pct < -0.3: score += 30
    elif pos.pnl_pct < -0.1: score += 15
    # SL 接近度
    sl_distance = abs(pos.current - pos.sl) / pos.current
    if sl_distance < 0.001: score += 25
    elif sl_distance < 0.003: score += 12
    # M5 反向
    if m5_data.ema20 < m5_data.ema50 and pos.type == "BUY": score += 20
    # 连亏计数(影响全账户)
    if consec_losses >= 1: score += 10
    return min(100, score)
```

---

## 11. 阶段拆解(铸峰按这个跑,每阶段有产出物+验收)

### 阶段 1 — 脚手架(2-3 天)
- [ ] F 盘建仓 `yujin-mt5/`(悟空拍位置)
- [ ] 写 `requirements.txt`:`fastapi`, `uvicorn[standard]`, `MetaTrader5`, `pandas`, `numpy`, `python-dotenv`, `pydantic`
- [ ] `app.py` 写 FastAPI 入口 + 静态文件托管
- [ ] `static/index.html` 自己重写(对齐原站交互但配色/字体/动效全换),先 DEMO 模式跑起来
- [ ] `.gitignore` + `.env.example` + `LICENSE`(MIT)+ `README.md`
- [ ] 本地起 `uvicorn app:app --reload`,浏览器开 `http://127.0.0.1:8000`,DEMO 模式完整跑通
- **验收**:DEMO 看板一屏展示,极光配色生效,Geist 字体加载,粒子背景动;23 品种配置已写入 `config/symbols.yaml`(占位默认值,铸峰开工后可调)

### 阶段 2 — MT5 桥(3-4 天)
- [ ] `core/mt5_bridge.py`:封装 `mt5.initialize(path=...)`(只读模式,不传凭据)+ `copy_rates` + `account_info`
- [ ] `api/routes_account.py`:`GET /api/account`、`GET /api/health`
- [ ] 凭据流:扫描用只读 init(共享一个连接池)→ 买入触发"下单专用 init"(`init(login=, password=, server=)`)→ 下完 `mt5.shutdown()`
- [ ] 坑(悟空踩过):周末 `tick.last=0` → 取 `(bid+ask)/2`;FTMO 日界=北京 8 点(UTC 0 点),不是 broker 假 0 点
- **验收**:前端能展示 XAUUSD 实时账户信息(余额/净值/杠杆/服务器),不动 MT5 GUI 里的持仓

### 阶段 3 — 扫描器 + 6 道闸门(5-7 天)
- [ ] `core/scanner.py`:每 5s 拉一次 XAUUSD 多周期 K 线(M5/M15/H1/H4/D1),缓存到内存
- [ ] `core/strategy.py`:6 道闸门按 §5 实现,品种配置在 `config/symbols.yaml` 里驱动(预留 6 品种)
- [ ] `core/risk.py`:`RiskAmount=$50`,LOT 计算,SL/TP 计算
- [ ] `api/routes_screen.py`:`POST /api/run` + `GET/POST /api/scan/settings`
- **验收**:`POST /api/run` 返回 23 品种当前真实扫描结果,前端表格能渲染 5 大类目(外汇/指数/商品/加密/股票)

### 阶段 4 — 一键买入/平仓(2-3 天)
- [ ] `api/routes_trade.py`:`POST /api/buy` `POST /api/sell` `POST /api/unmonitor`
- [ ] `core/positions.py`:持仓持久化到 `outputs/positions.json`
- [ ] SHADOW 模式:写 `trade_decisions.jsonl`,加入监控列表
- [ ] LIVE 模式:`mt5.order_send` 真发,带 SL/TP 挂单
- **验收**:SHADOW 模式:模拟账户"买"出持仓,看得到 severity 渐变;LIVE 模式:FTMO 模拟账户(`YOUR_LOGIN` placeholder)真下一单,SL/TP 全挂

### 阶段 5 — 持仓监控 + 逃生(3 天)
- [ ] `core/positions.py` 每 5s 巡检所有持仓
- [ ] severity 评分(§10.3 算法)
- [ ] severity ≥ 70 触发逃生:前端持仓卡片红框闪烁 + 日志写 ALERT
- [ ] 立即平仓按钮(对应当前 ticket)
- **验收**:SHADOW 模式能看到持仓 severity 渐变(脚本可模拟),触发逃生时高亮+红框闪烁+日志告警

### 阶段 6 — DEMO 模式 + GitHub Pages(1-2 天)
- [ ] 后端连不上时前端自动进 DEMO(沿用 `body.publicro` 思路)
- [ ] `docs/index.html` 同步脚本(沿用原 `scripts/git-hooks`)
- [ ] GitHub Actions:推 `main` 自动部署 Pages
- [ ] 公开演示页只读,不能下单(用 `publicRO` CSS 类隐藏买入按钮)
- **验收**:断网或停后端,前端能进 DEMO 模式跑极光配色假数据;GitHub Pages 公开 demo URL 跑通

### 阶段 7 — 扩展到 60+ 满配(主流程已含 23 核心,此阶段加 Exotic + Minor + 更多股票 CFD)
- [ ] `config/symbols.yaml` 加 37+ 扩展品种(Exotic 外汇 + Minor 交叉 + 10+ 股票 CFD + 5+ 加密)
- [ ] `core/scanner.py` 并行扫扩展品种(用 `asyncio` 或线程池)
- [ ] DXY 反向闸门扩展(US500 时考虑 TNX,NAS100 考虑 NDX 等)
- **验收**:60+ 品种同时跑,前端 KPI 显示多类目聚合

### 阶段 8 — LLM 解释(延后,可选 · 悟空 2026-06-17 拍 v0.1 不接)
- [ ] `core/llm_explainer.py` 接 LLM API(0g.ai / OpenAI 兼容)
- [ ] 注入消毒(symbol_safe 替换)+ 结构化 prompt(只喂数值)
- [ ] 闸门 5-6 之间加 LLM 闸门
- **验收**:幸存者有 LLM 生成的 pass/watch/reject 解释 + 置信度

---

## 12. 验收标准(铸峰交付 = 悟空过目 = 观澜上线验收)

- [ ] 阶段 1-6 全部跑通,DEMO + SHADOW + LIVE 三模式全部可切
- [ ] FTMO 模拟账户(`YOUR_LOGIN` 占位)能真下一单 SL/TP 全挂
- [ ] 持仓 severity 渐变可见,逃生信号触发正确
- [ ] GitHub Pages 公开 demo 跑通(极光配色生效)
- [ ] `.env` / 真账号字符串 / `outputs/` 全部 `.gitignore`
- [ ] 全部代码中文注释
- [ ] 提交后 1 周内无 P0/P1 bug

---

## 13. 脱敏清单 + .gitignore 模板

### 13.1 必脱敏字符串(代码/注释/文档/日志)
- MT5 账号:真实值 → `YOUR_LOGIN`
- MT5 密码:真实值 → `YOUR_PASSWORD`
- MT5 服务器:真实值 → `YOUR_SERVER`
- MT5 终端路径:真实值 → `YOUR_MT5_PATH`(e.g. `F:\MT5\terminal64.exe`)
- 任何包含真实账号数字的注释:`# 1513619224` → `# YOUR_LOGIN`

### 13.2 `.gitignore` 模板
```gitignore
# 凭据
.env
*.env.local

# 运行时数据
outputs/*.json
outputs/*.jsonl

# MT5 文件
*.set
*.ex5

# 系统
__pycache__/
*.pyc
.venv/
venv/

# IDE
.vscode/
.idea/
*.swp
.DS_Store

# 测试临时
test_outputs/
*.log
```

### 13.3 `.env.example` 模板
```bash
# MT5 凭据(运行时填,不进仓库)
MT5_LOGIN=YOUR_LOGIN
MT5_PASSWORD=YOUR_PASSWORD
MT5_SERVER=YOUR_SERVER
MT5_PATH=YOUR_MT5_PATH

# 应用
APP_HOST=127.0.0.1
APP_PORT=8000
LIVE_TRADING_DISABLED=false
RISK_AMOUNT_USD=50
MAX_CONCURRENT_POSITIONS=3
DAILY_LOSS_CAP_USD=300
```

---

## 14. 编码约定

- **语言**:中文注释,英文代码标识符
- **风格**:PEP 8,Black 格式化
- **类型**:全部函数加 type hint,`pydantic` 校验 API 入参/出参
- **日志**:`logging` 模块,INFO 级别写文件,DEBUG 级别只在控制台
- **错误**:API 用 `HTTPException(status_code, detail="中文错误信息")`
- **测试**:阶段 3 开始每个核心函数加单元测试(`pytest`),覆盖率 ≥ 60%
- **Git**:commit message 中文,格式 `类型(范围): 说明`(`feat(strategy): 加 EMA 共振闸门`)
- **分支**:`main` 稳定,`feat/*` 开发,`fix/*` 修复

---

## 15. 决策清单(已全部锁默认 · 2026-06-17)

| # | 项 | 默认 | 备选 |
|---|---|---|---|
| 1 | 项目目录 | `F:\yujin-mt5\` ✅ | `F:\guanlan-mt5\` / `F:\projects\yujin-mt5\` |
| 2 | 品牌 | YUJIN AI TRADER ✅ | — |
| 3 | 协议 | MIT ✅ | Apache-2.0 |
| 4 | 配色 | A 极光深空 ✅ | B 量子紫翡翠 / C 终端钛银 |
| 5 | 字体 | Geist + Geist Mono ✅ | Inter Display / JetBrains Mono |
| 6 | 粒子背景 | 极光呼吸 8s 循环 ✅ | 静态 / 无 |
| 7 | 范围 | 23 个核心品种(5 大类目)✅ | 15 精简 / 60+ 满配 |
| 8 | LLM 闸门 | **第一版占位** ✅(悟空 2026-06-17 拍) | 第一版就接 |
| 9 | DEMO 模式 | 保留 ✅ | 不要 |
| 10 | 凭据流 | "下单专用 init"独立链路 ✅ | 主进程共享 |

> 全部默认项已于 2026-06-17 由悟空拍板,后续修改请直接 patch 此表。

---

## 16. 给铸峰的回信(开工前回这 3 个)

1. **MT5 SDK 熟不熟**?`MetaTrader5` 官方包用过没?需要先做 `pip install` 测试吗?
2. **WebSocket vs 轮询**?原站是 fetch 轮询(5-6s),工作量最小;要不要换 WebSocket 推流(代码量大)
3. **FastAPI vs Flask**?我默认 FastAPI(对齐原站),你熟的话直接用;不熟换 Flask 也可以

---

**完。** 这版是 v0.1 开工基线,后续悟空改字段/加规则直接在这版上 patch,每次 patch 留 git commit。
