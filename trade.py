

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import os
from datetime import datetime, timedelta

import backtrader as bt
import pandas as pd
import yfinance as yf
from dotenv import load_dotenv

# 你的统一策略接口（已包含 SMACrossEngine / VWAPEngine / Decision）
from strategy import Decision, SMACrossEngine, VWAPEngine


# ========= Backtrader 包装：把“引擎”接到 BT =========
class EngineWrapper(bt.Strategy):
    """
    用统一的策略引擎驱动 Backtrader。
    支持 strategy_name = 'sma' | 'vwap'
    """
    params = dict(
        strategy_name="sma",
        # SMA 专用
        fast=10,
        slow=50,
        # 通用控制
        hysteresis=0.002,
        cooldown_bars=3,
        confirm_bars=1,
        verbose=False,
    )

    def __init__(self):
        name = (self.p.strategy_name or "sma").lower()

        if name == "sma":
            # 画线只用于可视化；交易决策来自你的引擎
            self.bt_sma_fast = bt.ind.SMA(self.data.close, period=self.p.fast)
            self.bt_sma_slow = bt.ind.SMA(self.data.close, period=self.p.slow)
            self.bt_sma_fast.plotinfo.plotname = f"SMA({self.p.fast})"
            self.bt_sma_slow.plotinfo.plotname = f"SMA({self.p.slow})"
            self.bt_sma_fast.plotinfo.plotmaster = self.data
            self.bt_sma_slow.plotinfo.plotmaster = self.data

            self.engine = SMACrossEngine(
                fast=self.p.fast,
                slow=self.p.slow,
                hysteresis=self.p.hysteresis,
                cooldown_bars=self.p.cooldown_bars,
                confirm_bars=self.p.confirm_bars,
            )
        elif name == "vwap":
            # VWAP 引擎（分钟/多分钟更合适）
            self.engine = VWAPEngine(
                hysteresis=self.p.hysteresis,
                confirm_bars=self.p.confirm_bars,
                cooldown_bars=self.p.cooldown_bars,
            )
        else:
            raise ValueError(f"Unknown strategy: {self.p.strategy_name}")

        self._name = name

    def next(self):
        close = float(self.data.close[0])

        if self._name == "vwap":
            # VWAP 需要 high/low/volume
            high = float(self.data.high[0])
            low = float(self.data.low[0])
            volume = float(self.data.volume[0])
            d: Decision = self.engine.on_bar_close(
                close=close, high=high, low=low, volume=volume
            )
        else:
            # SMA 只要 close
            d: Decision = self.engine.on_bar_close(close)

        if self.p.verbose:
            dt = self.data.datetime.datetime(0)
            f = f"{(d.sma_fast if d.sma_fast is not None else float('nan')):.4f}" if d.sma_fast is not None else "None"
            s = f"{(d.sma_slow if d.sma_slow is not None else float('nan')):.4f}" if d.sma_slow is not None else "None"
            print(f"[{dt}] close={close:.4f} fast={f} slow={s} action={d.action} reason={d.reason}")

        # 执行交易
        if d.action == "BUY" and not self.position:
            self.buy()
        elif d.action == "SELL" and self.position:
            self.sell()


# ========= 数据下载 & 处理 =========
def _normalize_df(df: pd.DataFrame) -> pd.DataFrame:
    """
    统一列名、索引、增加 OpenInterest，Backtrader 友好。
    """
    if df is None or df.empty:
        return df

    # yfinance 可能返回 MultiIndex 列
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]

    # 只保留标准列
    need = ["Open", "High", "Low", "Close", "Volume"]
    cols = [c for c in need if c in df.columns]
    df = df[cols].copy()

    # 索引去时区（BT 更稳定）
    if isinstance(df.index, pd.DatetimeIndex) and df.index.tz is not None:
        df.index = df.index.tz_convert(None)

    # Backtrader 需要这一列
    df["OpenInterest"] = 0
    df.dropna(inplace=True)
    return df


def _resample_to_5m(df_1m: pd.DataFrame) -> pd.DataFrame:
    """
    将 1m OHLCV 重采样为 5m。
    以右闭合/右标签收盘对齐。
    """
    df = df_1m.copy()
    df = df.resample("5min", label="right", closed="right").agg({
        "Open": "first",
        "High": "max",
        "Low": "min",
        "Close": "last",
        "Volume": "sum",
    }).dropna()
    return df


