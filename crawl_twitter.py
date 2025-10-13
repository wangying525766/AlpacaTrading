#!/usr/bin/env python3
"""
crawl_social.py — unified social sentiment crawler (Twitter + Reddit + Mock fallback)
Output: JSON with {"summary": str, "recommendations": [ {ticker, score, reason}, ... ]}
"""

import argparse, sys, re, json, datetime as dt
from pathlib import Path

# -------------------- 通用工具 --------------------
def log(msg, lf=None):
    s = f"[{dt.datetime.utcnow().isoformat(timespec='seconds')}Z] {msg}"
    if lf:
        Path(lf).parent.mkdir(parents=True, exist_ok=True)  # ← 自动建父目录
        with open(lf, "a") as f:
            f.write(s + "\n")
    print(s, flush=True)


TICKER_RE = re.compile(r"\$([A-Z]{1,5})\b|(?<![A-Z])([A-Z]{1,5})(?![A-Z])")
POS = {"buy","bull","call","long","breakout","moon","pump","rip","up"}
NEG = {"sell","bear","put","short","dump","drop","down","bag"}
NOISE = {"USD","AI","CEO","ETF","THE","AND","FOR"}

def extract_tickers(text: str):
    cands = []
    for m in TICKER_RE.finditer((text or "").upper()):
        t = m.group(1) or m.group(2)
        if not t or t in NOISE:
            continue
        cands.append(t)
    return cands

def sentiment_score(text: str):
    txt = (text or "").lower()
    p = sum(w in txt for w in POS)
    n = sum(w in txt for w in NEG)
    return p - n


# -------------------- Twitter 爬取 --------------------
# def crawl_twitter(query, hours, lang, max_tweets, log_path):
#     try:
#         from snscrape.modules.twitter import TwitterSearchScraper
#         TwitterSearchScraper.BASE_URL = "https://nitter.net"  # 替代防封源
#         since_date = (dt.datetime.utcnow() - dt.timedelta(hours=hours)).strftime("%Y-%m-%d")
#         q = f'{query} lang:{lang} since:{since_date} -filter:retweets -filter:replies'
#         scraper = TwitterSearchScraper(q)
#         log(f"[twitter] query={q}", log_path)
#     except Exception as e:
#         log(f"[twitter] import failed: {e}", log_path)
#         return []
#
#     data = []
#     try:
#         for i, tweet in enumerate(scraper.get_items()):
#             if max_tweets and i >= max_tweets:
#                 break
#             content = getattr(tweet, "content", "") or ""
#             if not content:
#                 continue
#             tickers = extract_tickers(content)
#             if tickers:
#                 data.append((content, tickers))
#             if i % 100 == 0 and i > 0:
#                 log(f"[twitter] fetched={i}", log_path)
#     except Exception as e:
#         log(f"[twitter] scraping failed: {e}", log_path)
#     return data

