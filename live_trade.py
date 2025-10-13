# #!/usr/bin/env python3
# # -*- coding: utf-8 -*-
#
# import argparse
# import os
# import time
# import datetime as dt
# from typing import List, Tuple, Optional
#
# # ---- Matplotlib backend ----
# import matplotlib
# try:
#     matplotlib.use("MacOSX")
# except Exception:
#     matplotlib.use("TkAgg")
# from matplotlib import pyplot as plt
#
# import numpy as np
# import pandas as pd
# from dotenv import load_dotenv
#
# # Alpaca SDK
# from alpaca.trading.client import TradingClient
# from alpaca.trading.requests import MarketOrderRequest, LimitOrderRequest
# from alpaca.trading.enums import OrderSide, TimeInForce
# from alpaca.data.historical import StockHistoricalDataClient
# from alpaca.data.requests import StockBarsRequest
# from alpaca.data.timeframe import TimeFrame
# from alpaca.data.enums import DataFeed
#
# # Strategy engines
# from strategy import SMACrossEngine, Decision
# try:
#     from strategy import VWAPEngine   # 如果你有就会使用
# except Exception:
#     VWAPEngine = None                 # 否则用轻量兜底
#
# # ---- mplfinance (optional) ----
# try:
#     import mplfinance as mpf
# except Exception:
#     mpf = None
#
# # 旧方案：每帧重画但先关闭上一张，稳定不挑版本
# _LAST_FIG = None
#
#
# # ----------------- Utilities -----------------
# def is_market_open_now(trading: TradingClient) -> bool:
#     try:
#         clk = trading.get_clock()
#         return bool(getattr(clk, "is_open", False))
#     except Exception:
#         return False
#
#
# def normalize_bars_df(df: pd.DataFrame, symbol: Optional[str] = None) -> pd.DataFrame:
#     """Normalize alpaca bars df to single-symbol OHLCV with naive tz index."""
#     if df is None or df.empty:
#         return pd.DataFrame()
#     if isinstance(df.index, pd.MultiIndex):
#         if not symbol:
#             raise ValueError("normalize_bars_df: MultiIndex needs symbol")
#         df = df.xs(symbol, level="symbol")
#     df = df.copy()
#     df.columns = [str(c).lower() for c in df.columns]
#     if isinstance(df.index, pd.DatetimeIndex) and df.index.tz is not None:
#         df.index = df.index.tz_convert(None)
#     cols = [c for c in ["open", "high", "low", "close", "volume"] if c in df.columns]
#     return df[cols]
#
#
# def get_bars(client, symbol: str, start: dt.datetime, end: dt.datetime, limit: int) -> pd.DataFrame:
#     # ✅ 固定 IEX feed
#     req = StockBarsRequest(
#         symbol_or_symbols=symbol,
#         timeframe=TimeFrame.Minute,
#         start=start,
#         end=end,
#         limit=limit,
#         adjustment="raw",
#         feed=DataFeed.IEX,
#     )
#     bars = client.get_stock_bars(req).df
#     return normalize_bars_df(bars, symbol=symbol)
#
#
# def get_last_complete_session(client, symbol: str, days_back: int = 3) -> pd.DataFrame:
#     """
#     抓最近几天里“最完整”的一个交易日分钟线（收盘后回放用）。
#     """
#     end = dt.datetime.utcnow()
#     start = end - dt.timedelta(days=days_back)
#     all_df = get_bars(client, symbol, start, end, 10000)
#     if all_df.empty:
#         return all_df
#     by_day = {day: g for day, g in all_df.groupby(all_df.index.normalize())}
#     if not by_day:
#         return pd.DataFrame()
#     best_day = max(by_day.items(), key=lambda kv: len(kv[1]))[0]
#     return by_day[best_day]
#
#
# # ----------------- Plotting (稳定版，每帧重画但关闭上一张) -----------------
# def plot_intraday(df: pd.DataFrame,
#                   symbol: str,
#                   overlays: List[pd.Series],
#                   buys: List[Tuple[pd.Timestamp, float]],
#                   sells: List[Tuple[pd.Timestamp, float]],
#                   title: str = "",
#                   window: int = 200):
#     global _LAST_FIG
#     if mpf is None or df is None or df.empty:
#         return
#
#     # 清洗 + 取窗口
#     d = df.copy()
#     d.columns = [str(c).lower() for c in d.columns]
#     need = ["open", "high", "low", "close"]
#     if any(c not in d.columns for c in need):
#         return
#     cols = need + (["volume"] if "volume" in d.columns else [])
#     d = d[cols].iloc[-window:]
#     if not d.index.is_monotonic_increasing:
#         d = d.sort_index()
#     d = d[~d.index.duplicated(keep="last")].dropna(subset=need)
#     if len(d) < 2:
#         return
#
#     # 叠加：严格对齐主索引；至少 2 个有效点才加入
#     # 叠加：与主索引对齐；不要 dropna（否则长度变短会和主图 x 维不一致）
#     apds = []
#     for s in overlays or []:
#         if s is None:
#             continue
#         rs_full = s.reindex(d.index).astype(float)          # 与主索引等长，允许 NaN
#         if rs_full.dropna().shape[0] >= 2:                  # 仅用于判断是否有足够有效点
#             apds.append(mpf.make_addplot(rs_full, width=1.2))
#
#
#     # 买卖标记：构造与主索引等长的稀疏序列（避免 x/y 维度不一致）
#     if buys:
#         bser = pd.Series(index=d.index, dtype=float)
#         for ts, px in buys:
#             if ts in bser.index:
#                 bser.loc[ts] = px
#         if bser.dropna().shape[0] > 0:
#             apds.append(mpf.make_addplot(bser, type="scatter", marker="^", markersize=40))
#     if sells:
#         sser = pd.Series(index=d.index, dtype=float)
#         for ts, px in sells:
#             if ts in sser.index:
#                 sser.loc[ts] = px
#         if sser.dropna().shape[0] > 0:
#             apds.append(mpf.make_addplot(sser, type="scatter", marker="v", markersize=40))
#
#     # 关闭上一张，防止 20+ figures 告警
#     try:
#         if _LAST_FIG is not None:
#             plt.close(_LAST_FIG)
#             _LAST_FIG = None
#     except Exception:
#         pass
#
#     # 绘制（不传 ax/volume 句柄，完全交给 mplfinance 管理，避免 suptitle/ax 类型坑）
#     try:
#         fig, _ = mpf.plot(
#             d.rename(columns={"open":"Open","high":"High","low":"Low","close":"Close","volume":"Volume"}),
#             type="candle",
#             volume=("volume" in d.columns),        # ✅ 只传 True/False
#             addplot=(apds if apds else None),      # 没有叠加就传 None
#             style="yahoo",
#             title=(title or symbol),
#             tight_layout=True,
#             block=False,
#             returnfig=True
#         )
#         _LAST_FIG = fig
#         plt.pause(0.001)
#     except Exception as e:
#         print("Plot error:", e)
#
#
# # ----------------- Strategy factory -----------------
# def make_engine(args):
#     if args.strategy == "sma":
#         return SMACrossEngine(
#             fast=args.fast, slow=args.slow,
#             hysteresis=args.hysteresis,
#             cooldown_bars=args.cooldown,
#             confirm_bars=args.confirm,
#         )
#
#     # -------- VWAP ----------
#     if args.strategy == "vwap":
#         # 如果 strategy.py 里有 VWAPEngine，尝试多套构造签名
#         if VWAPEngine is not None:
#             attempts = [
#                 {"window": args.vwap_window, "mult": args.vwap_mult},
#                 {"period": args.vwap_window, "mult": args.vwap_mult},
#                 {"period": args.vwap_window, "threshold": args.vwap_mult},
#                 {"length": args.vwap_window, "mult": args.vwap_mult},
#                 {"length": args.vwap_window, "k": args.vwap_mult},
#                 {"lookback": args.vwap_window, "mult": args.vwap_mult},
#                 {"lookback": args.vwap_window, "threshold": args.vwap_mult},
#             ]
#             # 先尝试带名字参数
#             for kw in attempts:
#                 try:
#                     return VWAPEngine(**kw)
#                 except TypeError:
#                     pass
#             # 再试位置参数 (window, mult)
#             try:
#                 return VWAPEngine(args.vwap_window, args.vwap_mult)
#             except TypeError:
#                 pass
#             # 最后试不带参数（用引擎默认）
#             try:
#                 return VWAPEngine()
#             except Exception:
#                 pass
#
#         # 兜底：轻量 VWAP（rolling vwap ± k*std）
#         class _VWAPLite:
#             def __init__(self, window=20, mult=2.0):
#                 self.window = window
#                 self.mult = mult
#                 self.prices = []
#                 self.vols = []
#                 self.vwap = None
#                 self.upper = None
#                 self.lower = None
#             def on_bar_close(self, close: float, volume: float = 1.0):
#                 self.prices.append(close)
#                 self.vols.append(volume)
#                 if len(self.prices) > self.window:
#                     self.prices = self.prices[-self.window:]
#                     self.vols = self.vols[-self.window:]
#                 v = np.array(self.vols); p = np.array(self.prices)
#                 v_sum = float(v.sum()) if v.size else 0.0
#                 self.vwap = float((p * v).sum() / v_sum) if v_sum > 0 else float(np.mean(p))
#                 std = float(p.std()) if len(p) >= 2 else 0.0
#                 self.upper = self.vwap + self.mult * std
#                 self.lower = self.vwap - self.mult * std
#                 action, reason = "HOLD", "within band"
#                 if close > self.upper: action, reason = "SELL", "price>upper"
#                 elif close < self.lower: action, reason = "BUY", "price<lower"
#                 # 复用字段用于日志/绘图，无实义
#                 return Decision(action=action, reason=reason,
#                                 sma_fast=self.vwap, sma_slow=self.upper)
#         return _VWAPLite(window=args.vwap_window, mult=args.vwap_mult)
#
#     raise ValueError(f"Unknown strategy {args.strategy}")
#
#
# def overlays_for_plot(args, bars: pd.DataFrame, engine) -> List[pd.Series]:
#     if args.strategy == "sma":
#         s1 = bars["close"].rolling(args.fast).mean().rename(f"SMA{args.fast}")
#         s2 = bars["close"].rolling(args.slow).mean().rename(f"SMA{args.slow}")
#         return [s1, s2]
#     elif args.strategy == "vwap":
#         w = max(1, args.vwap_window)
#         vol_sum = bars["volume"].rolling(w).sum()
#         pv_sum  = (bars["close"] * bars["volume"]).rolling(w).sum()
#         vwap = (pv_sum / vol_sum).where(vol_sum > 0)
#         return [vwap.rename(f"VWAP({w})")]
#     return []
#
#
# # ----------------- Order helpers -----------------
# def submit_buy(trading: TradingClient, symbol: str, qty: int,
#                tif: TimeInForce = TimeInForce.DAY,
#                limit_price: Optional[float] = None,
#                extended: bool = False):
#     if qty <= 0: return
#     if limit_price is None:
#         trading.submit_order(MarketOrderRequest(symbol=symbol, qty=qty, side=OrderSide.BUY, time_in_force=tif))
#     else:
#         trading.submit_order(LimitOrderRequest(symbol=symbol, qty=qty, side=OrderSide.BUY,
#                                               time_in_force=tif, limit_price=limit_price, extended_hours=extended))
#
#
# def submit_sell(trading: TradingClient, symbol: str, qty: int,
#                 tif: TimeInForce = TimeInForce.DAY,
#                 limit_price: Optional[float] = None,
#                 extended: bool = False):
#     if qty <= 0: return
#     if limit_price is None:
#         trading.submit_order(MarketOrderRequest(symbol=symbol, qty=qty, side=OrderSide.SELL, time_in_force=tif))
#     else:
#         trading.submit_order(LimitOrderRequest(symbol=symbol, qty=qty, side=OrderSide.SELL,
#                                               time_in_force=tif, limit_price=limit_price, extended_hours=extended))
#
#
# # ----------------- SIM: market close 回放（可选下单） -----------------
# def run_simulated_session(args, trading: TradingClient, data_client: StockHistoricalDataClient, symbol: str):
#     day_df = get_last_complete_session(data_client, symbol, days_back=3)
#     if day_df is None or day_df.empty:
#         print("No recent complete session found.")
#         return
#
#     engine = make_engine(args)
#     buy_marks: List[Tuple[pd.Timestamp, float]] = []
#     sell_marks: List[Tuple[pd.Timestamp, float]] = []
#
#     overlays = overlays_for_plot(args, day_df, engine)
#
#     pos_qty = 0
#     title = f"{symbol} (SIM {args.strategy.upper()} {'+API' if args.sim_place_orders else ''})"
#     for ts, row in day_df.iterrows():
#         close = float(row["close"])
#         volume = float(row.get("volume", 0.0))
#         try:
#             d: Decision = engine.on_bar_close(close) if args.strategy == "sma" else engine.on_bar_close(close, volume)
#         except TypeError:
#             d: Decision = engine.on_bar_close(close)
#
#         if args.verbose:
#             print(f"[SIM {ts}] close={close:.2f} action={d.action} reason={d.reason} pos={pos_qty}")
#
#         if d.action == "BUY" and pos_qty <= 0:
#             if args.sim_place_orders:
#                 # ✅ 即使收盘，DAY 市场单也会排队到下一个常规交易时段
#                 if args.limit_on_sim is not None:
#                     submit_buy(trading, symbol, args.sim_qty, tif=TimeInForce.DAY,
#                                limit_price=round(close * (1 + args.limit_on_sim), 2),
#                                extended=args.extended)
#                 else:
#                     submit_buy(trading, symbol, args.sim_qty, tif=TimeInForce.DAY)
#             pos_qty = args.sim_qty
#             buy_marks.append((pd.Timestamp(ts), close))
#
#         elif d.action == "SELL" and pos_qty > 0:
#             if args.sim_place_orders:
#                 if args.limit_on_sim is not None:
#                     submit_sell(trading, symbol, pos_qty, tif=TimeInForce.DAY,
#                                 limit_price=round(close * (1 - args.limit_on_sim), 2),
#                                 extended=args.extended)
#                 else:
#                     submit_sell(trading, symbol, pos_qty, tif=TimeInForce.DAY)
#             sell_marks.append((pd.Timestamp(ts), close))
#             pos_qty = 0
#
#         if args.live_plot:
#             sub = day_df.loc[:ts]
#             n = sub.shape[0]
#             if n >= max(2, getattr(args, "plot_warmup", 40)) and (n % max(1, args.plot_every) == 0):
#                 plot_intraday(sub, symbol, overlays, buy_marks, sell_marks,
#                               title=title, window=args.plot_window)
#
#         time.sleep(args.sim_speed)
#
#     print("Simulation finished.")
#
#
# # ----------------- Live: 开市实时 -----------------
# def run_live_stream(args, trading: TradingClient, data_client: StockHistoricalDataClient, symbol: str):
#     engine = make_engine(args)
#     buy_marks: List[Tuple[pd.Timestamp, float]] = []
#     sell_marks: List[Tuple[pd.Timestamp, float]] = []
#
#     last_bar_time = None
#     while True:
#         try:
#             end = dt.datetime.utcnow()
#             start = end - dt.timedelta(hours=2)
#             bars = get_bars(data_client, symbol, start, end, 500)
#             if bars is None or bars.empty:
#                 time.sleep(5)
#                 continue
#
#             last = bars.iloc[-1]
#             bar_time, bar_close = last.name, float(last["close"])
#             volume = float(last.get("volume", 0.0))
#
#             if last_bar_time is None or bar_time > last_bar_time:
#                 last_bar_time = bar_time
#                 try:
#                     d: Decision = engine.on_bar_close(bar_close) if args.strategy == "sma" else engine.on_bar_close(bar_close, volume)
#                 except TypeError:
#                     d: Decision = engine.on_bar_close(bar_close)
#
#                 # 当前持仓
#                 pos_qty = 0
#                 try:
#                     for p in trading.get_all_positions() or []:
#                         if p.symbol == symbol:
#                             pos_qty = int(float(p.qty))
#                             break
#                 except Exception:
#                     pass
#
#                 if args.verbose:
#                     extras = []
#                     if getattr(d, "sma_fast", None) is not None: extras.append(f"f={d.sma_fast:.4f}")
#                     if getattr(d, "sma_slow", None) is not None: extras.append(f"s={d.sma_slow:.4f}")
#                     print(f"[{bar_time}] close={bar_close:.2f} {' '.join(extras)} action={d.action} reason={d.reason} pos={pos_qty}")
#
#                 if d.action == "BUY" and pos_qty <= 0:
#                     acct = trading.get_account()
#                     buying_power = float(acct.buying_power)
#                     qty = int((buying_power * args.cash_pct) // bar_close)
#                     qty = min(qty, args.max_shares)
#                     if qty > 0:
#                         submit_buy(trading, symbol, qty, tif=TimeInForce.DAY)
#                         buy_marks.append((pd.Timestamp(bar_time), bar_close))
#                         print(f"BUY {qty} {symbol} @~{bar_close:.2f}")
#
#                 elif d.action == "SELL" and pos_qty > 0:
#                     submit_sell(trading, symbol, pos_qty, tif=TimeInForce.DAY)
#                     sell_marks.append((pd.Timestamp(bar_time), bar_close))
#                     print(f"SELL {pos_qty} {symbol} @~{bar_close:.2f}")
#
#                 if args.live_plot:
#                     overlays = overlays_for_plot(args, bars, engine)
#                     plot_intraday(bars, symbol, overlays, buy_marks, sell_marks,
#                                   title=f"{symbol} (LIVE {args.strategy.upper()})", window=args.plot_window)
#
#             time.sleep(5)
#         except Exception as e:
#             print("ERROR:", e)
#             time.sleep(5)
#
#
# def main():
#     load_dotenv()
#
#     parser = argparse.ArgumentParser(description="Live/Sim trading (Alpaca paper, IEX only)")
#     parser.add_argument("--symbol", type=str, default=os.getenv("SYMBOL", "AAPL"))
#     parser.add_argument("--strategy", type=str, default=os.getenv("STRATEGY", "sma"),
#                         choices=["sma", "vwap"])
#
#     # SMA params
#     parser.add_argument("--fast", type=int, default=int(os.getenv("FAST", "10")))
#     parser.add_argument("--slow", type=int, default=int(os.getenv("SLOW", "50")))
#     parser.add_argument("--hysteresis", type=float, default=float(os.getenv("HYSTERESIS", "0.002")))
#     parser.add_argument("--cooldown", type=int, default=int(os.getenv("COOLDOWN_BARS", "3")))
#     parser.add_argument("--confirm", type=int, default=int(os.getenv("CONFIRM_BARS", "1")))
#
#     # VWAP params
#     parser.add_argument("--vwap-window", type=int, default=int(os.getenv("VWAP_WINDOW", "20")))
#     parser.add_argument("--vwap-mult", type=float, default=float(os.getenv("VWAP_MULT", "2.0")))
#
#     # Trading / risk
#     parser.add_argument("--cash_pct", type=float, default=float(os.getenv("CASH_PCT", "0.95")))
#     parser.add_argument("--max-shares", type=int, default=int(os.getenv("MAX_SHARES", "500")))
#
#     # Mode
#     parser.add_argument("--mode", type=str, default=os.getenv("MODE", "auto"),
#                         choices=["auto", "live", "sim"],
#                         help="auto: 市场开=live, 收盘=sim；sim: 仅回放；live: 只实时")
#
#     # SIM options (回放时可选真实下单)
#     parser.add_argument("--sim-place-orders", action="store_true",
#                         help="在 SIM 回放中也通过 Alpaca 下单（收盘时订单会排队到下个交易时段）")
#     parser.add_argument("--sim-qty", type=int, default=int(os.getenv("SIM_QTY", "1")))
#     parser.add_argument("--sim-speed", type=float, default=float(os.getenv("SIM_SPEED", "0.02")),
#                         help="模拟每根bar推进的 sleep 秒数")
#     parser.add_argument("--limit-on-sim", type=float, default=None,
#                         help="SIM 下单时使用限价的百分比偏移（例如 0.002 表示±0.2%），默认 None 用市价")
#     parser.add_argument("--extended", action="store_true",
#                         help="限价单是否允许 extended hours（注意收盘完全关闭时仍会排到下一个交易时段）")
#
#     # Optional plotting
#     parser.add_argument("--live-plot", action="store_true")
#     parser.add_argument("--plot-window", type=int, default=200)
#     parser.add_argument("--plot-every", type=int, default=3,
#                         help="每隔多少根bar绘一次图，降低开销与闪烁")
#     parser.add_argument("--plot-warmup", type=int, default=40,
#                         help="至少积累多少根bar后再开始画图，避免rolling初期全NaN")
#
#     # Force orders (立即手动一笔)
#     parser.add_argument("--force-buy", type=int, help="强制买入指定股数（立即下单）")
#     parser.add_argument("--force-sell", type=int, help="强制卖出指定股数（立即下单）")
#
#     parser.add_argument("--verbose", action="store_true")
#     args = parser.parse_args()
#
#     API_KEY = os.getenv("ALPACA_API_KEY")
#     API_SECRET = os.getenv("ALPACA_SECRET_KEY") or os.getenv("ALPACA_API_SECRET")
#     USE_PAPER = os.getenv("ALPACA_USE_PAPER", "true").lower() == "true"
#     if not API_KEY or not API_SECRET:
#         raise RuntimeError("Missing ALPACA_API_KEY / ALPACA_SECRET_KEY")
#
#     symbol = args.symbol.upper()
#
#     trading = TradingClient(API_KEY, API_SECRET, paper=USE_PAPER)
#     data_client = StockHistoricalDataClient(API_KEY, API_SECRET)
#
#     # 手动强制单（随时一股/多股）
#     if args.force_buy or args.force_sell:
#         if args.force_buy:
#             submit_buy(trading, symbol, args.force_buy, tif=TimeInForce.DAY)
#             print(f"[FORCE BUY] {args.force_buy} {symbol}")
#         if args.force_sell:
#             submit_sell(trading, symbol, args.force_sell, tif=TimeInForce.DAY)
#             print(f"[FORCE SELL] {args.force_sell} {symbol}")
#         return
#
#     market_open = is_market_open_now(trading)
#
#     if args.mode == "live":
#         if not market_open:
#             print("Market is closed; --mode=live 无法实时。可用 --mode=sim + --sim-place-orders 做回放下单。")
#             return
#         run_live_stream(args, trading, data_client, symbol)
#         return
#
#     if args.mode == "sim":
#         run_simulated_session(args, trading, data_client, symbol)
#         return
#
#     # auto
#     print(f"Mode=auto | market_open={market_open}")
#     if market_open:
#         run_live_stream(args, trading, data_client, symbol)
#     else:
#         run_simulated_session(args, trading, data_client, symbol)
#
#
# if __name__ == "__main__":
#     main()

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import os
import time
import datetime as dt
from typing import List, Tuple, Optional

