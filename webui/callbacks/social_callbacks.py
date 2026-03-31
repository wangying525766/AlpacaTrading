# webui/callbacks/callbacks_social.py
from __future__ import annotations

from dash import Input, Output, State, callback
from dash.exceptions import PreventUpdate
from pathlib import Path
from datetime import datetime
import subprocess, os, json

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PYTHON_BIN   = str(PROJECT_ROOT / ".venv" / "bin" / "python")
LOG_DIR      = PROJECT_ROOT / "logs"
TMP_DIR      = PROJECT_ROOT / "tmp"
LOG_DIR.mkdir(parents=True, exist_ok=True)
TMP_DIR.mkdir(parents=True, exist_ok=True)

_CB_SOCIAL_REGISTERED = False

def register_social_callbacks(app):
    global _CB_SOCIAL_REGISTERED
    if _CB_SOCIAL_REGISTERED:
        return
    _CB_SOCIAL_REGISTERED = True

    # 启动爬虫, twitter 版
#     @callback(
#         Output("crawl-logfile", "data", allow_duplicate=True),
#         Output("crawl-result-path", "data", allow_duplicate=True),
#         Output("crawl-poll", "disabled", allow_duplicate=True),
#         Output("crawl-log", "children", allow_duplicate=True),
#         Input("btn-crawl", "n_clicks"),
#         State("crawl-query", "value"),
#         State("crawl-hours", "value"),
#         State("crawl-topk", "value"),
#         State("crawl-min-mentions", "value"),
#         prevent_initial_call=True
#     )
#     def start_crawl(n, query, hours, topk, min_mentions):
#         if not n:
#             raise PreventUpdate
#         query = (query or "").strip()
#         if not query:
#             return None, None, True, "⚠️ Please enter a query."
#
#         stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
#         log_file = LOG_DIR / f"crawl_{stamp}.log"
#         out_file = TMP_DIR / f"crawl_{stamp}.json"
#
#         cmd = [
#             PYTHON_BIN, "-u", "scripts/social/crawl_twitter.py",
#             "--query", query,
#             "--hours", str(int(hours or 6)),
#             "--topk", str(int(topk or 8)),
#             "--min-mentions", str(int(min_mentions or 3)),
#             "--out", str(out_file),
#             "--log", str(log_file),
#         ]
#         # 用 .env 里的配置即可，不需要额外参数
#
#         try:
#             lf = open(log_file, "w", buffering=1)
#             subprocess.Popen(
#                 cmd, cwd=str(PROJECT_ROOT),
#                 stdout=lf, stderr=subprocess.STDOUT,
#                 start_new_session=True,
#                 env={**os.environ, "PYTHONUNBUFFERED": "1"},
#             )
#             banner = (
#                 "🟢 Crawl started.\n"
#                 f"Cmd: {' '.join(cmd)}\n"
#                 f"Log: {log_file}\n"
#                 f"Out: {out_file}\n"
#                 "---- live log ----\n"
#             )
#             return str(log_file), str(out_file), False, banner
#         except Exception as e:
#             return None, None, True, f"❌ Failed to start crawler: {e}"

