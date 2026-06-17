# YUJIN AI TRADER · 铸峰施工单(精简版)

> 完整规格见 [SPEC.md](SPEC.md)。本文件只讲**铸峰一上手要做的 3 件事**。

---

## 1. 开工前必读(15 分钟)

**先读 SPEC 这 3 个章节,顺序不能乱**:

1. **§3 铁律** — 5 条红线,违反任意一条打回(V4.5 不碰 / C 盘禁存 / MT5 用 `path=` 只读 / 多品种按配置驱动 / JSONL 日志)
2. **§11 阶段拆解** — 8 个阶段,每阶段有产出物 + 验收点,**你从阶段 1 开始**
3. **§15 决策清单** — 10 项已锁默认,不动直接干,改要同步悟空

---

## 2. 阶段 1 任务清单(2-3 天,你的第一站)

**目标**:DEMO 模式完整跑通(极光配色 + Geist 字体 + 粒子背景 + 23 品种假数据)。

- [ ] `app.py` 写 FastAPI 入口(瘦,只路由)+ 静态文件托管
- [ ] `requirements.txt` 已就位,跑 `pip install -r requirements.txt`
- [ ] `static/index.html` **自己重写**,对齐原站交互但配色/字体/动效全换
  - 极光深空配色:`SPEC §8.1`(13 个 CSS 变量 hex 值)
  - Geist + Geist Mono 字体:`SPEC §8.2`
  - 极光呼吸粒子背景 8s 循环:`SPEC §8.3`
- [ ] `.gitignore` + `.env.example` + `LICENSE` + `README.md` 已就位(检查一遍)
- [ ] `config/symbols.yaml` 写 23 品种配置:
  - 7 forex major(EURUSD/GBPUSD/USDJPY/USDCHF/AUDUSD/NZDUSD/USDCAD)
  - 3 forex cross(EURJPY/GBPJPY/AUDJPY)
  - 4 index(US500/NAS100/UK100/GER40)
  - 3 commodity(XAUUSD/XAGUSD/USOIL)
  - 3 crypto(BTCUSD/ETHUSD/LTCUSD)
  - 3 stock(AAPL/TSLA/NVDA)
  - 每品种:`category / pip_value / spread_max / dxy_corr / trading_hours`
- [ ] 本地起 `uvicorn app:app --reload`,浏览器开 `http://127.0.0.1:8000`
- [ ] DEMO 模式完整跑通(不用 MT5,前端能展示 23 品种假数据)

**验收**:DEMO 看板一屏展示,极光配色生效,Geist 字体加载,粒子背景动;23 品种配置已写入 `config/symbols.yaml`。

---

## 3. 推代码流程

1. **clone 仓**:`git clone https://github.com/OneGearGo/YUJIN-AI-TRADER.git F:\yujin-mt5`(悟空本机已经 clone 过,直接用)
2. **身份已配**:悟空机器已配 `OneGearGo / OneGearGo@users.noreply.github.com`
3. **认证**:悟空会给你一个 **GitHub PAT**(90 天有效,勾 `repo` 权限)
   - 第一次 push 时 git 会问用户名/密码
   - 用户名:`OneGearGo`
   - 密码:**贴那个 PAT token**(不是悟空的 GitHub 密码)
4. **commit 规范**:`类型(范围): 说明`,中文 message
   - 例:`feat(scanner): 加 23 品种多周期 K 线拉取`
5. **推完通知悟空**,悟空过目后交观澜验收

---

## 4. 必看的 3 个参考文件

在 `docs/reference/`,**只读参考,代码全部自己重写**:

- `pre-commit.sample` — static/ → docs/ 同步钩子模板(阶段 6 用)
- `requirements.txt.original` — 原版依赖(对比)
- `spec-sections-9-11.md` — 原版数据结构 / 前端 / 状态(参考字段命名)

---

## 5. 不要做这些

- ❌ 不引用 V4.5 / 御金Pro 的任何代码 / SET / 参数
- ❌ 不把 `outputs/` 提交到 git(已经在 `.gitignore`)
- ❌ 不把 `.env` 提交(已经在 `.gitignore`,真账号字符串全部 `YOUR_LOGIN` 替换)
- ❌ 不 hardcode XAUUSD 单品种(配置驱动,23 品种都要能跑)
- ❌ 不接 LLM(v0.1 占位,接口预留,改 `core/llm_explainer.py` 就行)
- ❌ 不碰 C 盘任何位置

---

## 6. 阶段 1 完成后

通知悟空 + 推 commit。悟空会叫你开阶段 2(MT5 桥)。

---

**完。开干。**