# ---- Matplotlib backend ----
import matplotlib
try:
    matplotlib.use("MacOSX")
except Exception:
    matplotlib.use("TkAgg")
from matplotlib import pyplot as plt

import numpy as np
import pandas as pd
from dotenv import load_dotenv

# Alpaca SDK
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest, LimitOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame
from alpaca.data.enums import DataFeed

# Strategy engines
from strategy import SMACrossEngine, Decision
try:
    from strategy import VWAPEngine   # 如果你有就会使用
except Exception:
    VWAPEngine = None                 # 否则用轻量兜底

# ---- mplfinance (optional) ----
try:
    import mplfinance as mpf
except Exception:
    mpf = None

# 每帧重画前关闭上一张，稳定不挑版本
_LAST_FIG = None


# ----------------- Utilities -----------------
def is_market_open_now(trading: TradingClient) -> bool:
    try:
        clk = trading.get_clock()
        return bool(getattr(clk, "is_open", False))
    except Exception:
        return False


def normalize_bars_df(df: pd.DataFrame, symbol: Optional[str] = None) -> pd.DataFrame:
    """Normalize alpaca bars df to single-symbol OHLCV with naive tz index."""
    if df is None or df.empty:
        return pd.DataFrame()
    if isinstance(df.index, pd.MultiIndex):
        if not symbol:
            raise ValueError("normalize_bars_df: MultiIndex needs symbol")
        df = df.xs(symbol, level="symbol")
    df = df.copy()
    df.columns = [str(c).lower() for c in df.columns]
    if isinstance(df.index, pd.DatetimeIndex) and df.index.tz is not None:
        df.index = df.index.tz_convert(None)
    cols = [c for c in ["open", "high", "low", "close", "volume"] if c in df.columns]
    return df[cols]


