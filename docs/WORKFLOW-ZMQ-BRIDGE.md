# ZMQ桥接 · 施工工作流

> 目标：MT5 EA 通过 ZeroMQ 实时推送 tick/K线 → Python pyzmq 订阅 → FastAPI → 前端

## 工期估算

| 阶段 | 内容 | 预估 |
|------|------|------|
| Phase 1 | 环境搭建：ZeroMQ安装 + pyzmq + MQL5 ZMQ库 | 0.5天 |
| Phase 2 | EA开发：MQL5 push端，tick→ZMQ | 2天 |
| Phase 3 | Python改造：mt5_bridge.py 轮询→subscriber | 1天 |
| Phase 4 | 联调：品种对齐 + 字段映射 + 重连测试 | 1.5天 |
| Phase 5 | 文档 + 锁死 | 0.5天 |

**总：约1周（5个工作日）**

## 分阶段步骤

### Phase 1：环境搭建

```bash
# Python端
pip install pyzmq

# MT5端
# 1. 从 https://github.com/dingmaotu/mql4-zeromq 下载 mql-zmq
# 2. 将 Include/ 下的 .mqh 文件放入 MT5 的 MQL5/Include/Zmq/
# 3. 将 Library/ 下的 .dll 放入 MT5 的 MQL5/Libraries/
#    注意：DLL分32位/64位，MT5用64位
```

**校验点**：MT5编译EA时不报 "cannot open include file Zmq.mqh"

### Phase 2：EA开发（铸峰写）

**文件**：`Experts/YUJIN_ZMQ_Bridge.mq5`

**核心逻辑**：
```
OnInit → ZMQ Context 初始化 → 绑定 tcp://127.0.0.1:5555
OnTick → 取 Symbol() + Bid + Ask + 时间 → json打包 → zmq_send
        → 取当前M15 K线(Open/High/Low/Close) → json打包 → zmq_send
OnDeinit → 关闭ZMQ socket
```

**铁律**：
- 不做任何交易逻辑。只推数据。风控/筛选/买卖全是Python的事
- JSON keys 用英文小写：`symbol, bid, ask, time, o, h, l, c, tf`
- 一次 tick 只推一笔，不攒 batch
- ZMQ 端口写死 `5555`，不读配置文件
- 不加日志落盘。跑起来就是静默推

**校验点**：加载EA后，用 `python -c "import zmq; ctx=zmq.Context(); s=ctx.socket(zmq.SUB); s.connect('tcp://127.0.0.1:5555'); s.setsockopt(zmq.SUBSCRIBE,b''); print(s.recv_string())"` 收到数据

### Phase 3：Python改造

**文件**：`core/mt5_bridge.py`

**改动**：
1. 删掉所有 `mt5.copy_rates_from_pos()` / `mt5.copy_ticks_from()` 调用
2. 删掉轮询循环（`while True: time.sleep()` 那套）
3. 新增 ZMQ subscriber：

```python
import zmq
import asyncio

ctx = zmq.Context()
socket = ctx.socket(zmq.SUB)
socket.connect("tcp://127.0.0.1:5555")
socket.setsockopt(zmq.SUBSCRIBE, b"")

async def zmq_listen():
    while True:
        raw = socket.recv_string()
        tick = json.loads(raw)
        # 推给现有6道闸门处理链
        await pipeline.process(tick)
```

**铁律**：
- `zmq_listen` 跑在独立 asyncio 任务里，不阻塞 FastAPI 事件循环
- 收到数据 -> 扔队列 -> 立刻返回等下一笔。不攒，不延迟处理
- ZMQ重连由pyzmq自动处理，不写手动重连逻辑

**校验点**：FastAPI `http://127.0.0.1:8000/api/status` 返回数据源状态 "zmq_connected"

### Phase 4：联调

1. MT5开终端 → 加载EA到任意品种图表 → 看MT5日志：无报错
2. 启Python后端 → `uvicorn app:app` → `/api/status` 显示 zmq_connected
3. MT5品种价格跳动 → 前端看板刷新 → 确认品种/价格/时间正确
4. 断MT5连接测试 → ZMQ自动重连 → 数据恢复 → 无崩溃
5. 重启Python后端 → 自动重连 → 前端恢复

**铁律**：联调时铸峰和观澜一起看。数据对不上当场查，不隔夜。

### Phase 5：锁死

- WORKLOG 记录踩坑
- 锁死 ZMQ 端口/JSON字段/Python端队列逻辑
- 不动的部分明确标注 "LOCKED"
