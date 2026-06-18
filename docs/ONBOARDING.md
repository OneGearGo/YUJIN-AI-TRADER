# YUJIN AI TRADER · 铸峰接续指令(2026-06-17 起)

## 一句话
F:\yujin-mt5\ 是 YUJIN AI TRADER:借 GMGN AI Trader 看板形态,跑 MT5 品种(14 品种 / 5 类目 / 6 闸门 / 风险系统),FastAPI + 前端单 HTML,公开 MIT。
**跟 V4.5(御金量化PRO)物理隔离 — 严禁 import / 参考 / 复用代码**。

## 路径
- 项目根:`F:\yujin-mt5\`
- 仓库:`OneGearGo/YUJIN-AI-TRADER` · 公开 MIT
- 部署:https://onegeargo.github.io/YUJIN-AI-TRADER/
- 本地:http://127.0.0.1:8000/

## 怎么读(按顺序)
1. `SPEC.md` 16 章决策锁死 — **第一遍先看,所有改动对齐这里**
2. `WORKFLOW.md` — 协作者施工单
3. `docs/WORKLOG-2026-06-17.md` — 今日进度 + 未完成 + 教训
4. `config/symbols.yaml` — 14 品种 + 类目系数
5. `app.py` + `core/` + `api/` — 后端入口

## 当前状态(数字)
- 4 commit push 成功:`b2e450d` / `d03879b` / `83d1bd7` / `c26fc65`
- 公开 URL · 57538 bytes · 本地 8ms 200 OK
- 14 品种(forex 5 / index 4 / crypto 3 / stock 2 / **commodity 0 缺**)
- 7 KPI / 3 持仓 / 10 日志 / 6 闸门漏斗
- SHADOW demo 模式(`.env` 未填 MT5 凭据)

## 铁律(不能碰)
1. **V4.5 不动** — 御金量化PRO 悟空亲用,跟本项目物理隔离
2. **MT5 终端不动** — 有持仓时终端断开=止损全失效,悟空自己管
3. **V4.5 策略不外** — 平台用均线,别漏 Al Brooks / SMC / 结构位
4. **凭据不入对话** — `.env` 真凭据,真值不入 commit / 对话 / token
5. **不动桌面文件** — `C:\Users\Administrator\Desktop\`,已误删 15 个
6. **删/覆盖/移动前必问** — 列文件 + 等悟空确认
7. **凭据泄露** — 立即提醒悟空撤 + 改 remote URL

## 阶段路线
| 版本 | 状态 | 内容 |
|---|---|---|
| v0.1 | ✅ 已 | 脚手架 + UI + 6 闸门 + 风险 + SHADOW demo |
| v0.2 | → 下一步 | MT5 真接 + LLM 闸门 v0.1→v0.2 + 补 commodity |
| v0.3 | 待拍 | V4.5 集成 / 实盘切换 |
| v0.4 | 待拍 | 公众号 / 监控 / 自动备份 |

## 接下去做(按优先级)
1. **修 vision 通道** — 浏览器 UTF-8 错误,需重启 Hermes session
2. **持仓 card 接 openPanel** — 持仓详情第二层(本日留尾巴)
3. **表格行接 openPanel** — 品种详情第二层(本日留尾巴)
4. **补 commodity 类目** — XTIUSD / XAGUSD / XCUUSD
5. **MT5 真接** — 走 `core/mt5_bridge.py` + `.env` 凭据

## 怎么跑
```bash
cd /f/yujin-mt5
uvicorn app:app --reload          # 本地服务:http://127.0.0.1:8000/
```

## 怎么推
fine-grained PAT 模式(URL inline 不支持,需走 credential helper):
```bash
git add <files>
git commit -m "<type>(<scope>): <desc>"
git -c credential.helper='!f() { echo "username=OneGearGo"; echo "password=ghp_你的token"; }; f' push origin main
```

## 找谁
- **悟空**:决策 + 审阅。V4.5 / 上实盘 / 新策略 / 重大变更找他。
- **观澜(我)**:验收 + 回测 + 分析。动代码 / 动文件 / 重大判断前先说。

## 收工
每天在 `docs/WORKLOG-YYYY-MM-DD.md` 写工作日记(参 2026-06-17 那篇模板):
- 今日 commit 链 + 字节数
- 关键改动(分块 + 数字)
- 部署状态(URL / 字节 / Actions)
- 未完成 / 下次接续
- 风险 / 教训
- 明日待办

## 风险提醒
- **EMJI 中文**:UI 文案中文,代码注释中文
- **不照搬 GMGN 站点具体内容**:形态 / 语言可借鉴,代码 / 文案 / 配色不照搬(防 IP 风险)
- **6 道闸门不复用 V4.5**:V4.5 是 Al Brooks + M15,平台是均线 + 6 闸门,完全独立
- **每次 patch 后必查**:`grep -c "</script>" static/index.html`(本次出过 1 次事故,误插 `</script>` 把后面函数踢出 script 块)
- **每天 commit / push 不囤**:本次因为"先不要急"囤了 4 块改动,差点丢
