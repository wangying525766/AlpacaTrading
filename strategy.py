# strategy.py
from __future__ import annotations
from dataclasses import dataclass
from collections import deque
import numpy as np
from typing import Optional


@dataclass
class Decision:
    """
    统一的策略输出对象。
    注意：为了兼容你现有日志打印，这里保留了 sma_fast/sma_slow 字段名：
      - 对 SMA: sma_fast=FAST均线, sma_slow=SLOW均线
      - 对 VWAP: sma_fast=当前价格(或典型价), sma_slow=VWAP
    """
    action: str                 # "BUY" | "SELL" | "HOLD"
    sma_fast: Optional[float]   # 指标1（SMA fast / 价格）
    sma_slow: Optional[float]   # 指标2（SMA slow / VWAP）
    reason: str                 # 触发原因描述


# =========================
#   SMA Cross Engine
# =========================
class SMACrossEngine:
    """
    简单均线交叉策略（带滞后带 + 连续确认 + 冷却）
    - hysteresis: 比例阈值（如 0.002 = 0.2%），避免抖动反复交易
    - confirm_bars: 连续满足信号的K线数量（>=1）
    - cooldown_bars: 成交后必须等待的K线数量
    """
    def __init__(self, fast: int = 10, slow: int = 50,
                 hysteresis: float = 0.002,
                 cooldown_bars: int = 3,
                 confirm_bars: int = 1):
        assert fast < slow, "fast must be < slow"
        assert confirm_bars >= 1
        self.fast, self.slow = int(fast), int(slow)
        self.hys = float(hysteresis)
        self.cool = int(cooldown_bars)
        self.confirm = int(confirm_bars)

        self.buf = deque(maxlen=self.slow + 5)
        self.prev_state = 0      # -1/0/1
        self.cool_left = 0
        self.in_pos = False

        self._up_streak = 0
        self._dn_streak = 0

    def _sma(self, n: int) -> Optional[float]:
        if len(self.buf) < n:
            return None
        return float(np.mean(list(self.buf)[-n:]))

    def on_bar_close(self, close: float) -> Decision:
        self.buf.append(float(close))
        f = self._sma(self.fast)
        s = self._sma(self.slow)
        if f is None or s is None:
            return Decision("HOLD", f, s, "warmup")

        up = f > s * (1 + self.hys)
        dn = f < s * (1 - self.hys)
        curr = 1 if up else (-1 if dn else 0)

        if self.cool_left > 0:
            self.cool_left -= 1
            # 维护 streak，冷却期间也更新状态，避免刚解冷却立马误触发
            self._up_streak = self._up_streak + 1 if curr > 0 else 0
            self._dn_streak = self._dn_streak + 1 if curr < 0 else 0
            self.prev_state = curr
            return Decision("HOLD", f, s, "cooldown")

        # 连续确认计数
        if curr > 0:
            self._up_streak += 1
            self._dn_streak = 0
        elif curr < 0:
            self._dn_streak += 1
            self._up_streak = 0
        else:
            self._up_streak = 0
            self._dn_streak = 0

        cross_up   = (self.prev_state <= 0) and (curr > 0)
        cross_down = (self.prev_state >= 0) and (curr < 0)
        self.prev_state = curr

        if cross_up and not self.in_pos:
            if self._up_streak >= self.confirm:
                self.in_pos = True
                self.cool_left = self.cool
                return Decision("BUY", f, s, "cross_up")
            else:
                return Decision("HOLD", f, s, "confirming")

        if cross_down and self.in_pos:
            if self._dn_streak >= self.confirm:
                self.in_pos = False
                self.cool_left = self.cool
                return Decision("SELL", f, s, "cross_down")
            else:
                return Decision("HOLD", f, s, "confirming")

        return Decision("HOLD", f, s, "no_signal")