# -------------------- Twitter API 版（按账号抓取） --------------------
# -------------------- Twitter API 版（search/recent 优先，含429退避） --------------------
# -------------------- Twitter API 版（fast-fail on 429，命中2条即停） --------------------
def crawl_twitter(
    username: str = "OpenOutcrier",
    hours: int = 72,
    max_hits: int = 2,
    log_path: str = None,
    fast_fail_on_429: bool = True,  # ← 被限速时立刻返回 []，上层会走 mock
):
    """
    先用 /2/tweets/search/recent 按关键词+账户抓（更宽松的配额），
    若 0 命中，再退回 /2/users/:id/tweets 拉一页筛选。
    任一端点遇到 429 且 fast_fail_on_429=True 时，立即返回 []。
    返回: [(text, [tickers...]), ...]
    """
    import os, requests, datetime as dt
    from dotenv import load_dotenv

    load_dotenv()
    bearer = os.getenv("X_BEARER_TOKEN")
    if not bearer:
        log("[twitter] ❌ Missing X_BEARER_TOKEN", log_path)
        return []

    headers = {"Authorization": f"Bearer {bearer}"}
    base = "https://api.twitter.com/2"  # 更稳的 v2 基础域名

    # —— 时间窗（UTC-aware）
    cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=hours)
    start_time = cutoff.isoformat().replace("+00:00", "Z")

    # —— 关键词集合（宽口径，且要求有 $cashtag）
    key_or = '( "unusual options activity" OR "unusual activity" OR uoa OR "unusual call" OR "call flow" OR "calls sweep" OR "call sweeps" OR sweep )'
    query = f'from:{username} {key_or} has:cashtags -is:retweet -is:reply'

    def _within(ts_iso: str) -> bool:
        try:
            t = dt.datetime.fromisoformat(ts_iso.replace("Z", "+00:00"))
            if t.tzinfo is None:
                t = t.replace(tzinfo=dt.timezone.utc)
        except Exception:
            return False
        return t >= cutoff

    def _extract(text, entities):
        # 优先用 entities.cashtags；否则退回正则
        if entities and "cashtags" in entities:
            tags = [c.get("tag", "").upper() for c in entities["cashtags"] if c.get("tag")]
            return [t for t in tags if 1 <= len(t) <= 5]
        return extract_tickers(text)

    data, hits = [], 0

    # ========== 第一层：/tweets/search/recent ==========
    log(f"[twitter] search recent: {query} | start_time={start_time}", log_path)
    url = f"{base}/tweets/search/recent"
    params = {
        "query": query,
        "tweet.fields": "created_at,lang,entities",
        "max_results": 10,          # 小批次足够
        "start_time": start_time,   # 限定时间窗
    }
    resp = requests.get(url, headers=headers, params=params, timeout=20)
    if resp.status_code == 429:
        if fast_fail_on_429:
            log("[twitter] 429 rate-limited → fast-fail to mock.", log_path)
            return []  # 让上层走 mock
    elif resp.status_code != 200:
        log(f"[twitter] search/recent failed: {resp.status_code} {resp.text[:120]}", log_path)
    else:
        js = resp.json()
        for tw in js.get("data", []):
            if tw.get("lang") and tw["lang"] != "en":
                continue
            if not _within(tw.get("created_at", "")):
                continue
            text = tw.get("text", "") or ""
            ents = tw.get("entities", {})
            up = text.upper()
            if any(k in up for k in ["UNUSUAL OPTIONS ACTIVITY","UNUSUAL ACTIVITY","UOA","UNUSUAL CALL","CALL FLOW","CALLS SWEEP","CALL SWEEPS","SWEEP"]):
                tickers = _extract(text, ents)
                if tickers:
                    hits += 1
                    data.append((text, tickers))
                    clean = text[:80].replace("\n", " ")
                    log(f"[twitter] hit {hits}: {clean}", log_path)
                    if hits >= max_hits:
                        return data

    if hits >= max_hits:
        return data

    # ========== 第二层兜底：/users/:id/tweets ==========
    # 只在第一层没有达到 max_hits 时才尝试
    try:
        r = requests.get(f"{base}/users/by/username/{username}", headers=headers, timeout=15)
        r.raise_for_status()
        user_id = r.json()["data"]["id"]
        log(f"[twitter] user @{username} -> id {user_id}", log_path)
    except Exception as e:
        log(f"[twitter] fallback get user id failed: {e}", log_path)
        return data  # 不阻断；让上层依然能 fallback mock

    url2 = f"{base}/users/{user_id}/tweets"
    params2 = {
        "exclude": "retweets,replies",
        "tweet.fields": "created_at,lang,entities",
        "max_results": 50,
    }
    resp2 = requests.get(url2, headers=headers, params=params2, timeout=20)
    if resp2.status_code == 429:
        if fast_fail_on_429:
            log("[twitter] timeline 429 → fast-fail to mock.", log_path)
            return []
    elif resp2.status_code != 200:
        log(f"[twitter] users/:id/tweets failed: {resp2.status_code} {resp2.text[:120]}", log_path)
        return data

    js2 = resp2.json() if resp2.status_code == 200 else {}
    items = js2.get("data", [])
    for tw in items:
        if tw.get("lang") and tw["lang"] != "en":
            continue
        if not _within(tw.get("created_at", "")):
            break
        text = tw.get("text", "") or ""
        ents = tw.get("entities", {})
        up = text.upper()
        if any(k in up for k in ["UNUSUAL OPTIONS ACTIVITY","UNUSUAL ACTIVITY","UOA","UNUSUAL CALL","CALL FLOW","CALLS SWEEP","CALL SWEEPS","SWEEP"]):
            tickers = _extract(text, ents)
            if tickers:
                hits += 1
                data.append((text, tickers))
                clean = text[:80].replace("\n", " ")
                log(f"[twitter] [timeline] hit {hits}: {clean}", log_path)
                if hits >= max_hits:
                    break

    return data





