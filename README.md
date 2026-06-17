# YUJIN AI TRADER

> 借 GMGN AI Trader 看板形态,内核是 MT5 + 自家策略的本地交易工具。
> **机器筛,人按成交。**

**形态**:本地 Web 应用(FastAPI 后端 + 单页 HTML 前端)
**支持账户**:FTMO 考核 / FTMO 实盘 / 模拟账户
**运行模式**:DEMO(假数据)/ SHADOW(只记录)/ LIVE(真下单)
**协议**:MIT
**第一版范围**:XAUUSD 单品种跑通,后扩 6 品种

---

## 特性

- 🎨 **极光深空配色** — 全新视觉系统,跟原站告别
- 🛡️ **6 道闸门筛选** — 避雷 / 共振 / 结构 / 节奏 / 上下文 / 待决策(详见 [SPEC §5](SPEC.md))
- 💰 **三模式账户** — FTMO 考核 / 实盘 / 模拟,右上角一键切
- 📊 **持仓逃生监控** — severity 评分,触发即提示平仓
- 🔌 **6 品种预留** — 第一版跑通 XAUUSD,架构按 6 品种配置驱动
- 📝 **JSONL 决策日志** — 全部 SCREEN / FILTER / BUY / SELL 落盘,方便回测

---

## 快速开始

```bash
git clone https://github.com/YOUR_ORG/YUJIN-AI-TRADER.git
cd YUJIN-AI-TRADER
cp .env.example .env       # 编辑填入 MT5 凭据
pip install -r requirements.txt
uvicorn app:app --reload
# 浏览器打开 http://127.0.0.1:8000
```

---

## 文档

- [SPEC.md](SPEC.md) — 完整需求规格、API 契约、数据结构、阶段拆解
- [docs/reference/](docs/reference/) — 原 GMGN 项目的参考文件(仅学习用,代码全部自己重写)

---

## 风险声明

本项目是交易工具,**盈亏自负,不构成投资建议**。
真实交易有资金风险,请先在模拟账户验证策略,再上 FTMO 考核。

---

## 协议

MIT — 详见 [LICENSE](LICENSE)