# =========================
#        VWAP Engine
# =========================
class VWAPEngine:
    """
    VWAP 突破-回调-确认策略（含滞后带、斜率、成交量确认、止盈止损、移动止盈、时间止盈）
    使用方式不变：逐bar调用 on_bar_close()，新交易日调用 new_session() 或传 is_new_session=True
    """
    def __init__(
        self,
        # 信号与执行
        hysteresis: float = 0.001,        # VWAP 上下带宽（避免抖动）
        confirm_bars: int = 2,            # 连续满足信号的K线数量
        cooldown_bars: int = 3,           # 成交后冷却
        # 进场逻辑（防追高）
        entry_mode: str = "breakout_pullback",  # "cross" 或 "breakout_pullback"
        entry_max_ext: float = 0.004,     # 买入时价格相对VWAP的最大超价（0.4%）
        pullback_pct: float = 0.002,      # 突破后需回落至 |px - vwap|/vwap <= 0.2%
        # 方向过滤
        vwap_slope_window: int = 5,       # 斜率检测窗口（最近N根VWAP是否上行）
        slope_min: float = 0.0,           # 最小斜率阈值（0表示只要上行即可）
        # 成交量确认（可选）
        use_volume_confirm: bool = False,
        vol_window: int = 20,
        vol_confirm_mult: float = 1.2,    # 当前量 >= 均量 * 1.2
        # 风险管理
        take_profit: float = 0.03,        # +3% 止盈
        stop_loss: float = -0.01,         # -1% 止损
        trailing_pct: float = 0.02,       # 回撤2% 触发移动止盈
        max_hold_bars: int = 60,          # 最多持有N根K线
        # ATR 止损（可选，优先级高于百分比止损）
        use_atr_stop: bool = False,
        atr_window: int = 14,
        atr_mult_stop: float = 1.0,
    ):
        # 基本参数
        self.hys = float(hysteresis)
        self.confirm = int(confirm_bars)
        self.cool = int(cooldown_bars)
        # 进场逻辑
        self.entry_mode = entry_mode
        self.entry_max_ext = float(entry_max_ext)
        self.pullback_pct = float(pullback_pct)
        # 方向过滤
        self.vwap_slope_window = int(vwap_slope_window)
        self.slope_min = float(slope_min)
        # 量能
        self.use_volume_confirm = bool(use_volume_confirm)
        self.vol_window = int(vol_window)
        self.vol_confirm_mult = float(vol_confirm_mult)
        # 风控
        self.take_profit = float(take_profit)
        self.stop_loss = float(stop_loss)
        self.trailing_pct = float(trailing_pct)
        self.max_hold_bars = int(max_hold_bars)
        # ATR
        self.use_atr_stop = bool(use_atr_stop)
        self.atr_window = int(atr_window)
        self.atr_mult_stop = float(atr_mult_stop)

        self.reset_session()

    # ---- 会话控制 ----
    def reset_session(self):
        self.sum_pv = 0.0
        self.sum_vol = 0.0
        self.cool_left = 0
        self.in_pos = False
        self.up_streak = 0
        self.dn_streak = 0

        # 进场形态跟踪
        self._had_breakout_up = False     # 是否出现过向上突破
        self._bars_since_breakout = 0

        # 风控状态
        self.entry_price = None
        self.peak_price = None
        self.hold_bars = 0

        # 斜率与量能缓存
        from collections import deque
        self._vwap_hist = deque(maxlen=max(3, self.vwap_slope_window))
        self._vol_hist  = deque(maxlen=max(3, self.vol_window))

        # ATR
        self._atr_ready = False
        self._atr_hist = deque(maxlen=max(2, self.atr_window))
        self._prev_close = None
        self._curr_atr = None

    def new_session(self):
        self.reset_session()

    # ---- 工具 ----
    def _vwap_slope_ok(self) -> bool:
        if len(self._vwap_hist) < self.vwap_slope_window:
            return False
        # 简单线性斜率：末值 - 首值（也可换成线性回归）
        slope = (self._vwap_hist[-1] - self._vwap_hist[0]) / max(1, self.vwap_slope_window - 1)
        return slope > self.slope_min

    def _volume_ok(self, volume: float) -> bool:
        if not self.use_volume_confirm:
            return True
        if len(self._vol_hist) < self.vol_window:
            return False
        avg = sum(self._vol_hist) / len(self._vol_hist)
        return volume >= avg * self.vol_confirm_mult

    def _atr_update(self, high, low, close):
        if not self.use_atr_stop:
            return
        import math
        h, l, c = float(high), float(low), float(close)
        if self._prev_close is None:
            tr = h - l
        else:
            tr = max(h - l, abs(h - self._prev_close), abs(l - self._prev_close))
        self._prev_close = c
        self._atr_hist.append(tr)
        if len(self._atr_hist) >= self.atr_window:
            self._curr_atr = sum(self._atr_hist) / len(self._atr_hist)
            self._atr_ready = True

    # ---- 主逻辑 ----
    def on_bar_close(
        self,
        close: float,
        high: Optional[float] = None,
        low: Optional[float] = None,
        volume: float = 0.0,
        is_new_session: bool = False
    ) -> Decision:
        if is_new_session:
            self.reset_session()

        close = float(close)
        volume = float(volume)
        if high is None or low is None:
            typical = close
            high = close
            low = close
        else:
            high = float(high)
            low  = float(low)
            typical = (high + low + close) / 3.0

        # VWAP 累计
        self.sum_pv += typical * volume
        self.sum_vol += volume
        if self.sum_vol <= 0:
            return Decision("HOLD", None, None, "warmup")

        vwap = self.sum_pv / self.sum_vol
        px = close

        # 缓存斜率 & 量能 & ATR
        self._vwap_hist.append(vwap)
        self._vol_hist.append(volume)
        self._atr_update(high, low, close)

        # 冷却
        if self.cool_left > 0:
            self.cool_left -= 1
            # 持仓期间也更新持仓风控
            if self.in_pos:
                self.hold_bars += 1
                self.peak_price = px if (self.peak_price is None) else max(self.peak_price, px)
                reason = self._check_exit(px)
                if reason:
                    self.in_pos = False
                    self.cool_left = self.cool
                    return Decision("SELL", px, vwap, reason)
            return Decision("HOLD", px, vwap, "cooldown")

        # 价格相对 VWAP 的带宽判断
        up = px > vwap * (1 + self.hys)
        dn = px < vwap * (1 - self.hys)

        # 连续确认计数（仅用于“带宽在外”的状态）
        if up:
            self.up_streak += 1
            self.dn_streak = 0
        elif dn:
            self.dn_streak += 1
            self.up_streak = 0
        else:
            self.up_streak = 0
            self.dn_streak = 0

        # ------- 出场逻辑（先检查风控） -------
        if self.in_pos:
            self.hold_bars += 1
            self.peak_price = px if (self.peak_price is None) else max(self.peak_price, px)
            # 风控退出优先
            reason = self._check_exit(px)
            if reason:
                self.in_pos = False
                self.cool_left = self.cool
                return Decision("SELL", px, vwap, reason)
            # 次之：跌破带宽（连续确认）
            if self.dn_streak >= self.confirm:
                self.in_pos = False
                self.cool_left = self.cool
                return Decision("SELL", px, vwap, "cross_down")
            return Decision("HOLD", px, vwap, "hold")

        # ------- 入场逻辑 -------
        # 方向过滤：VWAP 斜率必须向上
        if not self._vwap_slope_ok():
            return Decision("HOLD", px, vwap, "slope_filter")

        # 成交量确认（可选）
        if not self._volume_ok(volume):
            return Decision("HOLD", px, vwap, "volume_filter")

        if self.entry_mode == "cross":
            # 简单上穿确认
            if self.up_streak >= self.confirm:
                if abs(px / vwap - 1.0) <= self.entry_max_ext:
                    self._enter_position(px)
                    return Decision("BUY", px, vwap, "cross_up")
                else:
                    return Decision("HOLD", px, vwap, "too_far_above_vwap")
            return Decision("HOLD", px, vwap, "confirming")

        # 默认：breakout → pullback → 近VWAP反弹买入
        # 步骤1：记录“向上突破”事件
        if up and self.up_streak >= self.confirm:
            self._had_breakout_up = True
            self._bars_since_breakout = 0
            return Decision("HOLD", px, vwap, "breakout_marked")

        # 步骤2：突破后允许一定回落，且价格需回到接近 VWAP（不远离）
        if self._had_breakout_up:
            self._bars_since_breakout += 1
            dist = abs(px / vwap - 1.0)
            near = dist <= self.pullback_pct
            not_far = dist <= self.entry_max_ext
            if near and not_far and px >= vwap * (1 - self.hys):
                # 二次确认：价格再次企稳于 vwap 上方
                self._enter_position(px)
                self._had_breakout_up = False
                return Decision("BUY", px, vwap, "breakout_pullback_buy")

            # 若回落过深，或过久未满足条件，则失效
            if px < vwap * (1 - self.hys) or self._bars_since_breakout > max(5, self.confirm + 2):
                self._had_breakout_up = False

        return Decision("HOLD", px, vwap, "no_signal")

    # ---- 内部：进场/出场辅助 ----
    def _enter_position(self, price: float):
        self.in_pos = True
        self.cool_left = self.cool
        self.entry_price = float(price)
        self.peak_price = float(price)
        self.hold_bars = 0

    def _check_exit(self, price: float) -> Optional[str]:
        if self.entry_price is None:
            return None
        ret = (price - self.entry_price) / max(1e-9, self.entry_price)

        # ATR 止损优先
        if self.use_atr_stop and self._atr_ready and self._curr_atr is not None:
            if (self.entry_price - price) >= self.atr_mult_stop * self._curr_atr:
                return f"atr_stop({self.atr_mult_stop}*ATR)"

        # 移动止盈（先更新峰值后判断回撤）
        if self.peak_price is not None and price < self.peak_price * (1 - self.trailing_pct):
            return "trailing_stop"

        if ret >= self.take_profit:
            return "take_profit"
        if ret <= self.stop_loss:
            return "stop_loss"
        if self.hold_bars >= self.max_hold_bars:
            return "time_exit"
        return None

    # 便捷：兼容 dict/Series
    def feed_ohlcv(self, row, is_new_session: bool = False) -> Decision:
        get = lambda k: (row.get(k, row.get(k.capitalize())) if hasattr(row, "get") else getattr(row, k, None))
        return self.on_bar_close(
            close=get("close"),
            high=get("high"),
            low=get("low"),
            volume=get("volume") or 0.0,
            is_new_session=is_new_session,
        )



# =========================
#     工厂 & 导出
# =========================
def select_strategy(name: str, **kwargs):
    """
    name: "sma" | "vwap"
    kwargs 透传给对应 Engine 的 __init__（比如 hysteresis/confirm_bars/cooldown_bars）
    """
    n = name.strip().lower()
    if n == "sma":
        return SMACrossEngine(**kwargs)
    if n == "vwap":
        return VWAPEngine(**kwargs)
    raise ValueError(f"Unknown strategy: {name!r}. Use 'sma' or 'vwap'.")


__all__ = [
    "Decision",
    "SMACrossEngine",
    "VWAPEngine",
    "select_strategy",
]