####################
### 用email trigger

    @callback(
        Output("crawl-logfile", "data", allow_duplicate=True),
        Output("crawl-result-path", "data", allow_duplicate=True),
        Output("crawl-poll", "disabled", allow_duplicate=True),
        Output("crawl-log", "children", allow_duplicate=True),
        Input("btn-crawl", "n_clicks"),
        State("crawl-query", "value"),
        State("crawl-hours", "value"),
        State("crawl-topk", "value"),
        State("crawl-min-mentions", "value"),
        prevent_initial_call=True
    )
    def start_crawl(n, query, hours, topk, min_mentions):
        if not n:
            raise PreventUpdate

        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = LOG_DIR / f"crawl_{stamp}.log"
        out_file = TMP_DIR  / f"crawl_{stamp}.json"

        # 统一默认值
        hours        = int(hours or 6)
        topk         = int(topk or 8)
        min_mentions = int(min_mentions or 2)
        subj_kw      = (query or "").strip() or os.getenv("EMAIL_SUBJECT_KEYWORD", "OpenOutCrier")

        # 用邮箱爬虫（不用传 CLI 参数，全部走环境变量）
        cmd = [PYTHON_BIN, "-u", "scripts/jobs/email_ticker_ingest.py"]

        # 把前端参数传给子进程作为环境变量，确保写到我们指定的 tmp 路径
        env = {
            **os.environ,
            "PYTHONUNBUFFERED": "1",
            "OUT_PATH": str(out_file),
            "LOG_PATH": str(log_file),
            "HOURS_LOOKBACK": str(hours),
            "TOPK": str(topk),
            "MIN_MENTIONS": str(min_mentions),
            # 可选：用前端 query 覆盖主题关键字（允许 “Open Outcrier” 这种空格形式）
            "EMAIL_SUBJECT_KEYWORD": subj_kw,
            # 如果你只想要 $TICKER 样式（避免普通大写词）：
            # "EMAIL_ONLY_CASHTAGS": "true",
        }

        try:
            lf = open(log_file, "w", buffering=1)
            subprocess.Popen(
                cmd,
                cwd=str(PROJECT_ROOT),
                stdout=lf,
                stderr=subprocess.STDOUT,
                start_new_session=True,
                env=env,
            )
            banner = (
                "🟢 Email ingest started.\n"
                f"Cmd: {' '.join(cmd)}\n"
                f"Log: {log_file}\n"
                f"Out: {out_file}\n"
                f"Params: hours={hours}, topk={topk}, min_mentions={min_mentions}, subj='{subj_kw}'\n"
                "---- live log ----\n"
            )
            # 返回给前端：日志文件路径、结果文件路径、开启轮询（disabled=False）、初始 banner
            return str(log_file), str(out_file), False, banner
        except Exception as e:
            return None, None, True, f"❌ Failed to start email ingest: {e}"



    # 停止轮询（不杀进程，仅停止前端刷新）
    @callback(
        Output("crawl-poll", "disabled", allow_duplicate=True),
        Input("btn-crawl-stop", "n_clicks"),
        prevent_initial_call=True
    )
    def stop_poll(_n):
        return True

    # 轮询：读日志尾部 + 解析结果
    @callback(
        Output("crawl-log", "children", allow_duplicate=True),
        Output("crawl-summary", "children", allow_duplicate=True),
        Output("crawl-recos", "children", allow_duplicate=True),
        Input("crawl-poll", "n_intervals"),
        State("crawl-logfile", "data"),
        State("crawl-result-path", "data"),
        prevent_initial_call=True
    )
    def poll_log(_n, log_path, res_path):
        if not log_path:
            raise PreventUpdate

        # 1) 日志尾部
        log_text = "(waiting for log...)"
        p = Path(log_path)
        if p.exists():
            try:
                with open(p, "rb") as f:
                    f.seek(0, os.SEEK_END)
                    size = f.tell()
                    f.seek(max(0, size - 65536), os.SEEK_SET)
                    chunk = f.read().decode("utf-8", errors="replace")
                log_text = "\n".join(chunk.splitlines()[-100:]) or "(log empty)"
            except Exception as e:
                log_text = f"(read log error: {e})"

        # 2) 结果（存在就渲染推荐）
        summary = ""
        recos_html = ""
        if res_path and Path(res_path).exists():
            try:
                with open(res_path, "r") as rf:
                    data = json.load(rf)
                summary = data.get("summary", "")
                recos = data.get("recommendations", [])

                if recos:
                    # 简单渲染：Ticker + 得分 + 推荐理由
                    items = []
                    for r in recos:
                        t = r.get("ticker", "")
                        score = r.get("score", 0)
                        reason = r.get("reason", "")
                        items.append(f"• {t:<6}  score={score:.2f}  {reason}")
                    recos_html = "\n".join(items)
                else:
                    recos_html = "(no recommendations yet)"
            except Exception as e:
                summary = ""
                recos_html = f"(parse result error: {e})"

        return log_text, summary, recos_html