def get_bars(client, symbol: str, start: dt.datetime, end: dt.datetime, limit: int) -> pd.DataFrame:
    # ✅ 固定 IEX feed
    req = StockBarsRequest(
        symbol_or_symbols=symbol,
        timeframe=TimeFrame.Minute,
        start=start,
        end=end,
        limit=limit,
        adjustment="raw",
        feed=DataFeed.IEX,
    )
    bars = client.get_stock_bars(req).df
    return normalize_bars_df(bars, symbol=symbol)


def get_last_complete_session(client, symbol: str, days_back: int = 3) -> pd.DataFrame:
    """
    抓最近几天里“最完整”的一个交易日分钟线（收盘后回放用）。
    """
    end = dt.datetime.utcnow()
    start = end - dt.timedelta(days=days_back)
    all_df = get_bars(client, symbol, start, end, 10000)
    if all_df.empty:
        return all_df
    by_day = {day: g for day, g in all_df.groupby(all_df.index.normalize())}
    if not by_day:
        return pd.DataFrame()
    best_day = max(by_day.items(), key=lambda kv: len(kv[1]))[0]
    return by_day[best_day]


# ----------------- Plotting (稳定版：每帧重画但关闭上一张) -----------------
def plot_intraday(df: pd.DataFrame,
                  symbol: str,
                  overlays: List[pd.Series],
                  buys: List[Tuple[pd.Timestamp, float]],
                  sells: List[Tuple[pd.Timestamp, float]],
                  title: str = "",
                  window: int = 200):
    global _LAST_FIG
    if mpf is None or df is None or df.empty:
        return

    # 清洗 + 取窗口
    d = df.copy()
    d.columns = [str(c).lower() for c in d.columns]
    need = ["open", "high", "low", "close"]
    if any(c not in d.columns for c in need):
        return
    cols = need + (["volume"] if "volume" in d.columns else [])
    d = d[cols].iloc[-window:]
    if not d.index.is_monotonic_increasing:
        d = d.sort_index()
    d = d[~d.index.duplicated(keep="last")].dropna(subset=need)
    if len(d) < 2:
        return

    # 叠加：与主索引对齐（不要 dropna，否则长度变短会和主图 x 维不一致）
    apds = []
    for s in overlays or []:
        if s is None:
            continue
        rs_full = s.reindex(d.index).astype(float)  # 与主索引等长，允许 NaN（断线）
        if rs_full.dropna().shape[0] >= 2:
            apds.append(mpf.make_addplot(rs_full, width=1.2))

    # 买卖标记：构造与主索引等长的稀疏序列（避免 x/y 维度不一致）
    if buys:
        bser = pd.Series(index=d.index, dtype=float)
        for ts, px in buys:
            if ts in bser.index:
                bser.loc[ts] = px
        if bser.dropna().shape[0] > 0:
            apds.append(mpf.make_addplot(bser, type="scatter", marker="^", markersize=40))
    if sells:
        sser = pd.Series(index=d.index, dtype=float)
        for ts, px in sells:
            if ts in sser.index:
                sser.loc[ts] = px
        if sser.dropna().shape[0] > 0:
            apds.append(mpf.make_addplot(sser, type="scatter", marker="v", markersize=40))

    # 关闭上一张，防止 20+ figures 告警
    try:
        if _LAST_FIG is not None:
            plt.close(_LAST_FIG)
            _LAST_FIG = None
    except Exception:
        pass

    # 绘制（不传 ax/volume 句柄，完全交给 mplfinance 管理，避免 suptitle/ax 类型坑）
    try:
        fig, _ = mpf.plot(
            d.rename(columns={"open":"Open","high":"High","low":"Low","close":"Close","volume":"Volume"}),
            type="candle",
            volume=("volume" in d.columns),        # ✅ 只传 True/False
            addplot=(apds if apds else None),      # 没有叠加就传 None
            style="yahoo",
            title=(title or symbol),
            tight_layout=True,
            block=False,
            returnfig=True
        )
        _LAST_FIG = fig
        plt.pause(0.001)
    except Exception as e:
        print("Plot error:", e)


