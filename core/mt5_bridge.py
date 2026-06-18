"""
MT5 桥接模块 — Phase 8 v4 · 救命药一(完整版):

 核心锁消除原则:
   · MT5 Python SDK 底层 C++ DLL,严格单线程同步阻塞
   · 全场 所有 MT5 调用 走 _mt5_executor (max_workers=1) 串行化
   · 应用层 完全 不 用    bridge._lock   OS 层   1 线程  天然 串行
   · asyncio.to_thread (默认 ThreadPoolExecutor 多线程) 不 用   会 DLL segfault
   · 跨 event loop 调 chain = loop.run_in_executor(_mt5_executor, sync_fn)

 设计:
   1. sync 函 (copy_rates, heartbeat_ping, init_readonly, ...)
   2. async 包装  函 (copy_rates_async, heartbeat_ping_async, ...)  路由 直 接 await
   3. trade 原子:sync_execute_trade 包 init+send+shutdown 一个 链  →  execute_trade_async 单 executor call
     (分 3 调 init/order/shutdown 被 心跳 / other  插入 上下文乱 → 必须 atomic)
"""
import os
import time
import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor
from enum import Enum
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List
import pandas as pd
import MetaTrader5 as mt5
import logging
logger = logging.getLogger(__name__)


class MT5State(str, Enum):
    DISCONNECTED = "DISCONNECTED"
    CONNECTING = "CONNECTING"
    CONNECTED = "CONNECTED"
    RECONNECTING = "RECONNECTING"


# ============================================================
# 救命药一:全局单线程 Executor 锁消除
#   · MT5 Python SDK 底层 C++ DLL,严格单线程同步阻塞
#   · max_workers=1 → OS 层 串行化,不需要 bridge._lock
#   · 不 死锁 · 不 挣扎 · 不 hung
# ============================================================
_mt5_executor = ThreadPoolExecutor(
    max_workers=1,
    thread_name_prefix="mt5_worker",
)


def _run_in_mt5(sync_fn, *args, **kwargs):
    """顶层 helper:把 sync 函 扔 到 _mt5_executor  →  await 拿 future"""
    loop = asyncio.get_running_loop()
    return loop.run_in_executor(_mt5_executor, lambda: sync_fn(*args, **kwargs))


