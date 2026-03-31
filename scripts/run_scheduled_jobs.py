#!/usr/bin/env python3
"""
Long-running worker scheduler for recurring data jobs.
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, time as dt_time
from pathlib import Path
from zoneinfo import ZoneInfo


LOCAL_TZ = ZoneInfo("America/Los_Angeles")
STATE_FILE = Path("data/metadata/job_state.json")
DEFAULT_STATE = {"premarket": None, "afterhours": None, "cleanup": None}


def _log(message: str) -> None:
    ts = datetime.now(LOCAL_TZ).isoformat(timespec="seconds")
    print(f"[{ts}] {message}", flush=True)


def load_job_state() -> dict:
    """Load local scheduler state safely."""
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not STATE_FILE.exists():
        save_job_state(DEFAULT_STATE.copy())
        return DEFAULT_STATE.copy()

    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            raw = json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        _log(f"State file missing/corrupt, resetting: {exc}")
        save_job_state(DEFAULT_STATE.copy())
        return DEFAULT_STATE.copy()

    state = DEFAULT_STATE.copy()
    if isinstance(raw, dict):
        for key in state:
            state[key] = raw.get(key)
    return state


def save_job_state(state: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


def run_premarket_job() -> None:
    from scripts.jobs.email_ticker_ingest import ingest_emails

    _log("Starting premarket job")
    ingest_emails("premarket")
    _log("Finished premarket job")


def run_afterhours_job() -> None:
    from scripts.jobs.email_ticker_ingest import ingest_emails

    _log("Starting afterhours job")
    ingest_emails("afterhours")
    _log("Finished afterhours job")


def run_cleanup_job() -> None:
    from scripts.jobs.cleanup_old_data import cleanup_old_files

    _log("Starting cleanup job")
    cleanup_old_files()
    _log("Finished cleanup job")


def scheduler_loop() -> None:
    sleep_minutes = int(os.getenv("WORKER_SLEEP_MINUTES", "10"))
    sleep_seconds = max(60, sleep_minutes * 60)
    _log(f"Scheduler started (interval={sleep_minutes} minutes)")

    while True:
        now = datetime.now(LOCAL_TZ)
        today = now.date().isoformat()
        state = load_job_state()

        # Only run jobs Monday-Friday.
        if now.weekday() >= 5:
            _log("Skipping jobs (weekend)")
            time.sleep(sleep_seconds)
            continue

        if now.time() >= dt_time(6, 30):
            if state.get("premarket") == today:
                _log("Skipping premarket job (already ran today)")
            else:
                try:
                    run_premarket_job()
                    state["premarket"] = today
                    save_job_state(state)
                except Exception as exc:
                    _log(f"Premarket job failed: {exc}")

        if now.time() >= dt_time(13, 30):
            if state.get("afterhours") == today:
                _log("Skipping afterhours job (already ran today)")
            else:
                try:
                    run_afterhours_job()
                    state["afterhours"] = today
                    save_job_state(state)
                except Exception as exc:
                    _log(f"Afterhours job failed: {exc}")

        if state.get("cleanup") == today:
            _log("Skipping cleanup job (already ran today)")
        else:
            try:
                run_cleanup_job()
                state["cleanup"] = today
                save_job_state(state)
            except Exception as exc:
                _log(f"Cleanup job failed: {exc}")

        time.sleep(sleep_seconds)


if __name__ == "__main__":
    scheduler_loop()