# ----------------- Strategy factory -----------------
def make_engine(args):
    if args.strategy == "sma":
        return SMACrossEngine(
            fast=args.fast, slow=args.slow,
            hysteresis=args.hysteresis,
            cooldown_bars=args.cooldown,
            confirm_bars=args.confirm,
        )

    if args.strategy == "vwap":
        # 如果 strategy.py 里有 VWAPEngine，尝试多套构造签名
        if VWAPEngine is not None:
            attempts = [
                {"window": args.vwap_window, "mult": args.vwap_mult},
                {"period": args.vwap_window, "mult": args.vwap_mult},
                {"period": args.vwap_window, "threshold": args.vwap_mult},
                {"length": args.vwap_window, "mult": args.vwap_mult},
                {"length": args.vwap_window, "k": args.vwap_mult},
                {"lookback": args.vwap_window, "mult": args.vwap_mult},
                {"lookback": args.vwap_window, "threshold": args.vwap_mult},
            ]
            for kw in attempts:
                try:
                    return VWAPEngine(**kw)
                except TypeError:
                    pass
            try:
                return VWAPEngine(args.vwap_window, args.vwap_mult)
            except TypeError:
                pass
            try:
                return VWAPEngine()
            except Exception:
                pass

        # 兜底：轻量 VWAP（rolling vwap ± k*std）
        class _VWAPLite:
            def __init__(self, window=20, mult=2.0):
                self.window = window
                self.mult = mult
                self.prices = []
                self.vols = []
                self.vwap = None
                self.upper = None
                self.lower = None
            def on_bar_close(self, close: float, volume: float = 1.0):
                self.prices.append(close)
                self.vols.append(volume)
                if len(self.prices) > self.window:
                    self.prices = self.prices[-self.window:]
                    self.vols = self.vols[-self.window:]
                v = np.array(self.vols); p = np.array(self.prices)
                v_sum = float(v.sum()) if v.size else 0.0
                self.vwap = float((p * v).sum() / v_sum) if v_sum > 0 else float(np.mean(p))
                std = float(p.std()) if len(p) >= 2 else 0.0
                self.upper = self.vwap + self.mult * std
                self.lower = self.vwap - self.mult * std
                action, reason = "HOLD", "within band"
                if close > self.upper: action, reason = "SELL", "price>upper"
                elif close < self.lower: action, reason = "BUY", "price<lower"
                return Decision(action=action, reason=reason,
                                sma_fast=self.vwap, sma_slow=self.upper)
        return _VWAPLite(window=args.vwap_window, mult=args.vwap_mult)

    raise ValueError(f"Unknown strategy {args.strategy}")


