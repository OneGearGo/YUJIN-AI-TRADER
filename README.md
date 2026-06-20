# YUJIN AI TRADER

> AI Trader 看板，内核是 MT5 行情 + 御金交易策略。

## 简介

本地 Web 应用：FastAPI 后端 + 单页 HTML 前端，后端同源托管前端。

- **用户**：自用 + 信任的少数人，各自本机跑、配自己的 MT5 账户
- **支持账户**：FTMO 考核 / FTMO 实盘 / 模拟账户
- **模式切换**：SHADOW（只记录）/ LIVE（真发单）

## 快速开始

```bash
# 1. 创建虚拟环境
python -m venv .venv
.venv\Scripts\activate

# 2. 安装依赖
pip install -r requirements.txt

# 3. 配置凭据
copy .env.example .env
# 编辑 .env 填入 MT5 凭据

# 4. 启动
uvicorn app:app --reload
# 浏览器打开 http://127.0.0.1:8000
```

## 流水线

```
MT5 终端 → mt5_bridge → scanner → strategy (6道闸门) → risk → 前端看板
                                    用户点「一键买入」→ risk校验 → mt5_bridge.order_send → positions监控
```

## 配色

A 极光深空：深空底 + 极光青紫 + 琥珀 + 番茄，偏"机构交易台"气质。

## 风险声明

纯交易工具，盈亏自负；不构成投资建议。

## License

MIT

---

## Round History (UI/UX polish waves)

The UI has been reshaped in numbered "rounds" since the 1:1 mirror of gmgnai's AI Trader reference. Each round is automatically reproducible: see `_patches/` for the byte-exact patcher scripts (`_r##_*.py` + `_r##_ship.sh`) that produced the commit. Most recent first.

| Round | Commit | Subject |
| --- | --- | --- |
| r29 | `e8063f3` | **anti-cache meta + APP_VERSION v0.0.1 → v0.0.2 + title `AI Trader · r29` suffix** — three `<meta http-equiv>` no-store tags plus a `<meta name="yujin-build" content="r29">` cursor meta so future rounds only need a one-literal overwrite. Browser-tab version skew + no cache after this point. |
| r28 | `3448c1c` | **CHAIN SOL → FOREX (刀头全部换掉)** — every visible SOL/CHAIN/GMGN CLI label swapped to MT5 forex (lots, FOREX, MT5-CLI, `~/.config/yujin-mt5/.env`). 23 anchors × 2 files (static + docs). Round-28 closed the chain→forex rebrand. |
| r27 | `abd4025` | **cipher-jargon rewrite of 6 zh + 6 en LIVE decision-log templates** — `detail_passed`, `log_screen_reason`, `kpi_sub_expo`, `toast_buy`, `toast_buy_demo`, `buy_log_reason`. Cipher-tags `[Audit:0xa01/a02]`, `[Expo:0xb03]`, `[Wire:0xd04/d05]`, `[Monitor:0xe06]`, `[Unit:0xa11]`. |
| r26 | `21c36d6` | **feat(theme): rewrite SOL/crypto → MT5 forex+indices; cipher-jargon the decision log** — `sig_*`, `bk_rank`, `inj_tip`, `gatetip3`, `pipe_reset`. Round-26 only cipher-tags static I18N entries; Round-27 expanded it to LIVE runtime logs. |
| r23 | `714b106` | **`.tag` content locked to 5-step handoff prose** — `你按下成交 ➡️ 人机协同 / 一锤定音 / 闭环收口 / 最终授权 / 拍板转化`. Tag rendering dropped the `APP_VERSION` prefix; visible skew now lives in browser title. |
| r19 | `a97a8c2` | **demobar restored `<b>` bold wrappers + lime link style** — after Round-18's full-phrase overwrite, Round-19 rebuilt the visual emphasis the reference used. |
| r18 | *local* | **fp phrase replace** — first ad-hoc round; replace legacy deterministic-rule/ML-cut/LLM-explain phrase with placeholder for Round-19 reuse. |
| r17 | *local* | **restyle** — button text/iconography polish before r18 phrase edits. |
| r15 | *local* | **demobar lime-link replace** — point `查看源代码 ↗` at OneGearGo/YUJIN-AI-TRADER. |
| r11 | *local* | **demobar v3** — final demobar copy after user feedback. |
| r10 | *local* | **demobar v2 + restore backup** — middle iter of demobar during Polish #5.3. |
| r8  | *local* | **8-patch precursor** — Round-18…23-style polish precursor before demobar dispute settled. |

### Why rounds instead of semver?

Semver has no overhang for "visible-content/identity polish waves" inside a zero-day public demo. The repo keeps `APP_VERSION` as `v0.0.x` for the runtime; the **rounds count** is the public-facing iteration clock until the broker adapter and a real user's account block lands. The Round-29 fix moved visible version signal out of the `.tag` and into the browser-tab `<title>`, freeing `APP_VERSION` to mean "software schema" rather than "document revision".

### Older reset anchors (pre-r8)

| Commit | Subject |
| --- | --- |
| `b53861a` | Update README.md |
| `09cc3bc` | fix(demobar): 自配经销商或自营上账户信息 → 自配经销商和自营商账户信息 |
| `70c10f1` | feat(demobar): user-specified text + link to OneGearGo/YUJIN-AI-TRADER |
| `6a54680` | feat: 1:1 mirror gmgnai.github.io/skillmarket-demos/aitrader |
| `66f7417` | fix(demobar): restore user-specified disclaimer text |
| `3e07cc2` | chore(hygiene): gitignore runs + remove stale `*.bak` files |
| `d6822da` | chore(rebrand): YUJIN AI TRADER v0.0.1 + CN/EN demobar rewrite |
| `021a2db` | feat(mt5): thin-proxy 17-symbol FX adapter |

Polish-trail commits (no per-round patcher script, only `HANDOFF.md`): `a1549d5 chore(infra): Polish #8.1` · `a08b307 ci: Polish #8.4.1` · `0480168 build(deps): Polish #8.5` · `d3a91df docs(trail)` · `16b1fbf docs(trail)` · `5ab3bd5 chore(trail)` · `56146f3 chore(trail)` · `89a7309 chore(trail)` · `fb80a93 ci(workflow): Polish #8.10` · `e7685ce fix(docs,static): lock dashboard to single viewport`.

