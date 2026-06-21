//+------------------------------------------------------------------+
//|                                       YUJIN_ZMQ_Bridge.mq5      |
//|                          ZMQ Data Bridge · Phase 1               |
//|                          MT5 → Python 实时数据推送               |
//+------------------------------------------------------------------+
//  铁律引用: A1 A2 A5 C1 C2 C5
//  - 不做交易决策 (C1)
//  - 端口 5555 写死 (C2)
//  - PUB/SUB 会丢消息，不加重传 (C5)
//  - 走 Zmq.mqh + libzmq.dll，没有 SocketCreate (A1)
//  - DLL 放 MQL5/Libraries/ (A2)
//  - 用户须勾选 Allow DLL imports (A5)
//+------------------------------------------------------------------+
#property copyright "YUJIN AI TRADER"
#property version   "1.00"
#property description "ZMQ Bridge: MT5 → Python real-time tick/bar push"
#property strict

#include <Zmq/Zmq.mqh>

//--- 输入参数
input int InpTimerMs = 100;          // 轮询间隔 (ms)

//--- 常量 (写死，不读配置 — C2)
#define ZMQ_ENDPOINT "tcp://127.0.0.1:5555"

//--- ZMQ 全局对象 (析构自动清理)
Context g_ctx("yujin_zmq");
Socket  g_pub(g_ctx, ZMQ_PUB);

//--- 品种状态
string   g_sym[];                    // 品种名
int      g_dig[];                    // 小数位
int      g_cnt = 0;                  // 品种数

//--- M15 bar 追踪
datetime g_last_bar[];               // 上次推送的 bar open time

//+------------------------------------------------------------------+
//| datetime → ISO 8601 (秒级，MQL5 无毫秒)                           |
//+------------------------------------------------------------------+
string TimeToISO(datetime dt)
{
   MqlDateTime s;
   TimeToStruct(dt, s);
   return StringFormat("%04d-%02d-%02dT%02d:%02d:%02d",
                       s.year, s.mon, s.day,
                       s.hour, s.min, s.sec);
}

//+------------------------------------------------------------------+
//| 构建品种列表 (MarketWatch 可见品种)                                |
//+------------------------------------------------------------------+
void BuildSymbols()
{
   int total = SymbolsTotal(true);
   ArrayResize(g_sym, total);
   ArrayResize(g_dig, total);
   g_cnt = 0;

   for(int i = 0; i < total; i++)
   {
      string name = SymbolName(i, true);
      if(StringLen(name) == 0) continue;
      SymbolSelect(name, true);

      g_sym[g_cnt] = name;
      g_dig[g_cnt] = (int)SymbolInfoInteger(name, SYMBOL_DIGITS);
      g_cnt++;
   }

   ArrayResize(g_sym, g_cnt);
   ArrayResize(g_dig, g_cnt);
}

//+------------------------------------------------------------------+
//| Expert 初始化                                                      |
//+------------------------------------------------------------------+
int OnInit()
{
   //--- ZMQ PUB 绑定 (写死 5555 — C2)
   g_pub.bind(ZMQ_ENDPOINT);

   //--- 构建品种列表
   BuildSymbols();

   //--- 初始化 bar 追踪 (避免首根 bar 误推)
   ArrayResize(g_last_bar, g_cnt);
   for(int i = 0; i < g_cnt; i++)
      g_last_bar[i] = iTime(g_sym[i], PERIOD_M15, 0);

   //--- 启动定时器
   EventSetMillisecondTimer(InpTimerMs);

   Print("[ZMQ] Bridge started → ", ZMQ_ENDPOINT,
         " | ", g_cnt, " symbols | ", InpTimerMs, "ms interval");
   return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
//| 定时器: 遍历品种推 tick + 检测新 M15 bar                           |
//+------------------------------------------------------------------+
void OnTimer()
{
   for(int i = 0; i < g_cnt; i++)
   {
      string sym = g_sym[i];
      int    dig = g_dig[i];

      //--- tick 推送
      MqlTick tick;
      if(SymbolInfoTick(sym, tick))
      {
         int spread = (int)SymbolInfoInteger(sym, SYMBOL_SPREAD);
         string json = StringFormat(
            "{\"type\":\"tick\",\"symbol\":\"%s\",\"bid\":%s,\"ask\":%s,\"time\":\"%s\",\"spread\":%d}",
            sym,
            DoubleToString(tick.bid, dig),
            DoubleToString(tick.ask, dig),
            TimeToISO(tick.time),
            spread
         );
         ZmqMsg msg(json);
         g_pub.send(msg);
      }

      //--- M15 bar (新 bar 形成时推上一根已完成的 bar)
      datetime bar_time = iTime(sym, PERIOD_M15, 0);
      if(bar_time > 0 && bar_time != g_last_bar[i])
      {
         g_last_bar[i] = bar_time;

         // index 1 = 刚收盘的那根
         double o = iOpen(sym, PERIOD_M15, 1);
         double h = iHigh(sym, PERIOD_M15, 1);
         double l = iLow(sym, PERIOD_M15, 1);
         double c = iClose(sym, PERIOD_M15, 1);

         if(o > 0)
         {
            datetime bar_open = iTime(sym, PERIOD_M15, 1);
            string bar_json = StringFormat(
               "{\"type\":\"bar\",\"symbol\":\"%s\",\"tf\":\"M15\",\"time\":\"%s\",\"o\":%s,\"h\":%s,\"l\":%s,\"c\":%s}",
               sym,
               TimeToISO(bar_open),
               DoubleToString(o, dig),
               DoubleToString(h, dig),
               DoubleToString(l, dig),
               DoubleToString(c, dig)
            );
            ZmqMsg bar_msg(bar_json);
            g_pub.send(bar_msg);
         }
      }
   }
}

//+------------------------------------------------------------------+
//| Expert 反初始化                                                    |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   EventKillTimer();
   g_pub.unbind(ZMQ_ENDPOINT);
   Print("[ZMQ] Bridge stopped (reason=", reason, ")");
}
//+------------------------------------------------------------------+