def overlays_for_plot(args, bars: pd.DataFrame, engine) -> List[pd.Series]:
    if args.strategy == "sma":
        s1 = bars["close"].rolling(args.fast).mean().rename(f"SMA{args.fast}")
        s2 = bars["close"].rolling(args.slow).mean().rename(f"SMA{args.slow}")
        return [s1, s2]
    elif args.strategy == "vwap":
        w = max(1, args.vwap_window)
        vol_sum = bars["volume"].rolling(w).sum()
        pv_sum  = (bars["close"] * bars["volume"]).rolling(w).sum()
        vwap = (pv_sum / vol_sum).where(vol_sum > 0)
        return [vwap.rename(f"VWAP({w})")]
    return []


# ----------------- Order helpers -----------------
def submit_buy(trading: TradingClient, symbol: str, qty: int,
               tif: TimeInForce = TimeInForce.DAY,
               limit_price: Optional[float] = None,
               extended: bool = False):
    if qty <= 0: return
    if limit_price is None:
        trading.submit_order(MarketOrderRequest(symbol=symbol, qty=qty, side=OrderSide.BUY, time_in_force=tif))
    else:
        trading.submit_order(LimitOrderRequest(symbol=symbol, qty=qty, side=OrderSide.BUY,
                                              time_in_force=tif, limit_price=limit_price, extended_hours=extended))


