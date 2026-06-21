# 大模型幻觉打地鼠 · 开发铁律

> 用法：每次让大模型写码前，把这份文档贴进上下文。打中了直接引用编号。

---

## A. MQL5禁区

### A1 — 函数不存在
MQL5里没有这些函数。看到直接否决：
- `SocketCreate()` / `SocketConnect()` / `SocketSend()` — MQL5不支持原生socket
- `WebSocketConnect()` — 没有这个内置函数
- `PushData()` / `StreamTick()` — 不存在，别自己发明
- `send()` / `recv()` — C语言的，不是MQL5的

**正确做法**：ZeroMQ只通过第三方DLL（`Zmq.mqh` + `libzmq.dll`）使用。所有socket操作走 `ZmqMsg` / `ZmqSocket` 类。

### A2 — DLL路径
MQL5加载DLL走的是MT5安装目录的 `MQL5/Libraries/`，不是Windows系统路径。

❌ `#import "C:\Users\Administrator\Downloads\libzmq.dll"`  
✓ 把DLL放进 `MQL5/Libraries/`，然后 `#import "libzmq.dll"`

### A3 — WebRequest不是WebSocket
`WebRequest()` 是HTTP请求，不是WebSocket。每次调用之间最少间隔500ms。给tick数据用这个=找死。

### A4 — MQL4/MQL5语法混用
MQL4的 `start()` 在MQL5里不存在。MQL5用 `OnTick()`。  
MQL4的 `OrderSend()` 参数顺序和MQL5完全不同。不过本项目EA不交易，不碰这个。

### A5 — DLL调用权限
MT5默认禁止EA调用DLL。用户必须手动开启：
Tools → Options → Expert Advisors → ✓ Allow DLL imports

EA代码里不加 `#property strict` 会导致编译警告但能用。`#property strict` 推荐加。

---

## B. Python端禁区

### B1 — pyzmq版本
❌ `import zmq` 不能直接用，需要 `pip install pyzmq`  
❌ 不要假设系统装了 `libzmq`。Windows上 `pyzmq` 自带bundled的libzmq，不需要单独装C库。

### B2 — 不要在async里阻塞
zmq的 `recv()` 默认阻塞。Python端必须用 `zmq.Poller` 或 `zmq.DEALER` 配合 asyncio 的事件循环。

❌ `data = socket.recv()` 直接写在 async 函数里  
✓ 用 `asyncio.get_event_loop().run_in_executor()` 包一层，或走 `zmq.asyncio`

### B3 — mt5.initialize() 只能调一次
当前代码如果用 `mt5.initialize()` + 后续 `shutdown()` 循环，改ZMQ后删掉这整个循环。  
ZMQ通路建立后，不再需要主动调用任何 `MetaTrader5` 包函数。

### B4 — 路径硬编码
❌ `path="C:\Program Files\MetaTrader 5\terminal64.exe"`  
✓ 从 `config/settings.yaml` 或 `.env` 读。MT5安装路径两台电脑可能不同。

### B5 — pip包不存在
❌ `pip install metaapi-zeromq` — 这个包不存在，别编  
❌ `pip install mt5zeromq` — 也不存在  
✓ 只装 `pyzmq`。ZMQ桥接不需要任何额外的MT5专用Python包。

---

## C. 架构禁区

### C1 — EA不能做交易决策
EA只推数据。风控、闸门、买卖单、止盈止损全在Python端。

❌ EA里写 `OrderSend()`  
✓ EA里只有 `ZmqSocket.send()`

### C2 — 端口不能出现在配置里
5555写死在EA代码和Python代码里。不读yaml不读env。改端口=改代码重编译。

### C3 — 不碰V4.5
本项目 `F:\yujin-mt5\` 物理隔离于 `F:\trading-wiki\` 下的V4.5。不import，不参考，不复用。

### C4 — MT5终端不能被代码关闭
不要用 `mt5.shutdown()`。不要杀 terminal64.exe 进程。MT5终端只能悟空手动关。

---

## D. 环境禁区

### D1 — 不要用WSL路径
所有路径用 Windows 原生格式：`F:\yujin-mt5\`，不是 `/mnt/f/yujin-mt5/`。  
Hermes/MSYS2里可以用 `/f/yujin-mt5/`，但MQL5编译器只看Windows路径。

### D2 — Python版本
当前环境 Python 3.11.7。不要用Python 3.12+的语法（如 f-string 内的反斜杠）。  
用 `python` 命令，不是 `python3`。

### D3 — 不要发明依赖
每装一个包之前，先确认它真的存在：`pip index versions <包名>` 或 `pip search`。  
不准编造 pip 包名。

### D4 — 文件编码
全部 UTF-8。MQL5源文件也是UTF-8（MT5编译器支持）。EA里有中文注释不会乱码。

---

## E. 常见幻觉速查

| 幻觉 | 打地鼠引用 |
|------|-----------|
| "用WebSocket从MT5推数据" | A1, A3 |
| "pip install mt5-zmq" | B5 |
| "EA里用socket库" | A1 |
| "把DLL放C盘System32" | A2 |
| "Python直接调MQL5函数" | B3 |
| "改一下mt5_bridge.py的轮询间隔就行" | B3 (轮询全删) |
| "EA顺便做个简单止损" | C1 |
| "用redis做消息队列中间层" | C3 (不引入新依赖) |

---

## F. 使用规则

1. **大模型给出代码后**，先扫一遍这个清单，对号入座
2. **命中A1-A5** → 代码直接作废，让重写
3. **命中B1-B5** → 指出具体行号，让修正
4. **命中C1-C4** → 代码作废+提醒铁律，不商量
5. **命中D1-D4** → 纠正路径/版本/命令
6. **连续命中3次** → 换一个模型或换一个角度重新提问。别再纠同一个错误
