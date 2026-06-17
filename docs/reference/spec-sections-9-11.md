## 9. 前端看板

布局：演示横幅(仅DEMO) → 顶部状态条 → 7 KPI → 主区左(筛选结果表 + 实时日志) 右(持仓逃生监控 + 闸门漏斗 + 风控迷你条)。整体已为笔记本屏幕**紧凑化**(行/标题 padding 收紧)。

筛选结果表列：TOKEN(可点复制 Ticker + 雷达图标=该币已持仓) / 规则→排序→LLM(闸门图标) / 安全(蜜罐·放权徽章) / BUND / DEV / T10 / 聪明钱/KOL(degen/kol) / 时机(早期·横盘·过热·阴跌) / LLM(pass/watch/reject) / 优先级 / 决策。
- **TOKEN 列**：Ticker 下方显示 CA(前5…后4，点击新窗口开 GMGN 代币页) + 代币年龄(d/h/m/s，<1h 标绿)；点 Ticker 复制到剪贴板。
- **行点击**：展开下方解读详情，再点收起；默认不展开(省空间)。
- **「只看持仓」过滤**：TOKEN 旁 siren 图标开关，只显示已持仓的币。
- **即时 tooltip**：闸门图标 / LLM / 决策阵亡标签 / 时机 / 聪明钱列 hover 立即弹自画浮层(非原生 title)；委托挂在 document。
- **买入数量**：标题栏全局输入框，单位随链(SOL/BNB/ETH)，数值按链存 localStorage；改值下面所有买入按钮同步。
- **CHAIN 下拉**(右上)：SOL/BSC/Base/ETH 切换。**链是每个 tab 独立的**：本 tab 存 `sessionStorage`(多 tab 各看各链互不干扰)，`localStorage` 仅作新 tab 默认链种子。切链只改本 tab + 重扫(链随请求传)，不通知后端。
- **MODE 图标**(右上，原在配置齿轮内)：点击切换 实盘/模拟盘，调 `POST /api/mode` 改后端 `ST.mode`。→LIVE 弹二次确认(动真钱)、→SHADOW 直接切；硬锁时不让切 LIVE。每轮 `/api/run` 回传 mode，前端 `syncBackendMode` 保持图标与后端一致（重启后端回 SHADOW 会自动翻回 + 警示）。
- **后台 tab 暂停轮询**：`document.hidden` 时 `scanCycle` 跳过(不烧配额)，tab 重新可见立即补一轮(`visibilitychange`)。

关键交互：
- **一键买入 / 平仓 / 取消监控 / 切 LIVE**：全部用**自定义居中确认弹窗**(`confirmDialog`，已无任何浏览器原生 confirm/alert)。
- **持仓逃生监控**：每个持仓显示 现价·建仓价 + PnL% + severity 进度条 + 信号 + 平仓 + ×取消监控；severity≥70 变红脉动；**该币在左侧筛选非全绿/掉榜 → 卡片闪一下弱红并保持**(escAlertSet，恢复全绿则消失)。标题显示 `N/上限 持仓`。
- **数据源**：DEMO(示例数据自跑) / 本地后端(轮询 `/api/run`)；`scanCycle` 有防重入(避免堆积)，请求返回前若已切走则丢弃结果。
- **刷新**：筛选区先骨架 loading，不假写代币；连不上后端→自动 DEMO。
- 安全：key 只发 127.0.0.1、不写 localStorage；链/买入数量等无敏感项才入 localStorage。

---

## 10. 风控与安全约束（不可破）

- 组合级硬风控：最大并发持仓、总敞口上限、当日亏损上限、连亏 kill-switch。筛选时只提示（`risk_warn`），成交时硬拦。
- 仓位 = 固定分数法（冒险额 / 止损距离），由代码算，LLM 永不出数字。
- 退出预案：硬止损 + TP 阶梯 + 移动止损，成交后挂策略单。
- 后端只绑 `127.0.0.1`，**禁止** `0.0.0.0` 或暴露公网。需对外只能走外层隧道（见 §7 `PUBLIC_DEMO`：绑定不变，靠隧道转发；且该模式下后端纯只读、写接口全 403、持仓不外泄）。
- key 写本机 `.env`（chmod 600），不入项目、不入浏览器存储；每个使用者用自己的 key（GMGN key 绑申请时 IP 白名单，不可共用）。

