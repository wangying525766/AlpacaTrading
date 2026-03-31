#!/usr/bin/env python3
"""
Backfill recent historical FlowAlgo-derived CSV data and enforce retention.
"""

from __future__ import annotations

import argparse
import datetime as dt
from pathlib import Path
from typing import Dict, List, Tuple


DATA_TARGETS = {
    "bigflow": {"dir": Path("data/bigflow"), "prefix": "bigflow"},
    "unusual_flow": {"dir": Path("data/unusual_flow"), "prefix": "unusual"},
    "key_levels": {"dir": Path("data/key_levels"), "prefix": "key_levels"},
}


def _date_range(days: int) -> List[dt.date]:
    today = dt.date.today()
    start = today - dt.timedelta(days=days - 1)
    return [start + dt.timedelta(days=i) for i in range(days)]


def _path_for(data_key: str, day: dt.date) -> Path:
    cfg = DATA_TARGETS[data_key]
    return cfg["dir"] / f"{cfg['prefix']}_{day.isoformat()}.csv"


def _collect_status(days: int) -> Dict[str, Dict[str, List[str]]]:
    results = {}
    dates = _date_range(days)
    for key in DATA_TARGETS:
        existing = []
        missing = []
        for day in dates:
            date_str = day.isoformat()
            if _path_for(key, day).exists():
                existing.append(date_str)
            else:
                missing.append(date_str)
        results[key] = {"existing": existing, "missing": missing}
    return results


def _parse_file_date(file_path: Path) -> dt.date | None:
    # Expected names: <prefix>_YYYY-MM-DD.csv or <prefix>_YYYYMMDD.csv
    date_token = file_path.stem.split("_")[-1]
    for fmt in ("%Y-%m-%d", "%Y%m%d"):
        try:
            return dt.datetime.strptime(date_token, fmt).date()
        except ValueError:
            continue
    return None


def _enforce_retention(days: int) -> List[Path]:
    cutoff = dt.date.today() - dt.timedelta(days=days)
    deleted = []
    for cfg in DATA_TARGETS.values():
        target_dir = cfg["dir"]
        if not target_dir.exists():
            continue
        for csv_file in target_dir.glob("*.csv"):
            file_date = _parse_file_date(csv_file)
            if file_date is None:
                continue
            if file_date < cutoff:
                csv_file.unlink()
                deleted.append(csv_file)
    return deleted


def _delete_window_files(days: int) -> None:
    for key in DATA_TARGETS:
        for day in _date_range(days):
            path = _path_for(key, day)
            if path.exists():
                path.unlink()


def backfill_recent_history(days: int = 60, overwrite: bool = False) -> Tuple[dict, list]:
    before = _collect_status(days)

    if overwrite:
        print(f"[BACKFILL] Overwrite enabled: deleting existing files in last {days} days window.")
        _delete_window_files(days)
        before = _collect_status(days)

    if any(before[key]["missing"] for key in before):
        # Reuse existing historical ingest pipeline.
        try:
            from scripts.jobs import fetch_flow_data
        except ModuleNotFoundError:
            import fetch_flow_data

        fetch_flow_data.FETCH_DAYS = days
        print(f"[BACKFILL] Running historical fetch for last {days} days...")
        fetch_flow_data.fetch_and_save_data()
    else:
        print("[BACKFILL] No missing dates detected. Skipping fetch.")

    after = _collect_status(days)
    summary = {}
    for key in DATA_TARGETS:
        before_existing = set(before[key]["existing"])
        before_missing = set(before[key]["missing"])
        after_existing = set(after[key]["existing"])

        backfilled = sorted(before_missing & after_existing)
        failed = sorted(before_missing - after_existing)
        skipped_existing = sorted(before_existing if not overwrite else [])

        summary[key] = {
            "backfilled": backfilled,
            "skipped_existing": skipped_existing,
            "failed": failed,
        }

    deleted = _enforce_retention(days)
    return summary, deleted


def _print_summary(summary: dict, deleted: List[Path]) -> None:
    for key, status in summary.items():
        print(f"\n[{key}]")
        print(f"  backfilled ({len(status['backfilled'])}): {status['backfilled']}")
        print(f"  skipped existing ({len(status['skipped_existing'])}): {status['skipped_existing']}")
        print(f"  failed ({len(status['failed'])}): {status['failed']}")

    print(f"\n[RETENTION] deleted old files ({len(deleted)}):")
    for path in deleted:
        print(f"  - {path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backfill recent history and enforce retention.")
    parser.add_argument("--days", type=int, default=60, help="Window size in days (default: 60)")
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Delete existing files in the window before backfill.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    summary, deleted = backfill_recent_history(days=args.days, overwrite=args.overwrite)
    _print_summary(summary, deleted)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