def submit_sell(trading: TradingClient, symbol: str, qty: int,
                tif: TimeInForce = TimeInForce.DAY,
                limit_price: Optional[float] = None,
                extended: bool = False):
    if qty <= 0: return
    if limit_price is None:
        trading.submit_order(MarketOrderRequest(symbol=symbol, qty=qty, side=OrderSide.SELL, time_in_force=tif))
    else:
        trading.submit_order(LimitOrderRequest(symbol=symbol, qty=qty, side=OrderSide.SELL,
                                              time_in_force=tif, limit_price=limit_price, extended_hours=extended))


# ----------------- SIM: market close 回放（可选下单） -----------------
def run_simulated_session(args, trading: TradingClient, data_client: StockHistoricalDataClient, symbol: str):
    day_df = get_last_complete_session(data_client, symbol, days_back=3)
    if day_df is None or day_df.empty:
        print("No recent complete session found.")
        return

    engine = make_engine(args)
    buy_marks: List[Tuple[pd.Timestamp, float]] = []
    sell_marks: List[Tuple[pd.Timestamp, float]] = []

    overlays = overlays_for_plot(args, day_df, engine)

    pos_qty = 0
    title = f"{symbol} (SIM {args.strategy.upper()} {'+API' if args.sim_place_orders else ''})"
    for ts, row in day_df.iterrows():
        close = float(row["close"])
        volume = float(row.get("volume", 0.0))
        try:
            d: Decision = engine.on_bar_close(close) if args.strategy == "sma" else engine.on_bar_close(close, volume)
        except TypeError:
            d: Decision = engine.on_bar_close(close)

        # 日志
        if args.verbose:
            print(f"[SIM {ts}] close={close:.2f} action={d.action} reason={d.reason} pos={pos_qty}")

        if d.action == "BUY" and pos_qty <= 0:
            if args.sim_place_orders:
                # 用 sim-qty 下单
                if args.limit_on_sim is not None:
                    submit_buy(trading, symbol, args.sim_qty, tif=TimeInForce.DAY,
                               limit_price=round(close * (1 + args.limit_on_sim), 2),
                               extended=args.extended)
                else:
                    submit_buy(trading, symbol, args.sim_qty, tif=TimeInForce.DAY)
                pos_qty = args.sim_qty
            elif args.signal_place_orders:
                # 没开 sim-place-orders 也可用 signal_* 开单
                qty = max(1, int(args.signal_qty))
                if args.signal_limit_pct is not None:
                    lim = round(close * (1 + float(args.signal_limit_pct)), 2)
                    submit_buy(trading, symbol, qty, tif=TimeInForce.DAY,
                               limit_price=lim, extended=args.signal_extended)
                else:
                    submit_buy(trading, symbol, qty, tif=TimeInForce.DAY)
                pos_qty = qty

            buy_marks.append((pd.Timestamp(ts), close))

        elif d.action == "SELL" and pos_qty > 0:
            if args.sim_place_orders:
                qty = pos_qty
                if args.limit_on_sim is not None:
                    submit_sell(trading, symbol, qty, tif=TimeInForce.DAY,
                                limit_price=round(close * (1 - args.limit_on_sim), 2),
                                extended=args.extended)
                else:
                    submit_sell(trading, symbol, qty, tif=TimeInForce.DAY)
                pos_qty = 0
            elif args.signal_place_orders:
                qty = min(pos_qty, max(1, int(args.signal_qty)))
                if args.signal_limit_pct is not None:
                    lim = round(close * (1 - float(args.signal_limit_pct)), 2)
                    submit_sell(trading, symbol, qty, tif=TimeInForce.DAY,
                                limit_price=lim, extended=args.signal_extended)
                else:
                    submit_sell(trading, symbol, qty, tif=TimeInForce.DAY)
                pos_qty -= qty

            sell_marks.append((pd.Timestamp(ts), close))

        if args.live_plot:
            sub = day_df.loc[:ts]
            n = sub.shape[0]
            if n >= max(2, getattr(args, "plot_warmup", 40)) and (n % max(1, args.plot_every) == 0):
                plot_intraday(sub, symbol, overlays, buy_marks, sell_marks,
                              title=title, window=args.plot_window)

        time.sleep(args.sim_speed)

    print("Simulation finished.")