关键参数集中在 `app.py` 的 `CFG`。本会话相关：
- `top_n_prefilter=100`、`llm_max=20`（启发式占位不花钱，放大减少 gate3 误杀；接真实 LLM 再收紧）。
- 避雷：`require_renounced_mint`、`max_buy_tax/max_sell_tax=0.10`、`max_rug_ratio=0.60`、`max_bundler_ratio=0.30`、`max_dev_holding_pct=0.10`、`max_top10_concentration=0.40`。
- 共识：`min_smart_money_confluence=1`（=smart_degen+renowned）。
- 排序：`rank_weights={mom5m:30,mom1h:12,buy_pressure:18,turnover:12,consensus:12,safety:10}`；阴跌沉底 `momentum_reject_chg1h=-0.12/chg5m=-0.06`；金狗/接盘 `buy_ratio_pass=0.50/buy_ratio_reject=0.42`。
- 风控：`max_concurrent_positions=20`（**感受阶段放宽**，真实上线前应调回 2~3）、`max_total_exposure_sol=1.0`、`daily_loss_cap_sol=0.5`、`kill_switch_consec_losses=3`。
- 安全护栏：`LIVE_TRADING_DISABLED`（app.py 顶部）。**当前为 `False`（已解锁真实交易）**：LIVE 模式 + 已配 `GMGN_PRIVATE_KEY` 时，「一键买入/平仓」会经签名密钥**真实发单、动用资金、不可逆**。仍是人在环（只有点按钮才成交），SHADOW 仍是默认安全态、需手动切 LIVE 才真发。置回 `True` 即可一键封死所有链上写。
  - **真实下单前置**：`~/.config/gmgn/.env` 的 `GMGN_PRIVATE_KEY` 必须非空（签名密钥），否则 `gmgn-cli swap/order` 报错；前端会显示「链上买入失败：…」清晰原因，不建仓。
  - **多链已对齐**（gmgn-cli 1.3.9 权威 Chain Currencies 表）：原生币 SOL=`So111…112`(9 位)、BSC/Base/ETH=`0x0000…0000`(18 位)；`--from` 按链用 `portfolio info` 自动解析。**EVM 各链尚未用真金白银实测**（私钥配好后建议先小额逐链验证）。

---

## 11. 当前状态

**已完成（可运行）**
- `app.py`：完整 FastAPI 后端，含重排后的流水线、硬门槛、评分、LLM 占位、持仓逃生监控、风控、四个 API、静态托管、Mock 适配器。默认 Mock+SHADOW 不填 key 即可跑。
- `static/index.html`：完整前端看板，已对接全部接口，DEMO 模式可独立演示。
- 脚手架：requirements / README / 目录结构。

**本会话已完成（真实数据 · 只读行情 · 买入做假 · 动能策略 · 多链 · 可演示托管）**
- gmgn-cli 1.3.9 适配 + `build_from_row`（零额外 cli）+ 真实字段判据（见 §6）。
- **排序改趋势动能模型** + **LLMJudge 金狗/接盘逻辑**（见 §4）：暴涨不一刀切，买占比区分跟/砍。
- **持仓真实价格涨跌**（entry_price/cur_price/pnl）+ **落盘持久化**（positions.json，reload/重启不丢）+ **按链隔离** + **取消监控**(/api/unmonitor)。
- **逃生监控修误报**：删 burn_ratio 信号（不可逆+跨源口径），只留 honeypot/renounced_mint/top10。
- **多链切换**（SOL/BSC/Base/ETH）：**链改为请求维度**（无全局当前链）——按链缓存 adapter + 按链 trending 短缓存(3s，同链多 tab 共享一次 cli)；前端每 tab 用 sessionStorage 各自持链，N tab 各看各链互不干扰；后台 tab 暂停轮询省配额。按链记忆命令(ST.trending_cmds)、买入单位/数量按链。
- **启动自动连真实数据**（env key → use_live → /api/status → 前端 autoConnect），api_key 可留空。
- **热榜命令按链默认 + 齿轮可配**（/api/settings；sol 默认=pump platform 命令）。
- **性能**：scanCycle 防重入 + 监控复用 trending 行 → `/api/run` 33s→~1s。
- **安全护栏 LIVE_TRADING_DISABLED**（见 §10）。
- **GitHub Pages 演示**：static 自适应 DEMO + 演示横幅 + docs/ + pre-commit 同步（见 §7）。
- 前端：见 §9（CA可点/年龄/即时tooltip/只看持仓/雷达/弱红联动/自定义确认弹窗/骨架loading/紧凑化等）。

**占位 / 待接入**
- `LLMJudge.judge`：动能启发式占位 → 换真实 Claude/GPT（喂 `symbol_safe`+数值，绝不喂原始名；JSON 严格解析）。当前 llm_max=20。
- `priority_score`：确定性动能加权 → 可换轻量 ML 排序（介入点 1），训练数据=回填盈亏后的 `trade_decisions.jsonl`。
- 反馈飞轮（介入点 4）：`trade_decisions.jsonl` 已 append SCREEN/FILTER/BUY/SELL/UNMONITOR，**当前只写不读**；需回填实际盈亏 → 调 `CFG` 阈值。
- 自适应阈值：`CFG` 写死，未按市场温度自动收紧/放宽、未做激进/保守档。
- 去重聚合（介入点 2）：未实现。
- 逃生"流动性撤离"信号：删了不可靠的 burn_ratio，**真正的撤池应看 `liquidity` 下降**（需 entry 记 liquidity + 同源，未做）。
- 风控/状态：持仓已落盘；但 `RiskManager`（连亏/日亏/kill-switch）仍内存、不落盘，reload 即清。
- LIVE 真实下单：**已落地**（解锁 + 钱包自动解析 + 按链精度/原生币 + 卖出改 `--percent 100`，见 §10）。遗留：① EVM 各链未用真金白银实测（待私钥配好后小额逐链验证）；② `order get` 仅轮询一次，未做超时重试循环；③ `max_concurrent_positions` 仍为放宽的 20，真实上线前应调回 2~3。

---

## 12. 关键数据结构（实现参考）
