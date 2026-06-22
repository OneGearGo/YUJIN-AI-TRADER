# ZMQ桥接施工单 · 第2轮 — 成交回传 + EA下单

> 前提：Phase 1 已通（EA推tick → ZMQ 5555 → Python consumer）
> 这次做：前端点买入 → Python → ZMQ 5556 → EA下单 → 成交回传

## 架构变化

之前：
```
MT5(EA) —push→ ZMQ :5555 —→ Python —→ 前端
```

之后：
```
Ticks:  MT5(EA) —ZMQ 5555—→ Python —→ 前端
订单:   前端 —→ Python —ZMQ 5556—→ MT5(EA)  → OrderSend → 回单到 Python 显示
```

## 两步改动

### 第一步：EA端（铸峰）

**改 `YUJIN_ZMQ_Bridge.mq5`**，在现有push逻辑后面加一个ZMQ socket收消息：

```cpp
// 新增：成交信号接收 socket（ZMQ SUB，收 Python 指令）
void OnTick(){
    // 原有的 push 逻辑不变
  
    // 新增：检查是否有成交指令过来
    ZmqMsg msg;
    if(recv_socket.recv(msg, ZMQ_DONTWAIT)){
        string json = msg.data();
        // 解析 json → 拿到 action/symbol/lots/sl/tp
        // action == "buy" → OrderSend BUY
        // action == "sell" → OrderSend SELL
        // action == "close" → 平仓指定订单
        // 下单完成后，通过 push_socket 发回成交回单
    }
}
```

**JSON协议（从Python发来）：**
```json
{
  "action": "buy",
  "symbol": "XAUUSD",
  "lots": 0.05,
  "sl": 2330.0,
  "tp": 2350.0,
  "order_id": "uuid-1234"
}
```

**成交回单（EA发回Python）：**
```json
{
  "type": "order_result",
  "order_id": "uuid-1234",
  "ok": true,
  "ticket": 12345678,
  "price": 2342.15,
  "lots": 0.05
}
```

**端口分配：**
- ZMQ :5555 — EA → Python（tick/bar数据，现有，不改）
- ZMQ :5556 — Python → EA（成交指令）
- EA 在 OnInit() 里同时绑定两个 socket：push_socket（5555，PUB） + sub_socket（5556，SUB）

**不做的：**
- EA里不做风控、不做计算、不做判断
- EA只做三件事：收指令 → 下单 → 回传结果

### 第二步：Python端（铸峰）

**改 `core/zmq_subscriber.py`**，在现有 5555 消费逻辑后面加：

```python
# 新增：成交指令发送通道
import zmq.asyncio

ctx_send = zmq.asyncio.Context()
push_socket = ctx_send.socket(zmq.PUB)
push_socket.bind("tcp://127.0.0.1:5556")  # 绑定5556

async def send_order(action, symbol, lots, sl, tp):
    """前端点成交后调用，发指令给EA"""
    msg = json.dumps({
        "action": action,
        "symbol": symbol,
        "lots": lots,
        "sl": sl,
        "tp": tp,
        "order_id": str(uuid.uuid4())
    })
    await push_socket.send_string(msg)
```

**前端/api/buy 路由做两件事：**
1. 调 `send_order()` 发指令给EA
2. 挂起等待EA回单（通过ZMQ回传），回单到了才给前端返回成交结果

## 验证

1. MT5加载新EA，日志确认两个socket都绑定了（5555 PUB + 5556 SUB）
2. Python启动，日志有 `ZMQ send socket bound to 5556`
3. 前端点买入 → 看MT5日志有 `OrderSend` 执行记录 → MT5持仓出现
4. Python日志收到成交回单 → 前端持仓监控出现新持仓

## 铁律（复读机）

| 编号 | 内容 |
|------|------|
| C1 | EA不做交易决策。风控/闸门/判断全在Python |
| C5 | PUB/SUB会丢消息。成交消息丢了下次补 |
| C2 | 5555和5556都写死，不出配置 |
| E速查 | LLM说"用Redis""用数据库持久化"直接否决 |
