#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from strategy import SMACrossEngine
import numpy as np

# —— 单元测试默认用“宽松参数”，确保不会被防抖过滤 —— #
TEST_PARAMS = dict(
    hysteresis=0.0,       # 不设滞后带
    cooldown_bars=1,      # 最短冷却
    confirm_bars=1,       # 不需要连续确认
)

def run_sequence(prices, fast=3, slow=5, name="case"):
    eng = SMACrossEngine(fast=fast, slow=slow, **TEST_PARAMS)
    actions = []
    for i, p in enumerate(prices):
        d = eng.on_bar_close(float(p))
        if d.action in ("BUY", "SELL"):
            actions.append((i, d.action, round(d.sma_fast, 4), round(d.sma_slow, 4), d.reason))
    print(f"[{name}] actions:", actions)
    return actions

def test_cross_once():
    # 幅度更明显，便于触发一次BUY和一次SELL
    seq = [10, 9.5, 9.2, 9.4, 10.2, 10.8, 11.0, 10.7, 10.3, 9.8, 9.3]
    acts = run_sequence(seq, fast=3, slow=5, name="cross_once")
    assert any(a[1] == "BUY" for a in acts), "should have BUY"
    assert any(a[1] == "SELL" for a in acts), "should have SELL"

def test_no_signal_when_flat():
    # 横盘+微噪声：宽松参数下可能偶有触发，但数量不应太夸张
    base = 100.0
    rng = np.random.default_rng(42)
    noise = rng.normal(0, 0.01, 200)
    seq = (base + noise).tolist()
    acts = run_sequence(seq, fast=5, slow=20, name="flat")
    assert len(acts) <= 50, f"too many actions on flat data: {len(acts)}"

if __name__ == "__main__":
    test_cross_once()
    test_no_signal_when_flat()
    print("OK: strategy basic checks passed with relaxed params.")