# -------------------- Reddit 爬取 --------------------
def crawl_reddit(query, hours, log_path):
    try:
        import requests
        since = int((dt.datetime.utcnow() - dt.timedelta(hours=hours)).timestamp())
        url = (
            "https://api.pushshift.io/reddit/search/submission?"
            f"q={query.replace(' ', '+')} "
            "(subreddit:wallstreetbets OR subreddit:stocks OR subreddit:investing OR subreddit:options)"
            f" timestamp:{dt.datetime.utcnow().strftime('%Y-%m-%d')}..&limit=1000"
        )
        log(f"[reddit] {url}", log_path)
        r = requests.get(url, timeout=15)
        if r.status_code != 200:
            log(f"[reddit] failed with status={r.status_code}", log_path)
            return []
        posts = r.json().get("data", [])
    except Exception as e:
        log(f"[reddit] scraping failed: {e}", log_path)
        return []

    data = []
    for p in posts:
        txt = p.get("title", "") + " " + p.get("selftext", "")
        tickers = extract_tickers(txt)
        if tickers:
            data.append((txt, tickers))
    return data


# -------------------- 主逻辑 + fallback --------------------
def aggregate_and_save(all_texts, hours, query, topk, min_mentions, out, log_path):
    counts, scores = {}, {}
    for text, tickers in all_texts:
        s = sentiment_score(text)
        for t in tickers:
            counts[t] = counts.get(t, 0) + 1
            scores[t] = scores.get(t, 0.0) + s

    rows = []
    for t, c in counts.items():
        if c < min_mentions:
            continue
        avg_s = scores.get(t, 0.0) / max(1, c)
        score = c + 0.5 * avg_s
        rows.append((t, c, avg_s, score))
    rows.sort(key=lambda x: x[3], reverse=True)
    top = rows[:topk]

    if not top:
        log("⚠️ No data — using mock fallback.", log_path)
        summary = "Mock data: example trending tickers (Twitter/Reddit unavailable)."
        recos = [
            {"ticker": "NVDA", "score": 8.7, "reason": "mentions=20, avg_sent=+3.1"},
            {"ticker": "TSLA", "score": 7.9, "reason": "mentions=18, avg_sent=+2.8"},
            {"ticker": "AMD",  "score": 6.5, "reason": "mentions=14, avg_sent=+1.7"},
            {"ticker": "AAPL", "score": 5.9, "reason": "mentions=11, avg_sent=+1.2"},
            {"ticker": "SMCI", "score": 4.8, "reason": "mentions=9,  avg_sent=+0.9"}
        ]
    else:
        bullets = [f"{t} (mentions={c}, avg_sent={avg_s:+.2f})" for t,c,avg_s,_ in top]
        summary = (
            f"Top social tickers (last {hours}h, query='{query}'):\n"
            + "\n".join(f"• {b}" for b in bullets)
        )
        recos = [
            {"ticker": t, "score": float(score),
             "reason": f"mentions={c}, avg_sent={avg_s:+.2f}"} for t,c,avg_s,score in top
        ]

    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w") as f:
        json.dump({"summary": summary, "recommendations": recos}, f, indent=2)
    log(f"✅ result saved: {out}", log_path)
    log("crawl done.", log_path)


# -------------------- main --------------------
def run(query, hours, topk, min_mentions, out, log_path, lang="en", max_tweets=None):
    log(f"crawl start: query={query} hours={hours}", log_path)
    data = []

#     tw = crawl_twitter(query, hours, lang, max_tweets, log_path)
    tw = crawl_twitter(username="OpenOutcrier", hours=hours, max_hits=2, log_path=log_path)

    rd = crawl_reddit(query, hours, log_path)

    data.extend(tw)
    data.extend(rd)

    aggregate_and_save(data, hours, query, topk, min_mentions, out, log_path)
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--query", required=True)
    ap.add_argument("--hours", type=int, default=6)
    ap.add_argument("--topk", type=int, default=8)
    ap.add_argument("--min-mentions", type=int, default=3)
    ap.add_argument("--out", required=True)
    ap.add_argument("--log", required=True)
    ap.add_argument("--lang", type=str, default="en")
    ap.add_argument("--max-tweets", type=int, default=None)
    args = ap.parse_args()
    sys.exit(run(args.query, args.hours, args.topk, args.min_mentions,
                 Path(args.out), Path(args.log), args.lang, args.max_tweets))

if __name__ == "__main__":
    main()