class MT5Bridge:
    """MT5 单线程 Executor 桥接 · 全场 async safe"""

    def __init__(self):
        # 不 再 self._lock  · 走 _mt5_executor
        self._ro = False
        self._tr = False
        self._state = MT5State.DISCONNECTED
        self._last_heartbeat: Optional[float] = None
        self._reconnect_count = 0
        self._heartbeat_stop = threading.Event()
        self._heartbeat_thread: Optional[threading.Thread] = None
        self._base_s = int(os.getenv("MT5_RECONNECT_BASE_S", "5"))
        self._max_s = int(os.getenv("MT5_RECONNECT_MAX_S", "60"))
        self._hb_s = int(os.getenv("MT5_HEARTBEAT_S", "30"))
        self._data_mode = os.getenv("MT5_DATA_MODE", "SHADOW").upper()
        self._magic = int(os.getenv("MT5_MAGIC_NUMBER", "20260617"))  # env 可置

    @property
    def state(self):
        return self._state

    @property
    def last_heartbeat(self):
        return self._last_heartbeat

    @property
    def reconnect_count(self):
        return self._reconnect_count

    @property
    def data_mode(self):
        return self._data_mode

    def transition(self, new_state):
        if new_state != self._state:
            logger.info("MT5 state %s -> %s", self._state.value, new_state.value)
            self._state = new_state

    # ============================================================
    # sync 方法 — 内部 _mt5_executor.submit 走
    # 路由 别 直 接 调 sync 方法 · 必须 走 async_*_async
    # ============================================================
    def _submit(self, fn, *args, **kwargs):
        return _mt5_executor.submit(fn, *args, **kwargs)

    def init_readonly(self, path=None) -> bool:
        if self._ro:
            return True
        self.transition(MT5State.CONNECTING)
        p = path or os.getenv("MT5_PATH")
        kw = {"path": p} if p else {}
        try:
            fut = _mt5_executor.submit(mt5.initialize, **kw)
            ok = fut.result(timeout=10)
            if not ok:
                logger.warning("MT5 readonly init fail (mode=%s): %s", self._data_mode, mt5.last_error())
                self.transition(MT5State.RECONNECTING)
                return False
            self._ro = True
            self._last_heartbeat = time.time()
            self.transition(MT5State.CONNECTED)
            return True
        except Exception as e:
            logger.error("MT5 init exception: %s", e)
            self.transition(MT5State.RECONNECTING)
            return False

    async def init_readonly_async(self, path=None, timeout: float = 10.0) -> bool:
        """async 版 — lifespan 调用 · 永不 卡 event loop"""
        return await asyncio.wait_for(
            _run_in_mt5(self.init_readonly, path),
            timeout=timeout,
        )

    def init_for_trade(self, login, password, server) -> bool:
        if self._tr:
            return True
        kw = {"login": login, "password": password, "server": server}
        p = os.getenv("MT5_PATH")
        if p:
            kw["path"] = p
        try:
            fut = _mt5_executor.submit(mt5.initialize, **kw)
            ok = fut.result(timeout=10)
            if not ok:
                return False
            self._tr = True
            return True
        except Exception:
            return False

    def shutdown_trade(self):
        if self._tr:
            try:
                _mt5_executor.submit(mt5.shutdown).result(timeout=5)
            finally:
                self._tr = False

    def shutdown_all(self):
        self.stop_heartbeat()
        if self._ro or self._tr:
            try:
                _mt5_executor.submit(mt5.shutdown).result(timeout=5)
            finally:
                self._ro = self._tr = False
                self.transition(MT5State.DISCONNECTED)

    async def shutdown_all_async(self):
        """lifespan shutdown 调 · event loop 友好"""
        await _run_in_mt5(self.shutdown_all)

    # ============================================================
    # heartbeat (后台 daemon thread · 调 sync internal get_state)
    # ============================================================
    def start_heartbeat(self):
        if self._heartbeat_thread and self._heartbeat_thread.is_alive():
            return
        self._heartbeat_stop.clear()
        self._heartbeat_thread = threading.Thread(
            target=self._heartbeat_loop,
            daemon=True,
            name="mt5-heartbeat",
        )
        self._heartbeat_thread.start()

    def stop_heartbeat(self):
        self._heartbeat_stop.set()
        if self._heartbeat_thread:
            self._heartbeat_thread.join(timeout=6)

    def _heartbeat_loop(self):
        delay = self._base_s
        while not self._heartbeat_stop.is_set():
            if self._heartbeat_stop.wait(self._hb_s):
                break
            alive = False
            if self._ro:
                try:
                    fut = _mt5_executor.submit(mt5.terminal_info)
                    info = fut.result(timeout=5)
                    alive = bool(info and getattr(info, "connected", False))
                except Exception:
                    alive = False
            if alive:
                self._last_heartbeat = time.time()
                delay = self._base_s
                if self._state != MT5State.CONNECTED:
                    self.transition(MT5State.CONNECTED)
            elif self._ro:
                self._reconnect_count += 1
                self.transition(MT5State.RECONNECTING)
                self._ro = False
                if self._heartbeat_stop.wait(delay):
                    break
                if not self.init_readonly():
                    delay = min(delay * 2, self._max_s)

    # ============================================================
    # data ops — sync + async 包装
    # ============================================================
    def copy_rates(self, symbol: str, timeframe: str, count: int = 200):
        if not self._ro and not self.init_readonly():
            return None
        tf_map = {
            "M5": mt5.TIMEFRAME_M5, "M15": mt5.TIMEFRAME_M15,
            "H1": mt5.TIMEFRAME_H1, "H4": mt5.TIMEFRAME_H4, "D1": mt5.TIMEFRAME_D1,
        }
        tf = tf_map.get(timeframe)
        if tf is None:
            return None
        try:
            fut = _mt5_executor.submit(mt5.copy_rates_from_pos, symbol, tf, 0, count)
            rates = fut.result(timeout=10)
            if rates is None or len(rates) == 0:
                return None
            df = pd.DataFrame(rates)
            df["time"] = pd.to_datetime(df["time"], unit="s")
            return df
        except Exception:
            return None

    async def copy_rates_async(self, symbol: str, timeframe: str, count: int = 200, timeout: float = 10.0):
        """async 版 — 路由 / scanner 用 · 永不 卡 event loop"""
        return await asyncio.wait_for(
            _run_in_mt5(self.copy_rates, symbol, timeframe, count),
            timeout=timeout,
        )

    def symbol_info(self, symbol):
        if not self._ro and not self.init_readonly():
            return None
        try:
            fut = _mt5_executor.submit(mt5.symbol_info, symbol)
            info = fut.result(timeout=5)
            if info is None:
                return None
            return {
                "symbol": info.name, "point": info.point, "digits": info.digits,
                "spread": info.spread, "volume_min": info.volume_min,
                "volume_max": info.volume_max, "volume_step": info.volume_step,
                "trade_contract_size": info.trade_contract_size, "trade_mode": info.trade_mode,
            }
        except Exception:
            return None

    async def symbol_info_async(self, symbol, timeout: float = 5.0):
        return await asyncio.wait_for(
            _run_in_mt5(self.symbol_info, symbol),
            timeout=timeout,
        )

    def account_info(self):
        if not self._ro and not self.init_readonly():
            return None
        try:
            fut = _mt5_executor.submit(mt5.account_info)
            info = fut.result(timeout=5)
            if info is None:
                return None
            return {
                "login": info.login, "balance": info.balance, "equity": info.equity,
                "margin": info.margin, "free_margin": info.free_margin,
                "leverage": info.leverage, "server": info.server,
            }
        except Exception:
            return None

    async def account_info_async(self, timeout: float = 5.0):
        return await asyncio.wait_for(
            _run_in_mt5(self.account_info),
            timeout=timeout,
        )

    def heartbeat_ping(self) -> bool:
        if not self._ro:
            return False
        try:
            fut = _mt5_executor.submit(mt5.terminal_info)
            info = fut.result(timeout=5)
            return bool(info and getattr(info, "connected", False))
        except Exception:
            return False

    async def heartbeat_ping_async(self, timeout: float = 5.0) -> bool:
        return await asyncio.wait_for(
            _run_in_mt5(self.heartbeat_ping),
            timeout=timeout,
        )

    # ============================================================
    # trade atomic: sync_execute_trade — 单 chain init+send+force-shutdown
    #   · 必 拆    3 调 init/order/shutdown   心跳/其他  插入串 上下文乱
    #   · review MUST FIX #2:init_for_trade raise  _tr 未 set   shutdown_trade
    #     跳过 mt5.shutdown   会话 leak     兜底 强制 mt5.shutdown
    # ============================================================
    def sync_execute_trade(self, symbol: str, side: str, lots: float,
                            sl: float, tp: float, comment: str,
                            login: int, password: str, server: str) -> Optional[Dict[str, Any]]:
        """单 thread atom init_for_trade + order_send → force shutdown + _tr=False."""
        try:
            if not self.init_for_trade(login, password, server):
                return {"ok": False, "error": "MT5 trade init 失败"}
            return self._order_send_inline(symbol, side, lots, sl, tp, comment)
        finally:
            # review MUST FIX #2 兜底:位 sync · 荐 始关
            try:
                _mt5_executor.submit(mt5.shutdown).result(timeout=5)
            except Exception as e:
                logger.debug("trade force-shutdown exception: %s", e)
            self._tr = False

    async def execute_trade_async(self, symbol: str, side: str, lots: float,
                                    sl: float, tp: float, comment: str,
                                    login: int, password: str, server: str,
                                    timeout: float = 30.0):
        """单 executor call ·  嵌 init+send+shutdown · event loop 友好"""
        return await asyncio.wait_for(
            _run_in_mt5(self.sync_execute_trade, symbol, side, lots, sl, tp,
                        comment, login, password, server),
            timeout=timeout,
        )

    def _order_send_inline(self, symbol, order_type, lots, sl=0.0, tp=0.0, comment=""):
        """内 inline  · 仅 sync_execute_trade 调 · 不供外部"""
        try:
            fut_tick = _mt5_executor.submit(mt5.symbol_info_tick, symbol)
            tick = fut_tick.result(timeout=5)
            if tick is None:
                return {"ok": False, "error": "tick 无"}
            if order_type.upper() == "BUY":
                mt5_type, price = mt5.ORDER_TYPE_BUY, tick.ask
            else:
                mt5_type, price = mt5.ORDER_TYPE_SELL, tick.bid
            req = {
                "action": mt5.TRADE_ACTION_DEAL, "symbol": symbol, "volume": lots,
                "type": mt5_type, "price": price, "sl": sl, "tp": tp,
                "deviation": 20, "magic": self._magic, "comment": comment,
                "type_time": mt5.ORDER_TIME_GTC, "type_filling": mt5.ORDER_FILLING_IOC,
            }
            fut = _mt5_executor.submit(mt5.order_send, req)
            result = fut.result(timeout=10)
            if result is None:
                return {"ok": False, "error": "MT5 无回执"}
            if result.retcode != mt5.TRADE_RETCODE_DONE:
                return {"ok": False, "retcode": result.retcode, "comment": result.comment}
            return {"ok": True, "ticket": result.order, "price": price, "lots": lots}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    # ============================================================
    # positions (read-only · scan  monitor)
    # ============================================================
    def positions_get(self, symbol=None):
        if not self._ro and not self.init_readonly():
            return []
        try:
            if symbol:
                fut = _mt5_executor.submit(mt5.positions_get, symbol=symbol)
            else:
                fut = _mt5_executor.submit(mt5.positions_get)
            pos = fut.result(timeout=5)
            if pos is None:
                return []
            result = []
            for p in pos:
                fut_si = _mt5_executor.submit(mt5.symbol_info, p.symbol)
                si = fut_si.result(timeout=3)
                cs = si.trade_contract_size if si else 100
                pp = (p.profit / (p.volume * cs)) * 100 if cs > 0 else 0
                result.append({
                    "ticket": p.ticket, "symbol": p.symbol,
                    "type": "BUY" if p.type == mt5.POSITION_TYPE_BUY else "SELL",
                    "lots": p.volume, "entry": p.price_open, "current": p.price_current,
                    "sl": p.sl, "tp": p.tp, "pnl": p.profit, "pnl_pct": round(pp, 2),
                    "open_time": datetime.fromtimestamp(
                        p.time, tz=timezone(timedelta(hours=8))
                    ).isoformat(),
                })
            return result
        except Exception:
            return []

    async def positions_get_async(self, symbol=None, timeout: float = 5.0):
        return await asyncio.wait_for(
            _run_in_mt5(self.positions_get, symbol),
            timeout=timeout,
        )

    def close_position(self, ticket):
        if not self._tr:
            return None
        try:
            fut_pl = _mt5_executor.submit(mt5.positions_get, ticket=ticket)
            pl = fut_pl.result(timeout=5)
            if not pl:
                return None
            pos = pl[0]
            fut_t = _mt5_executor.submit(mt5.symbol_info_tick, pos.symbol)
            tick = fut_t.result(timeout=5)
            if tick is None:
                return None
            if pos.type == mt5.POSITION_TYPE_BUY:
                ct, price = mt5.ORDER_TYPE_SELL, tick.bid
            else:
                ct, price = mt5.ORDER_TYPE_BUY, tick.ask
            req = {
                "action": mt5.TRADE_ACTION_DEAL, "symbol": pos.symbol,
                "volume": pos.volume, "type": ct, "position": ticket,
                "price": price, "deviation": 20, "magic": self._magic,
                "comment": "close",
                "type_time": mt5.ORDER_TIME_GTC, "type_filling": mt5.ORDER_FILLING_IOC,
            }
            fut = _mt5_executor.submit(mt5.order_send, req)
            result = fut.result(timeout=10)
            if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
                return {"ok": False, "error": str(result.comment if result else mt5.last_error())}
            return {"ok": True, "pnl": pos.profit}
        except Exception:
            return None


bridge = MT5Bridge()


def shutdown_mt5_executor(wait: bool = True):
    _mt5_executor.shutdown(wait=wait)
