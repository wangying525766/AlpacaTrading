# #!/usr/bin/env python3
# # -*- coding: utf-8 -*-
# """
# email_ticker_ingest.py
# 从邮箱订阅邮件（如 OpenOutCrier）抽取 tickers，生成 out/social.json
# 输出 schema:
# {
#   "summary": "...",
#   "recommendations": [
#     {"ticker": "NVDA", "score": 8.7, "reason": "mentions=20, avg_sent=+3.1"},
#     ...
#   ]
# }
# """
#
# import os, re, imaplib, email, datetime as dt, json
# from email.header import decode_header
# from pathlib import Path
# from dotenv import load_dotenv
#
# # ---------- utils ----------
# TICKER_RE = re.compile(r"\$([A-Z]{1,5})\b|(?<![A-Z])([A-Z]{1,5})(?![A-Z])")
# POS = {"buy","bull","call","long","breakout","moon","pump","rip","up"}
# NEG = {"sell","bear","put","short","dump","drop","down","bag"}
# NOISE = {"USD","AI","CEO","ETF","THE","AND","FOR"}
#
# def extract_tickers(text: str):
#     text = (text or "").upper()
#     out = []
#     for m in TICKER_RE.finditer(text):
#         t = m.group(1) or m.group(2)
#         if not t or t in NOISE:
#             continue
#         out.append(t)
#     return out
#
# def sentiment_score(text: str) -> int:
#     low = (text or "").lower()
#     p = sum(w in low for w in POS)
#     n = sum(w in low for w in NEG)
#     return p - n
#
# def safe_decode(bytes_or_str, enc='utf-8'):
#     if isinstance(bytes_or_str, bytes):
#         try:
#             return bytes_or_str.decode(enc, errors="ignore")
#         except Exception:
#             return bytes_or_str.decode("utf-8", errors="ignore")
#     return bytes_or_str or ""
#
# def log(msg, lf=None):
#     s = f"[{dt.datetime.utcnow().isoformat(timespec='seconds')}Z] {msg}"
#     print(s, flush=True)
#     if lf:
#         Path(lf).parent.mkdir(parents=True, exist_ok=True)
#         with open(lf, "a") as f:
#             f.write(s + "\n")
#
# # ---------- main ----------
# def run_from_email(
#     host: str, address: str, app_password: str,
#     folder: str = "INBOX",
#     subject_keyword: str = "OpenOutCrier",
#     hours: int = 72,
#     out_path: str = "out/social.json",
#     log_path: str = "out/social_email.log",
#     min_mentions: int = 2,
#     topk: int = 8,
# ):
#     log(f"email ingest start: host={host} addr={address} hours={hours}", log_path)
#
#     since = (dt.datetime.utcnow() - dt.timedelta(hours=hours))
#     # Gmail 搜索语法：SINCE 是按本地日期（非时间）匹配
#     since_str = since.strftime("%d-%b-%Y")  # e.g. 06-Oct-2025
#
#     M = imaplib.IMAP4_SSL(host)
#     try:
#         M.login(address, app_password)
#     except imaplib.IMAP4.error as e:
#         log(f"[imap] login failed: {e}", log_path)
#         return 1
#
#     M.select(folder)
#     # 按主题关键词 + 时间过滤
#     # 注意：IMAP 的 SUBJECT 匹配是粗粒度的；我们后面还会二次过滤时间
#     typ, data = M.search(None, '(SUBJECT "{}" SINCE {})'.format(subject_keyword, since_str))
#     if typ != "OK":
#         log(f"[imap] search failed: {typ}", log_path)
#         M.logout()
#         return 1
#
#     ids = data[0].split()
#     log(f"[imap] matched messages: {len(ids)}", log_path)
#
#     all_texts = []
#     for i in ids[-500:]:  # 最多看最近 500 封，避免太多
#         typ, msg_data = M.fetch(i, "(RFC822 INTERNALDATE)")
#         if typ != "OK" or not msg_data:
#             continue
#
#         # 时间二次过滤（INTERNALDATE 兼容各家 IMAP）
#         internal_date_tuple = msg_data[0]
#         internal_date = None
#         if isinstance(internal_date_tuple, tuple) and len(internal_date_tuple) >= 2:
#             # INTERNALDATE 在 msg_data[0][0] 内部，但解析麻烦：简单起见再 fetch BODY
#             pass
#
#         # 重新完整取邮件并解析
#         typ, body_data = M.fetch(i, "(RFC822)")
#         if typ != "OK" or not body_data:
#             continue
#
#         raw = body_data[0][1]
#         msg = email.message_from_bytes(raw)
#
#         # 解析 Subject
#         dh = decode_header(msg.get("Subject", ""))
#         subj = " ".join(
#             safe_decode(t, enc or "utf-8") if isinstance(t, bytes) else (t or "")
#             for t, enc in dh
#         )
#
#         # 解析日期（Date 头）
#         date_hdr = msg.get("Date")
#         try:
#             msg_dt = dt.datetime(*email.utils.parsedate(date_hdr)[:6])
#         except Exception:
#             msg_dt = dt.datetime.utcnow()
#         if msg_dt < since:
#             continue  # 严格过滤时间窗口内
#
#         # 提取纯文本正文
#         content = []
#         if msg.is_multipart():
#             for part in msg.walk():
#                 ctype = part.get_content_type()
#                 disp = (part.get("Content-Disposition") or "").lower()
#                 if ctype == "text/plain" and "attachment" not in disp:
#                     charset = part.get_content_charset() or "utf-8"
#                     content.append(safe_decode(part.get_payload(decode=True), charset))
#         else:
#             charset = msg.get_content_charset() or "utf-8"
#             payload = msg.get_payload(decode=True)
#             content.append(safe_decode(payload, charset))
#
#         body = "\n".join(content)
#         merged = f"{subj}\n{body}"
#
#         tickers = extract_tickers(merged)
#         if not tickers:
#             continue
#
#         all_texts.append((merged, tickers))
#
#     M.close()
#     M.logout()
#
#     # 聚合 & 评分（与之前 crawler 兼容）
#     counts, scores = {}, {}
#     for text, tickers in all_texts:
#         s = sentiment_score(text)
#         for t in tickers:
#             counts[t] = counts.get(t, 0) + 1
#             scores[t] = scores.get(t, 0) + s
#
#     rows = []
#     for t, c in counts.items():
#         if c < min_mentions:
#             continue
#         avg_s = scores.get(t, 0.0) / max(1, c)
#         score = c + 0.5 * avg_s
#         rows.append((t, c, avg_s, score))
#     rows.sort(key=lambda x: x[3], reverse=True)
#     top = rows[:topk]
#
#     if not top:
#         # fallback 一些常用演示数据
#         summary = f"No matches in last {hours}h. Using mock."
#         recos = [
#             {"ticker": "NVDA", "score": 8.7, "reason": "mentions=20, avg_sent=+3.1"},
#             {"ticker": "TSLA", "score": 7.9, "reason": "mentions=18, avg_sent=+2.8"},
#             {"ticker": "AAPL", "score": 6.1, "reason": "mentions=12, avg_sent=+1.2"},
#         ]
#     else:
#         bullets = [f"{t} (mentions={c}, avg_sent={avg_s:+.2f})" for t,c,avg_s,_ in top]
#         summary = f"Email signals (last {hours}h, subj~\"{subject_keyword}\"):\n" + \
#                   "\n".join(f"• {b}" for b in bullets)
#         recos = [
#             {"ticker": t, "score": float(score),
#              "reason": f"mentions={c}, avg_sent={avg_s:+.2f}"} for t,c,avg_s,score in top
#         ]
#
#     Path(out_path).parent.mkdir(parents=True, exist_ok=True)
#     with open(out_path, "w") as f:
#         json.dump({"summary": summary, "recommendations": recos}, f, indent=2, ensure_ascii=False)
#
#     log(f"✅ saved: {out_path}", log_path)
#     return 0
#
#
# if __name__ == "__main__":
#     load_dotenv()
#     host  = os.getenv("EMAIL_IMAP_HOST", "imap.gmail.com")
#     addr  = os.getenv("EMAIL_ADDRESS")
#     apppw = os.getenv("EMAIL_APP_PASSWORD")
#     folder = os.getenv("EMAIL_FOLDER", "INBOX")
#     kw    = os.getenv("EMAIL_SUBJECT_KEYWORD", "OpenOutCrier")
#     hours = int(os.getenv("HOURS_LOOKBACK", "72"))
#     outp  = os.getenv("OUT_PATH", "out/social.json")
#     logp  = os.getenv("LOG_PATH", "out/social_email.log")
#     minm  = int(os.getenv("MIN_MENTIONS", "2"))
#     topk  = int(os.getenv("TOPK", "8"))
#
#     if not (addr and apppw):
#         print("❌ Missing EMAIL_ADDRESS / EMAIL_APP_PASSWORD")
#         raise SystemExit(2)
#
#     raise SystemExit(
#         run_from_email(host, addr, apppw, folder, kw, hours, outp, logp, minm, topk)
#     )