# ----------------- Live: 开市实时 -----------------
def run_live_stream(args, trading: TradingClient, data_client: StockHistoricalDataClient, symbol: str):
    engine = make_engine(args)
    buy_marks: List[Tuple[pd.Timestamp, float]] = []
    sell_marks: List[Tuple[pd.Timestamp, float]] = []

    last_bar_time = None
    while True:
        try:
            end = dt.datetime.utcnow()
            start = end - dt.timedelta(hours=2)
            bars = get_bars(data_client, symbol, start, end, 500)
            if bars is None or bars.empty:
                time.sleep(5)
                continue

            last = bars.iloc[-1]
            bar_time, bar_close = last.name, float(last["close"])
            volume = float(last.get("volume", 0.0))

            if last_bar_time is None or bar_time > last_bar_time:
                last_bar_time = bar_time
                try:
                    d: Decision = engine.on_bar_close(bar_close) if args.strategy == "sma" else engine.on_bar_close(bar_close, volume)
                except TypeError:
                    d: Decision = engine.on_bar_close(bar_close)

                # 当前持仓
                pos_qty = 0
                try:
                    for p in trading.get_all_positions() or []:
                        if p.symbol == symbol:
                            pos_qty = int(float(p.qty))
                            break
                except Exception:
                    pass

                if args.verbose:
                    extras = []
                    if getattr(d, "sma_fast", None) is not None: extras.append(f"f={d.sma_fast:.4f}")
                    if getattr(d, "sma_slow", None) is not None: extras.append(f"s={d.sma_slow:.4f}")
                    print(f"[{bar_time}] close={bar_close:.2f} {' '.join(extras)} action={d.action} reason={d.reason} pos={pos_qty}")

                # BUY
                if d.action == "BUY" and pos_qty <= 0:
                    if args.signal_place_orders:
                        qty = max(1, int(args.signal_qty))
                    else:
                        acct = trading.get_account()
                        buying_power = float(acct.buying_power)
                        qty = int((buying_power * args.cash_pct) // bar_close)
                        qty = min(qty, args.max_shares)

                    if qty > 0:
                        if args.signal_place_orders and args.signal_limit_pct is not None:
                            lim = round(bar_close * (1 + float(args.signal_limit_pct)), 2)
                            submit_buy(trading, symbol, qty, tif=TimeInForce.DAY,
                                       limit_price=lim, extended=args.signal_extended)
                        else:
                            submit_buy(trading, symbol, qty, tif=TimeInForce.DAY)
                        buy_marks.append((pd.Timestamp(bar_time), bar_close))
                        print(f"BUY {qty} {symbol} @~{bar_close:.2f}")

                # SELL
                elif d.action == "SELL" and pos_qty > 0:
                    if args.signal_place_orders:
                        qty = min(pos_qty, max(1, int(args.signal_qty)))
                    else:
                        qty = pos_qty  # 原逻辑一次性平仓

                    if args.signal_place_orders and args.signal_limit_pct is not None:
                        lim = round(bar_close * (1 - float(args.signal_limit_pct)), 2)
                        submit_sell(trading, symbol, qty, tif=TimeInForce.DAY,
                                    limit_price=lim, extended=args.signal_extended)
                    else:
                        submit_sell(trading, symbol, qty, tif=TimeInForce.DAY)
                    sell_marks.append((pd.Timestamp(bar_time), bar_close))
                    print(f"SELL {qty} {symbol} @~{bar_close:.2f}")

                if args.live_plot:
                    overlays = overlays_for_plot(args, bars, engine)
                    plot_intraday(bars, symbol, overlays, buy_marks, sell_marks,
                                  title=f"{symbol} (LIVE {args.strategy.upper()})", window=args.plot_window)

            time.sleep(5)
        except Exception as e:
            print("ERROR:", e)
            time.sleep(5)


def main():
    load_dotenv()

    parser = argparse.ArgumentParser(description="Live/Sim trading (Alpaca paper, IEX only)")
    parser.add_argument("--symbol", type=str, default=os.getenv("SYMBOL", "AAPL"))
    parser.add_argument("--strategy", type=str, default=os.getenv("STRATEGY", "sma"),
                        choices=["sma", "vwap"])

    # SMA params
    parser.add_argument("--fast", type=int, default=int(os.getenv("FAST", "10")))
    parser.add_argument("--slow", type=int, default=int(os.getenv("SLOW", "50")))
    parser.add_argument("--hysteresis", type=float, default=float(os.getenv("HYSTERESIS", "0.002")))
    parser.add_argument("--cooldown", type=int, default=int(os.getenv("COOLDOWN_BARS", "3")))
    parser.add_argument("--confirm", type=int, default=int(os.getenv("CONFIRM_BARS", "1")))

    # VWAP params
    parser.add_argument("--vwap-window", type=int, default=int(os.getenv("VWAP_WINDOW", "20")))
    parser.add_argument("--vwap-mult", type=float, default=float(os.getenv("VWAP_MULT", "2.0")))

    # Trading / risk
    parser.add_argument("--cash_pct", type=float, default=float(os.getenv("CASH_PCT", "0.95")))
    parser.add_argument("--max-shares", type=int, default=int(os.getenv("MAX_SHARES", "500")))

    # Mode
    parser.add_argument("--mode", type=str, default=os.getenv("MODE", "auto"),
                        choices=["auto", "live", "sim"],
                        help="auto: 市场开=live, 收盘=sim；sim: 仅回放；live: 只实时")

    # SIM options (回放时可选真实下单)
    parser.add_argument("--sim-place-orders", action="store_true",
                        help="在 SIM 回放中也通过 Alpaca 下单（收盘时订单会排队到下个交易时段）")
    parser.add_argument("--sim-qty", type=int, default=int(os.getenv("SIM_QTY", "1")))
    parser.add_argument("--sim-speed", type=float, default=float(os.getenv("SIM_SPEED", "0.02")),
                        help="模拟每根bar推进的 sleep 秒数")
    parser.add_argument("--limit-on-sim", type=float, default=None,
                        help="SIM 下单时使用限价的百分比偏移（例如 0.002 表示±0.2%），默认 None 用市价")
    parser.add_argument("--extended", action="store_true",
                        help="限价单是否允许 extended hours（注意收盘完全关闭时仍会排到下一个交易时段）")

    # Optional plotting
    parser.add_argument("--live-plot", action="store_true")
    parser.add_argument("--plot-window", type=int, default=200)
    parser.add_argument("--plot-every", type=int, default=3,
                        help="每隔多少根bar绘一次图，降低开销与闪烁")
    parser.add_argument("--plot-warmup", type=int, default=40,
                        help="至少积累多少根bar后再开始画图，避免rolling初期全NaN")

    # Signal-based orders (通用信号下单开关)
    parser.add_argument("--signal-place-orders", action="store_true",
                        help="根据策略买/卖信号自动下单（每次固定股数）")
    parser.add_argument("--signal-qty", type=int, default=1,
                        help="信号触发时每次下单的股数（默认1股）")
    parser.add_argument("--signal-limit-pct", type=float, default=None,
                        help="信号下单时使用限价的百分比偏移（例如 0.001=+0.1%% 买入 / -0.1%% 卖出；默认 None 用市价）")
    parser.add_argument("--signal-extended", action="store_true",
                        help="信号限价单是否允许 extended hours")

    # Force orders (立即手动一笔)
    parser.add_argument("--force-buy", type=int, help="强制买入指定股数（立即下单）")
    parser.add_argument("--force-sell", type=int, help="强制卖出指定股数（立即下单）")

    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    API_KEY = os.getenv("ALPACA_API_KEY")
    API_SECRET = os.getenv("ALPACA_SECRET_KEY") or os.getenv("ALPACA_API_SECRET")
    USE_PAPER = os.getenv("ALPACA_USE_PAPER", "true").lower() == "true"
    if not API_KEY or not API_SECRET:
        raise RuntimeError("Missing ALPACA_API_KEY / ALPACA_SECRET_KEY")

    symbol = args.symbol.upper()

    trading = TradingClient(API_KEY, API_SECRET, paper=USE_PAPER)
    data_client = StockHistoricalDataClient(API_KEY, API_SECRET)

    # 手动强制单（随时一股/多股）
    if args.force_buy or args.force_sell:
        if args.force_buy:
            submit_buy(trading, symbol, args.force_buy, tif=TimeInForce.DAY)
            print(f"[FORCE BUY] {args.force_buy} {symbol}")
        if args.force_sell:
            submit_sell(trading, symbol, args.force_sell, tif=TimeInForce.DAY)
            print(f"[FORCE SELL] {args.force_sell} {symbol}")
        return

    market_open = is_market_open_now(trading)

    if args.mode == "live":
        if not market_open:
            print("Market is closed; --mode=live 无法实时。可用 --mode=sim + --sim-place-orders 或 --signal-place-orders 做回放下单。")
            return
        run_live_stream(args, trading, data_client, symbol)
        return

    if args.mode == "sim":
        run_simulated_session(args, trading, data_client, symbol)
        return

    # auto
    print(f"Mode=auto | market_open={market_open}")
    if market_open:
        run_live_stream(args, trading, data_client, symbol)
    else:
        run_simulated_session(args, trading, data_client, symbol)


if __name__ == "__main__":
    main()