def download_ohlcv(symbol: str, start: str | None, end: str | None, interval: str) -> pd.DataFrame:
    """
    - 日线：使用 start/end
    - 1m/5m：使用 period='7d'（yfinance 限制 1m 最多 7天）
    """
    interval = interval.lower()
    if interval not in ("1d", "1m", "5m"):
        raise ValueError("interval must be one of: 1d, 1m, 5m")

    if interval == "1d":
        hist = yf.Ticker(symbol).history(
            start=start, end=end, auto_adjust=False, actions=False, interval="1d"
        )
        return _normalize_df(hist)

    # 分钟级：最多 7 天
    hist_1m = yf.Ticker(symbol).history(
        period="7d", interval="1m", auto_adjust=False, actions=False
    )
    if hist_1m.empty:
        raise ValueError("No 1m data (yfinance may restrict minutes to last ~7 days).")

    if interval == "5m":
        hist = _resample_to_5m(hist_1m)
    else:
        hist = hist_1m

    return _normalize_df(hist)


# ========= 回测主流程 =========
def run(symbol: str,
        start: str | None,
        end: str | None,
        strategy_name: str = "sma",
        interval: str = "1d",
        fast: int = 10,
        slow: int = 50,
        hysteresis: float = 0.002,
        cooldown_bars: int = 3,
        confirm_bars: int = 1,
        verbose: bool = False,
        plot: bool = False):

    cerebro = bt.Cerebro(stdstats=False)

    cerebro.addstrategy(
        EngineWrapper,
        strategy_name=strategy_name,
        fast=fast,
        slow=slow,
        hysteresis=hysteresis,
        cooldown_bars=cooldown_bars,
        confirm_bars=confirm_bars,
        verbose=verbose,
    )

    df = download_ohlcv(symbol, start, end, interval)
    data = bt.feeds.PandasData(dataname=df)
    data.plotinfo.plotvolume = False
    cerebro.adddata(data)

    # 买卖箭头
    cerebro.addobserver(bt.observers.BuySell, barplot=True, bardist=0.02)

    cerebro.broker.setcash(100000.0)
    print(f"Starting Portfolio Value: {cerebro.broker.getvalue():.2f}")
    cerebro.run()
    print(f"Final   Portfolio Value: {cerebro.broker.getvalue():.2f}")

    if plot:
        cerebro.plot(style="candlestick")


# ========= CLI =========
def main():
    load_dotenv()

    ap = argparse.ArgumentParser(description="Backtest with SMA/VWAP engines (Backtrader)")
    ap.add_argument("--symbol", type=str, default=os.getenv("SYMBOL", "AAPL"))
    ap.add_argument("--start", type=str, help="YYYY-MM-DD (日线用；分钟级通常忽略)")
    ap.add_argument("--end", type=str, help="YYYY-MM-DD")
    ap.add_argument("--strategy", type=str, default=os.getenv("STRATEGY", "sma"),
                    choices=["sma", "vwap"], help="选择策略：sma 或 vwap")
    ap.add_argument("--interval", type=str, default=os.getenv("INTERVAL", "1d"),
                    choices=["1d", "1m", "5m"], help="K线级别：日线/1分钟/5分钟")
    # SMA 参数
    ap.add_argument("--fast", type=int, default=int(os.getenv("FAST", "10")))
    ap.add_argument("--slow", type=int, default=int(os.getenv("SLOW", "50")))
    # 通用控制
    ap.add_argument("--hysteresis", type=float, default=float(os.getenv("HYSTERESIS", "0.002")))
    ap.add_argument("--cooldown", type=int, default=int(os.getenv("COOLDOWN_BARS", "3")))
    ap.add_argument("--confirm", type=int, default=int(os.getenv("CONFIRM_BARS", "1")))
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--plot", action="store_true")
    args = ap.parse_args()

    # 对分钟级给点提醒
    if args.interval in ("1m", "5m") and (args.start or args.end):
        print("[Note] yfinance 1m 数据最多 ~7 天；本脚本会自动用 period='7d' 来取分钟数据，"
              "因此 start/end 在分钟级通常会被忽略。")

    run(
        symbol=args.symbol,
        start=args.start,
        end=args.end,
        strategy_name=args.strategy,
        interval=args.interval,
        fast=args.fast,
        slow=args.slow,
        hysteresis=args.hysteresis,
        cooldown_bars=args.cooldown,
        confirm_bars=args.confirm,
        verbose=args.verbose,
        plot=args.plot,
    )


if __name__ == "__main__":
    main()
