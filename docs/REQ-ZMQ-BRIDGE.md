# ZMQ桥接 · 需求文档

## 一、背景问题

当前 `core/mt5_bridge.py` 通过 `MetaTrader5` Python包主动轮询MT5取数据。

**问题**：
- `copy_rates_from_pos()` 是同步阻塞调用。MT5终端响应慢时，Python线程卡住
- 高频轮询时，`mt5.initialize()`/`shutdown()` 反复调用导致终端不稳定
- FastAPI事件循环被同步IO阻塞，前端请求延迟堆叠
- 本质是"请求-响应"模式，不是实时推送。滞后随轮询间隔线性增长

## 二、目标

MT5终端实时推送 tick 和 M15 K线 → Python后端异步消费 → 前端看板秒级刷新

## 三、技术选型

**ZeroMQ (PUB/SUB模式)**

理由：
- MQL5社区广泛使用，Darwin的[mql4-zeromq](https://github.com/dingmaotu/mql4-zeromq)库维护多年
- PUB/SUB天然一对多。未来新增消费端不用改EA
- 自带缓冲和断线重连，不丢数据
- `pyzmq` 官方包，Windows兼容性好

不选WebSocket的理由：
- MQL5的`WebRequest`受限于MT5 URL白名单（Options → Expert Advisors → Allow WebRequest）
- `WebRequest`每次调用有500ms间隔限制，tick频率下不够
- WebSocket在MQL5里需要自己实现协议帧，复杂度高

## 四、架构

```
┌──────────────┐     ZMQ PUB      ┌──────────────┐     ASGI      ┌──────────┐
│  MT5终端      │ ──────────────→ │  Python后端   │ ──────────→  │  前端HTML │
│  EA(ZMQ push) │  tcp://127.0.0.1│  pyzmq sub    │  FastAPI     │  浏览器    │
│               │     :5555       │               │  SSE推送     │           │
└──────────────┘                  └──────────────┘              └──────────┘
```

**EA职责**：只推数据。不交易，不分析，不落盘。

**Python职责**：消费数据 → 跑6道闸门 → 推前端 → 记录日志。

**前端职责**：不变。跟现在一样收`/api/run`数据。

## 五、数据协议

### EA → Python (ZMQ消息)

每条消息一个JSON对象，UTF-8编码。

**tick消息**：
```json
{
  "type": "tick",
  "symbol": "XAUUSD",
  "bid": 2342.15,
  "ask": 2342.65,
  "time": "2026-06-21T14:30:05.123",
  "spread": 50
}
```

**K线消息**（M15 close时推一根）：
```json
{
  "type": "bar",
  "symbol": "XAUUSD",
  "tf": "M15",
  "time": "2026-06-21T14:30:00",
  "o": 2340.50,
  "h": 2343.20,
  "l": 2339.80,
  "c": 2342.15
}
```

### Python → 前端 (不变)

保持现有 `/api/run` 响应格式。前端不动。

## 六、品种覆盖

按 `config/symbols.yaml` 中的14品种推送。EA加载到第一个品种图表即可，`Symbol()` 循环遍历 `SymbolsTotal()` 和 `SymbolName()`。

## 七、非功能性要求

| 项 | 要求 |
|----|------|
| 延迟 | tick到达 → Python消费 < 50ms |
| 重连 | EA或Python重启，ZMQ自动恢复，无人工干预 |
| 端口 | `tcp://127.0.0.1:5555` 写死，不出现在配置文件里 |
| 编码 | 全UTF-8 |
| 日志 | EA不写盘；Python端仅ERROR级写盘 |
| 安全 | 只bind 127.0.0.1。不暴露到外网 |

## 八、不做什么

- EA不做交易决策
- 不存历史tick数据（Python端如需，后续加）
- 不改前端
- 不改6道闸门逻辑
- 不碰V4.5/御金PRO