#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
email_ticker_ingest.py
从邮箱订阅邮件（如 OpenOutCrier）抽取 tickers，生成 out/social.json
输出 schema:
{
  "summary": "...",
  "recommendations": [
    {"ticker": "NVDA", "score": 8.7, "reason": "mentions=20, avg_sent=+3.1"},
    ...
  ]
}
"""

import os, re, imaplib, email, datetime as dt, json
from email.header import decode_header
from pathlib import Path
from dotenv import load_dotenv
from typing import Set, List

# ---------- utils (精确提取 + 去噪) ----------
# 仅抓 $TICKER 的正则
CASH_TAG_RE = re.compile(r"\$([A-Z]{1,5})(?=\b)")
# 可选抓裸大写（需白名单校验）
BARE_TICKER_RE = re.compile(r"\b([A-Z]{1,5})\b")

# 扩充噪音（避免误判为股票）
NOISE = {
    "USD","AI","CEO","ETF","ETFS","THE","AND","FOR","OF","IN","TO","ON","BY",
    "HTTP","HTTPS","WSJ","CNBC","REUTERS","BBG","SI","SA","IPO",
    "OOC","PRE","BR","TM","ET","PM","AM","Q","YOY","QOQ","EPS","GAAP",
    "ADR","SPAC","EV","IPO","INTERNET","OPENAI",
}

# 段落标题：这类区域更像真实信号，稍作加权
SECTION_HEADERS = {
    "DEALS & BREAKING","DEALS","BREAKING",
    "DRUG/BIO","BIO","HEALTHCARE",
    "EARNINGS","RATINGS","+INITIATIONS","INITIATIONS",
    "SYNDICATE","UPGRADES","DOWNGRADES",
    "TOP CONFERENCES","TOP SHAREHOLDER MEETINGS","TOP ANALYST/INVESTOR CALLS",
}

POS = {"buy","bull","call","long","breakout","moon","pump","rip","up"}
NEG = {"sell","bear","put","short","dump","drop","down","bag"}

def sentiment_score(text: str) -> int:
    low = (text or "").lower()
    p = sum(w in low for w in POS)
    n = sum(w in low for w in NEG)
    return p - n

def safe_decode(bytes_or_str, enc='utf-8'):
    if isinstance(bytes_or_str, bytes):
        try:
            return bytes_or_str.decode(enc, errors="ignore")
        except Exception:
            return bytes_or_str.decode("utf-8", errors="ignore")
    return bytes_or_str or ""

def log(msg, lf=None):
    s = f"[{dt.datetime.utcnow().isoformat(timespec='seconds')}Z] {msg}"
    print(s, flush=True)
    if lf:
        Path(lf).parent.mkdir(parents=True, exist_ok=True)
        with open(lf, "a") as f:
            f.write(s + "\n")

def _clean_token(t: str) -> str:
    return (t or "").strip().upper().lstrip("$").strip()

def extract_cashtags(text: str) -> List[str]:
    out = []
    txt = (text or "").upper()
    for m in CASH_TAG_RE.finditer(txt):
        t = _clean_token(m.group(0))
        if 1 <= len(t) <= 5 and t not in NOISE:
            out.append(t)
    return out

def extract_bare_tickers(text: str, universe: Set[str]) -> List[str]:
    out = []
    U = set(x.upper() for x in (universe or []))
    txt = (text or "").upper()
    for m in BARE_TICKER_RE.finditer(txt):
        t = _clean_token(m.group(0))
        if 1 <= len(t) <= 5 and t not in NOISE and t in U:
            out.append(t)
    return out

def build_symbol_universe() -> Set[str]:
    """
    优先用 Alpaca tradable 资产作为白名单；
    否则读取 data/symbols.txt（每行一个代码）；
    都没有则用一小撮常见代码兜底。
    """
    uni: Set[str] = set()
    try:
        from alpaca.trading.client import TradingClient
        key = os.getenv("ALPACA_API_KEY")
        sec = os.getenv("ALPACA_SECRET_KEY") or os.getenv("ALPACA_API_SECRET")
        if key and sec:
            cli = TradingClient(key, sec, paper=True)
            assets = cli.get_all_assets()
            for a in assets:
                if getattr(a, "tradable", False):
                    uni.add(a.symbol.upper())
    except Exception:
        pass

    if not uni:
        p = Path("data/symbols.txt")
        if p.exists():
            uni |= {line.strip().upper() for line in p.read_text().splitlines() if line.strip()}

    if not uni:
        uni |= {"AAPL","MSFT","NVDA","TSLA","AMZN","META","GOOGL","GOOG","AMD","IBM","SPY","QQQ"}

    return uni

def extract_tickers(text: str, prefer_cashtag_only: bool = True, universe: Set[str] | None = None) -> List[str]:
    cashtags = extract_cashtags(text)
    if prefer_cashtag_only:
        return cashtags
    uni = universe or build_symbol_universe()
    bare = extract_bare_tickers(text, uni)
    # 合并去重（保留出现顺序）
    seen, out = set(), []
    for t in cashtags + bare:
        if t not in seen:
            seen.add(t); out.append(t)
    return out

def section_boost(text: str) -> float:
    up = (text or "").upper()
    return 1.5 if any(h in up for h in SECTION_HEADERS) else 1.0

def subj_fuzzy_match(subj: str, wanted: str) -> bool:
    """
    模糊匹配主题：直接包含 或 形如 open\s*out\s*crier 的变体。
    """
    s = (subj or "").lower()
    w = (wanted or "").lower()
    if not w:
        return True
    if w in s:
        return True
    if re.search(r"open\s*out\s*crier", s):
        return True
    return False

# ---------- main ----------
def run_from_email(
    host: str, address: str, app_password: str,
    folder: str = "INBOX",
    subject_keyword: str = "Open OutCrier",
    hours: int = 72,
    out_path: str = "out/social.json",
    log_path: str = "out/social_email.log",
    min_mentions: int = 2,
    topk: int = 8,
):
    log(f"email ingest start: host={host} addr={address} hours={hours}", log_path)

    since = (dt.datetime.utcnow() - dt.timedelta(hours=hours))
    since_str = since.strftime("%d-%b-%Y")  # e.g. 06-Oct-2025

    M = imaplib.IMAP4_SSL(host)
    try:
        M.login(address, app_password)
    except imaplib.IMAP4.error as e:
        log(f"[imap] login failed: {e}", log_path)
        return 1

    M.select(folder)

    # 为避免 IMAP SUBJECT 精确匹配过严：只用关键词的第一个词缩小范围，之后再在 Python 侧做模糊匹配
    first_word = (subject_keyword or "").strip().split()[0] if subject_keyword else ""
    if first_word:
        criteria = f'(SUBJECT "{first_word}" SINCE {since_str})'
    else:
        criteria = f'(SINCE {since_str})'

    typ, data = M.search(None, criteria)
    if typ != "OK":
        log(f"[imap] search failed: {typ}", log_path)
        M.logout()
        return 1

    ids = data[0].split()
    log(f"[imap] matched messages by IMAP: {len(ids)}", log_path)

    # 提取参数：是否只认 $cashtag
    prefer_cashtag_only = os.getenv("EMAIL_ONLY_CASHTAGS", "true").lower() == "true"
    universe = None if prefer_cashtag_only else build_symbol_universe()

    all_texts = []
    for i in ids[-800:]:  # 最多看最近 800 封，避免太多
        typ, body_data = M.fetch(i, "(RFC822)")
        if typ != "OK" or not body_data:
            continue

        raw = body_data[0][1]
        msg = email.message_from_bytes(raw)

        # 主题
        dh = decode_header(msg.get("Subject", ""))
        subj = " ".join(
            safe_decode(t, enc or "utf-8") if isinstance(t, bytes) else (t or "")
            for t, enc in dh
        )

        # Python 侧模糊主题过滤
        if not subj_fuzzy_match(subj, subject_keyword):
            continue

        # 日期
        date_hdr = msg.get("Date")
        try:
            msg_dt = dt.datetime(*email.utils.parsedate(date_hdr)[:6])
        except Exception:
            msg_dt = dt.datetime.utcnow()
        if msg_dt < since:
            continue  # 严格窗口

        # 正文
        content = []
        if msg.is_multipart():
            for part in msg.walk():
                ctype = part.get_content_type()
                disp = (part.get("Content-Disposition") or "").lower()
                if ctype == "text/plain" and "attachment" not in disp:
                    charset = part.get_content_charset() or "utf-8"
                    content.append(safe_decode(part.get_payload(decode=True), charset))
        else:
            charset = msg.get_content_charset() or "utf-8"
            payload = msg.get_payload(decode=True)
            content.append(safe_decode(payload, charset))

        body = "\n".join(content)
        merged = f"{subj}\n{body}"

        # 提取 ticker
        tickers = extract_tickers(merged, prefer_cashtag_only=prefer_cashtag_only, universe=universe)
        if not tickers:
            continue

        all_texts.append((merged, tickers))

    M.close()
    M.logout()

    # 聚合 & 评分（对强信号段落加权）
    counts, scores = {}, {}
    for text, tickers in all_texts:
        s = sentiment_score(text)
        w = section_boost(text)  # 1.0 或 1.5
        for t in tickers:
            counts[t] = counts.get(t, 0.0) + w
            scores[t] = scores.get(t, 0.0) + s * w

    rows = []
    for t, c in counts.items():
        if c < float(min_mentions):
            continue
        avg_s = scores.get(t, 0.0) / max(1.0, c)
        score = c + 0.5 * avg_s
        rows.append((t, c, avg_s, score))
    rows.sort(key=lambda x: x[3], reverse=True)
    top = rows[:topk]

    if not top:
        summary = f"No matches in last {hours}h. Using mock."
        recos = [
            {"ticker": "NVDA", "score": 8.7, "reason": "mentions=20, avg_sent=+3.1"},
            {"ticker": "TSLA", "score": 7.9, "reason": "mentions=18, avg_sent=+2.8"},
            {"ticker": "AAPL", "score": 6.1, "reason": "mentions=12, avg_sent=+1.2"},
        ]
    else:
        bullets = [f"{t} (mentions={int(c)}, avg_sent={avg_s:+.2f})" for t,c,avg_s,_ in top]
        summary = f"Email signals (last {hours}h, subj~\"{subject_keyword}\"):\n" + \
                  "\n".join(f"• {b}" for b in bullets)
        recos = [
            {"ticker": t, "score": float(score),
             "reason": f"mentions={int(c)}, avg_sent={avg_s:+.2f}"} for t,c,avg_s,score in top
        ]

    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump({"summary": summary, "recommendations": recos}, f, indent=2, ensure_ascii=False)

    log(f"✅ saved: {out_path}", log_path)
    return 0


if __name__ == "__main__":
    load_dotenv()
    host  = os.getenv("EMAIL_IMAP_HOST", "imap.gmail.com")
    addr  = os.getenv("EMAIL_ADDRESS")
    apppw = os.getenv("EMAIL_APP_PASSWORD")
    folder = os.getenv("EMAIL_FOLDER", "INBOX")
    # 注意默认改为带空格的版本；模糊匹配也支持 "OpenOutCrier"
    kw    = os.getenv("EMAIL_SUBJECT_KEYWORD", "Open OutCrier")
    hours = int(os.getenv("HOURS_LOOKBACK", "72"))
    outp  = os.getenv("OUT_PATH", "out/social.json")
    logp  = os.getenv("LOG_PATH", "out/social_email.log")
    minm  = int(os.getenv("MIN_MENTIONS", "2"))
    topk  = int(os.getenv("TOPK", "8"))

    if not (addr and apppw):
        print("❌ Missing EMAIL_ADDRESS / EMAIL_APP_PASSWORD")
        raise SystemExit(2)

    raise SystemExit(
        run_from_email(host, addr, apppw, folder, kw, hours, outp, logp, minm, topk)
    )
