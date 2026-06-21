# ZMQ桥接施工单 · 第1轮

> 铸峰接。参考文档三份：WORKFLOW-ZMQ-BRIDGE / REQ-ZMQ-BRIDGE / LLM-GUARDRAILS

## 本次要做的事

### 一、环境搭建

在悟空电脑上装好 ZMQ 依赖。

**Python端：**
```bash
pip install pyzmq
```
验证：`python -c "import zmq; print(zmq.zmq_version())"` → 输出 `4.x.x`

**MT5端：**
1. 从 https://github.com/dingmaotu/mql4-zeromq 下载 mql-zmq
2. `Include/Zmq/` 下所有 `.mqh` → 复制到 MT5的 `MQL5/Include/Zmq/`
3. `Library/` 下 `libzmq.dll`（选64位）→ 复制到 MT5的 `MQL5/Libraries/`
4. 悟空开MT5 → Tools → Options → Expert Advisors → 勾选 "Allow DLL imports"

验证：新建空EA，加一行 `#include <Zmq/Zmq.mqh>`，编译不报错。

### 二、EA开发

**文件：** `F:\yujin-mt5\mql5\Experts\YUJIN_ZMQ_Bridge.mq5`

**只做一件事：** tick到了 → JSON打包 → ZMQ push出去。

**不做的：**
- 不下单
- 不算指标
- 不写文件

**字段要求：**
```json
{"type":"tick","symbol":"XAUUSD","bid":2342.15,"ask":2342.65,"time":"2026-06-21T14:30:05.123","spread":50}
{"type":"bar","symbol":"XAUUSD","tf":"M15","time":"2026-06-21T14:30:00","o":2340.50,"h":2343.20,"l":2339.80,"c":2342.15}
```

**端口：** `tcp://127.0.0.1:5555`（写死）

**品种：** 循环 `SymbolsTotal()` 遍历。只推 `config/symbols.yaml` 里列的那14个品种。

**bar推送时机：** M15每根K线close时推。不在tick里重复推同一根bar。

### 三、验证

EA加载到任意图表后，在终端跑：
```bash
python -c "import zmq,json; ctx=zmq.Context(); s=ctx.socket(zmq.SUB); s.connect('tcp://127.0.0.1:5555'); s.setsockopt(zmq.SUBSCRIBE,b''); print(json.loads(s.recv_string()))"
```
收到带bid/ask/symbol的dict → 通了。

### 四、交付

- EA源文件 + 编译好的 `.ex5` 一起放 `F:\yujin-mt5\mql5\Experts\`
- Python验证脚本跑通的截图
- Git commit + push

---

## 铁律重申（出问题甩编号给LLM）

| 编号 | 内容 |
|------|------|
| A1 | 没有 SocketCreate/WebSocketConnect 函数，走ZMQ DLL |
| A2 | DLL放 MQL5/Libraries/，不要放C盘 |
| A5 | Allow DLL imports 必须勾 |
| C1 | EA不交易，只有 ZmqSocket.send() |
| C2 | 5555端口写死 |
| C5 | PUB/SUB会丢消息，别加重传 |

---

做完告诉我结果。
