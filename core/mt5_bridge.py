"""
MT5 桥接模块 -- Phase 8:状态机 + threading.Lock + 心跳与指数退避重连
"""
import os
import time
import threading
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


class MT5Bridge:
    """MT5 连接管理 + 状态机 + heartbeat"""

    def __init__(self):
        self._lock = threading.Lock()
        self._ro = False
        self._tr = False
        self._state = MT5State.DISCONNECTED
        self._last_heartbeat = None
        self._reconnect_count = 0
        self._heartbeat_stop = threading.Event()
        self._heartbeat_thread = None
        self._base_s = int(os.getenv("MT5_RECONNECT_BASE_S", "5"))
        self._max_s = int(os.getenv("MT5_RECONNECT_MAX_S", "60"))
        self._hb_s = int(os.getenv("MT5_HEARTBEAT_S", "30"))
        self._data_mode = os.getenv("MT5_DATA_MODE", "SHADOW").upper()

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

    def init_readonly(self, path=None):
        """只读 init — Phase 8 fix:不再写死 SHADOW 返 False,mdata_mode 只作 logging 参考。

        若 MT5 终端未启 / unavailable,init 失败 → heartbeat 进 RECONNECTING 循环;
        data_mode=SHADOW 时返 False,是 lifycle 心跳 不付 Flutter 礼。
        """
        if self._ro:
            return True
        self.transition(MT5State.CONNECTING)
        p = path or os.getenv("MT5_PATH")
        kw = {"path": p} if p else {}
        try:
            with self._lock:
                ok = mt5.initialize(**kw) if kw else mt5.initialize()
            if not ok:
                logger.warning(
                    "MT5 readonly init fail (mode=%s): %s · heartbeat 会重连",
                    self._data_mode, mt5.last_error(),
                )
                self.transition(MT5State.RECONNECTING)
                return False
            self._ro = True
            self._last_heartbeat = time.time()
            self.transition(MT5State.CONNECTED)
            logger.info("MT5 readonly init OK state=CONNECTED")
            return True
        except Exception as e:
            logger.error("MT5 init exception: %s", e)
            self.transition(MT5State.RECONNECTING)
            return False

    def init_for_trade(self, login, password, server):
        if self._tr:
            return True
        kw = {"login": login, "password": password, "server": server}
        p = os.getenv("MT5_PATH")
        if p:
            kw["path"] = p
        try:
            with self._lock:
                ok = mt5.initialize(**kw)
            if not ok:
                logger.error("MT5 trade init fail: %s", mt5.last_error())
                return False
            self._tr = True
            logger.info("MT5 trade init login=%d", login)
            return True
        except Exception:
            return False

    def shutdown_trade(self):
        if self._tr:
            try:
                with self._lock:
                    mt5.shutdown()
            finally:
                self._tr = False

    def shutdown_all(self):
        self.stop_heartbeat()
        if self._ro or self._tr:
            try:
                with self._lock:
                    mt5.shutdown()
            finally:
                self._ro = self._tr = False
                self.transition(MT5State.DISCONNECTED)

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
            # Phase 8 fix:加大 join timeout 到 6s 不 2s,避免 vs terminal_info 互锁
            self._heartbeat_thread.join(timeout=6)

    def _heartbeat_loop(self):
        delay = self._base_s
        while not self._heartbeat_stop.is_set():
            if self._heartbeat_stop.wait(self._hb_s):
                break
            alive = False
            if self._ro:
                try:
                    with self._lock:
                        info = mt5.terminal_info()
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

    def copy_rates(self, symbol, timeframe, count=200):
        if not self._ro and not self.init_readonly():
            return None
        tf_map = {
            "M5": mt5.TIMEFRAME_M5,
            "M15": mt5.TIMEFRAME_M15,
            "H1": mt5.TIMEFRAME_H1,
            "H4": mt5.TIMEFRAME_H4,
            "D1": mt5.TIMEFRAME_D1,
        }
        tf = tf_map.get(timeframe)
        if tf is None:
            return None
        try:
            with self._lock:
                rates = mt5.copy_rates_from_pos(symbol, tf, 0, count)
            if rates is None or len(rates) == 0:
                return None
            df = pd.DataFrame(rates)
            df["time"] = pd.to_datetime(df["time"], unit="s")
            return df
        except Exception:
            return None

    def symbol_info(self, symbol):
        if not self._ro and not self.init_readonly():
            return None
        try:
            with self._lock:
                info = mt5.symbol_info(symbol)
            if info is None:
                return None
            return {
                "symbol": info.name, "point": info.point, "digits": info.digits,
                "spread": info.spread, "volume_min": info.volume_min,
                "volume_max": info.volume_max, "volume_step": info.volume_step,
                "trade_contract_size": info.trade_contract_size,
                "trade_mode": info.trade_mode,
            }
        except Exception:
            return None

    def account_info(self):
        if not self._ro and not self.init_readonly():
            return None
        try:
            with self._lock:
                info = mt5.account_info()
            if info is None:
                return None
            return {
                "login": info.login, "balance": info.balance, "equity": info.equity,
                "margin": info.margin, "free_margin": info.free_margin,
                "leverage": info.leverage, "server": info.server,
            }
        except Exception:
            return None

    def heartbeat_ping(self):
        if not self._ro:
            return False
        try:
            with self._lock:
                info = mt5.terminal_info()
            return bool(info and getattr(info, "connected", False))
        except Exception:
            return False

    def order_send(self, symbol, order_type, lots, sl=0.0, tp=0.0, comment=""):
        if not self._tr:
            return None
        try:
            with self._lock:
                tick = mt5.symbol_info_tick(symbol)
            if tick is None:
                return None
            if order_type.upper() == "BUY":
                mt5_type, price = mt5.ORDER_TYPE_BUY, tick.ask
            else:
                mt5_type, price = mt5.ORDER_TYPE_SELL, tick.bid
            req = {
                "action": mt5.TRADE_ACTION_DEAL, "symbol": symbol, "volume": lots,
                "type": mt5_type, "price": price, "sl": sl, "tp": tp,
                "deviation": 20, "magic": 20260617, "comment": comment,
                "type_time": mt5.ORDER_TIME_GTC, "type_filling": mt5.ORDER_FILLING_IOC,
            }
            with self._lock:
                result = mt5.order_send(req)
            if result is None:
                return None
            if result.retcode != mt5.TRADE_RETCODE_DONE:
                return {"ok": False, "retcode": result.retcode, "comment": result.comment}
            return {"ok": True, "ticket": result.order, "price": price, "lots": lots}
        except Exception:
            return None

    def positions_get(self, symbol=None):
        if not self._ro and not self.init_readonly():
            return []
        try:
            with self._lock:
                pos = mt5.positions_get(symbol=symbol) if symbol else mt5.positions_get()
            if pos is None:
                return []
            result = []
            for p in pos:
                with self._lock:
                    si = mt5.symbol_info(p.symbol)
                cs = si.trade_contract_size if si else 100
                pp = (p.profit / (p.volume * cs)) * 100 if cs > 0 else 0
                result.append({
                    "ticket": p.ticket, "symbol": p.symbol,
                    "type": "BUY" if p.type == 0 else "SELL",
                    "lots": p.volume, "entry": p.price_open, "current": p.price_current,
                    "sl": p.sl, "tp": p.tp, "pnl": p.profit, "pnl_pct": round(pp, 2),
                    "open_time": datetime.fromtimestamp(
                        p.time, tz=timezone(timedelta(hours=8))
                    ).isoformat(),
                })
            return result
        except Exception:
            return []

    def close_position(self, ticket):
        if not self._tr:
            return None
        try:
            with self._lock:
                pl = mt5.positions_get(ticket=ticket)
            if not pl:
                return None
            pos = pl[0]
            with self._lock:
                tick = mt5.symbol_info_tick(pos.symbol)
            if tick is None:
                return None
            if pos.type == 0:
                ct, price = mt5.ORDER_TYPE_SELL, tick.bid
            else:
                ct, price = mt5.ORDER_TYPE_BUY, tick.ask
            req = {
                "action": mt5.TRADE_ACTION_DEAL, "symbol": pos.symbol,
                "volume": pos.volume, "type": ct, "position": ticket,
                "price": price, "deviation": 20, "magic": 20260617,
                "comment": "close",
                "type_time": mt5.ORDER_TIME_GTC, "type_filling": mt5.ORDER_FILLING_IOC,
            }
            with self._lock:
                result = mt5.order_send(req)
            if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
                return {
                    "ok": False,
                    "error": str(result.comment if result else mt5.last_error()),
                }
            return {"ok": True, "pnl": pos.profit}
        except Exception:
            return None


bridge = MT5Bridge()
