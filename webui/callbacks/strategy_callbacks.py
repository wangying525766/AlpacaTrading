# webui/callbacks/callbacks_strategy.py
from __future__ import annotations

from dash import Input, Output, State, callback
from dash.exceptions import PreventUpdate
from pathlib import Path
from datetime import datetime
import subprocess, os, re

PROJECT_ROOT = Path(__file__).resolve().parents[2]
HOME = Path.home()

PYTHON_BIN   = str(PROJECT_ROOT / ".venv" / "bin" / "python")
LOG_DIR      = PROJECT_ROOT / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

# 防重复注册（Dash 热重载/多处 import 时很重要）
_CB_REGISTERED = False

def register_strategy_callbacks(app):
    global _CB_REGISTERED
    if _CB_REGISTERED:
        return
    _CB_REGISTERED = True

    # ---------- 回测：同步执行 trade.py，输出到 stg-output ----------
    @callback(
        Output("stg-output", "children", allow_duplicate=True),  # 可能与 start_live 共用同一输出
        Input("btn-stg-backtest", "n_clicks"),
        State("stg-symbol", "value"),
        State("stg-strategy", "value"),
        State("stg-interval", "value"),   # 面板有这个，传给 trade.py（live 不用）
        State("stg-start", "value"),
        State("stg-end", "value"),
        State("stg-fast", "value"),
        State("stg-slow", "value"),
        State("stg-hys", "value"),
        State("stg-cool", "value"),
        State("stg-confirm", "value"),
        State("stg-plot", "value"),
        prevent_initial_call=True
    )
    def run_backtest(n, symbol, strategy, interval, start, end,
                     fast, slow, hys, cool, confirm, plot_vals):
        if not n:
            raise PreventUpdate
        if not symbol:
            return "⚠️ Please enter a symbol."

        symbol   = (symbol or "AAPL").strip().upper()
        strategy = (strategy or "sma").strip()
        interval = (interval or "1d").strip()

        cmd = [
            PYTHON_BIN, "trade.py",
            "--symbol", symbol,
            "--strategy", strategy,
            "--interval", interval,            # ✅ 回测保留 interval
            "--start", (start or "2025-01-01"),
            "--fast", str(int(fast or 10)),
            "--slow", str(int(slow or 50)),
            "--hysteresis", str(float(hys or 0.001)),
            "--cooldown", str(int(cool or 3)),
            "--confirm", str(int(confirm or 1)),
            "--verbose",
        ]
        if (end or "").strip():
            cmd += ["--end", end.strip()]
        if plot_vals and "plot" in plot_vals:
            cmd += ["--plot"]

        try:
            proc = subprocess.run(cmd, cwd=str(PROJECT_ROOT), capture_output=True, text=True, timeout=300)
            out  = (proc.stdout or "").strip()
            err  = (proc.stderr or "").strip()
            banner = f"$ {' '.join(cmd)}\n"
            if proc.returncode != 0:
                return f"{banner}\n❌ trade.py failed ({proc.returncode})\n\nSTDOUT:\n{out}\n\nSTDERR:\n{err}"
            return (
                f"{banner}\n"
                f"{out or '(no output)'}"
                + (f"\nSTDERR:\n{err}" if err else "")
            )
        except Exception as e:
            return f"❌ Exception running trade.py: {e}"

    # ---------- 启动 live（后台、mode=auto），保存日志路径并启用轮询 ----------
    @callback(
        Output("stg-output", "children", allow_duplicate=True),
        Output("stg-logfile", "data", allow_duplicate=True),
        Output("stg-log-poll", "disabled", allow_duplicate=True),
        Input("btn-stg-live", "n_clicks"),
        State("stg-symbol", "value"),
        State("stg-strategy", "value"),
        # 注意：不再使用 interval 传给 live_trade.py，所以不取它
        State("stg-fast", "value"),
        State("stg-slow", "value"),
        State("stg-hys", "value"),
        State("stg-cool", "value"),
        State("stg-confirm", "value"),
        prevent_initial_call=True
    )

    def start_live(n, symbol, strategy, fast, slow, hys, cool, confirm):
        if not n:
            raise PreventUpdate
        if not symbol:
            return "⚠️ Please enter a symbol.", None, True

        symbol   = symbol.strip().upper()
        strategy = (strategy or "sma").strip()

        stamp    = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = LOG_DIR / f"live_{symbol}_{stamp}.log"

        # ✅ 去掉 --interval，按你的 live_trade.py 现状启动
        cmd = [
            PYTHON_BIN, "-u", "live_trade.py",
            "--mode", "auto",                 # 开市走 live，闭市走 sim
            "--symbol", symbol,
            "--strategy", strategy,
            "--fast", str(int(fast or 10)),
            "--slow", str(int(slow or 50)),
            "--hysteresis", str(float(hys or 0.001)),
            "--cooldown", str(int(cool or 3)),
            "--confirm", str(int(confirm or 1)),
            "--verbose",
        ]
        if strategy == "vwap":
            cmd += ["--vwap-window", "20", "--vwap-mult", "2.0"]


        try:
            lf = open(log_file, "w", buffering=1)  # 行缓冲
            subprocess.Popen(
                cmd,
                cwd=str(PROJECT_ROOT),
                stdout=lf,
                stderr=subprocess.STDOUT,
                start_new_session=True,
                env={**os.environ, "PYTHONUNBUFFERED": "1"},  # 无缓冲输出
            )
            banner = (
                "✅ live_trade.py started (detached, mode=auto).\n"
                f"Log: {log_file}\n"
                f"Cmd: {' '.join(cmd)}\n"
                "---- Reading log below ----"
            )
            return banner, str(log_file), False  # False=启用轮询
        except Exception as e:
            return f"❌ Failed to start live_trade.py: {e}", None, True



    # ---------- 轮询日志：每2秒显示末尾 ----------
    @callback(
        Output("stg-live-log", "children", allow_duplicate=True),
        Input("stg-log-poll", "n_intervals"),
        State("stg-logfile", "data"),
        prevent_initial_call=True
    )
    def poll_live_log(_n, log_path):
        if not log_path:
            raise PreventUpdate
        p = Path(log_path)
        if not p.exists():
            return "(waiting for log...)"
        try:
            with open(p, "rb") as f:
                f.seek(0, os.SEEK_END)
                size = f.tell()
                f.seek(max(0, size - 65536), os.SEEK_SET)  # 只读最后 ~64KB
                chunk = f.read().decode("utf-8", errors="replace")
            lines = chunk.splitlines()[-100:]             # 显示最后 100 行
            return "\n".join(lines) or "(log empty)"
        except Exception as e:
            return f"(read log error: {e})"
