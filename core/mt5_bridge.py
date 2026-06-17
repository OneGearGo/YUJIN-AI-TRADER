"""
MT5 桥接模块 -- MetaTrader5 Python SDK 封装
铁律: 扫描用只读 init(不传凭据), 买入触发单独 init(传凭据), 下完立刻 shutdown()
"""
import os
import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List
import logging

logger = logging.getLogger(__name__)

TIMEFRAME_MAP = {
    "M5": mt5.TIMEFRAME_M5, "M15": mt5.TIMEFRAME_M15,
    "H1": mt5.TIMEFRAME_H1, "H4": mt5.TIMEFRAME_H4, "D1": mt5.TIMEFRAME_D1,
}


class MT5Bridge:
    """MT5 连接管理 -- 只读扫描 + 独立下单链路"""

    def __init__(self):
        self._ro = False
        self._tr = False

    @property
    def is_connected(self) -> bool:
        """公开属性: MT5 只读连接是否就绪"""
        return self._ro

    def init_readonly(self, path=None) -> bool:
        """只读初始化 -- 扫描行情用, 不传 login/password, 不会踢出 GUI"""
        if self._ro:
            return True
        p = path or os.getenv("MT5_PATH")
        kw = {"path": p} if p else {}
        if not mt5.initialize(**kw):
            logger.error("MT5 只读 init 失败: %s", mt5.last_error())
            return False
        self._ro = True
        info = mt5.terminal_info()
        logger.info("MT5 只读连接: %s", info.name if info else "unknown")
        return True

    def init_for_trade(self, login: int, password: str, server: str) -> bool:
        """下单专用初始化 -- 带凭据, 下完必须 shutdown()"""
        if self._tr:
            return True
        p = os.getenv("MT5_PATH")
        kw = {"login": login, "password": password, "server": server}
        if p:
            kw["path"] = p
        if not mt5.initialize(**kw):
            logger.error("MT5 下单 init 失败: %s", mt5.last_error())
            return False
        self._tr = True
        logger.info("MT5 下单连接: login=%d", login)
        return True

    def shutdown_trade(self):
        """关闭下单连接 -- 下完单必须调用"""
        if self._tr:
            mt5.shutdown()
            self._tr = False

    def copy_rates(self, symbol: str, timeframe: str, count: int = 200) -> Optional[pd.DataFrame]:
        """拉取 K 线数据"""
        if not self._ro and not self.init_readonly():
            return None
        tf = TIMEFRAME_MAP.get(timeframe)
        if tf is None:
            return None
        rates = mt5.copy_rates_from_pos(symbol, tf, 0, count)
        if rates is None or len(rates) == 0:
            return None
        df = pd.DataFrame(rates)
        df["time"] = pd.to_datetime(df["time"], unit="s")
        return df

    def symbol_info(self, symbol: str) -> Optional[Dict[str, Any]]:
        """获取品种信息"""
        if not self._ro and not self.init_readonly():
            return None
        info = mt5.symbol_info(symbol)
        if info is None:
            return None
        return {
            "symbol": info.name, "point": info.point, "digits": info.digits,
            "spread": info.spread, "volume_min": info.volume_min,
            "volume_max": info.volume_max, "volume_step": info.volume_step,
            "trade_contract_size": info.trade_contract_size, "trade_mode": info.trade_mode,
        }

    def account_info(self) -> Optional[Dict[str, Any]]:
        """获取账户信息"""
        if not self._ro and not self.init_readonly():
            return None
        info = mt5.account_info()
        if info is None:
            return None
        return {
            "login": info.login, "balance": info.balance, "equity": info.equity,
            "margin": info.margin, "free_margin": info.free_margin,
            "leverage": info.leverage, "server": info.server,
        }

    def order_send(self, symbol, order_type, lots, sl=0.0, tp=0.0, comment="") -> Optional[Dict]:
        """发送订单"""
        if not self._tr:
            return None
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
        result = mt5.order_send(req)
        if result is None:
            return None
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            return {"ok": False, "retcode": result.retcode, "comment": result.comment}
        return {"ok": True, "ticket": result.order, "price": price, "lots": lots}

    def positions_get(self, symbol=None) -> List[Dict[str, Any]]:
        """获取当前持仓"""
        if not self._ro and not self.init_readonly():
            return []
        pos = mt5.positions_get(symbol=symbol) if symbol else mt5.positions_get()
        if pos is None:
            return []
        result = []
        for p in pos:
            si = mt5.symbol_info(p.symbol)
            cs = si.trade_contract_size if si else 100
            pp = (p.profit / (p.volume * cs)) * 100 if cs > 0 else 0
            result.append({
                "ticket": p.ticket, "symbol": p.symbol,
                "type": "BUY" if p.type == 0 else "SELL",
                "lots": p.volume, "entry": p.price_open, "current": p.price_current,
                "sl": p.sl, "tp": p.tp, "pnl": p.profit, "pnl_pct": round(pp, 2),
                "open_time": datetime.fromtimestamp(p.time, tz=timezone(timedelta(hours=8))).isoformat(),
            })
        return result

    def close_position(self, ticket: int) -> Optional[Dict]:
        """平仓"""
        if not self._tr:
            return None
        pl = mt5.positions_get(ticket=ticket)
        if not pl:
            return None
        pos = pl[0]
        tick = mt5.symbol_info_tick(pos.symbol)
        if tick is None:
            return None
        if pos.type == 0:
            ct, price = mt5.ORDER_TYPE_SELL, tick.bid
        else:
            ct, price = mt5.ORDER_TYPE_BUY, tick.ask
        req = {
            "action": mt5.TRADE_ACTION_DEAL, "symbol": pos.symbol, "volume": pos.volume,
            "type": ct, "position": ticket, "price": price, "deviation": 20,
            "magic": 20260617, "comment": "close",
            "type_time": mt5.ORDER_TIME_GTC, "type_filling": mt5.ORDER_FILLING_IOC,
        }
        result = mt5.order_send(req)
        if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
            return {"ok": False, "error": str(result.comment if result else mt5.last_error())}
        return {"ok": True, "pnl": pos.profit}


bridge = MT5Bridge()
