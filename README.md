# 御金量化 · yujin-mt5

> 形态借自 GMGN AI Trader 看板，内核是 MT5 行情 + 御金交易策略。

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
