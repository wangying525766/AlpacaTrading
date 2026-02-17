import os
import datetime as dt
from pathlib import Path

DATA_DIRS = ["data/bigflow", "data/unusual_flow"]
RETENTION_DAYS = 60

def cleanup_old_files():
    """Removes files older than RETENTION_DAYS from DATA_DIRS."""
    cutoff_date = dt.datetime.now() - dt.timedelta(days=RETENTION_DAYS)
    print(f"Removing files older than {cutoff_date.strftime('%Y-%m-%d')}...")

    for data_dir in DATA_DIRS:
        p = Path(data_dir)
        if not p.exists():
            print(f"Directory not found, skipping: {data_dir}")
            continue

        for f in p.glob("*.csv"):
            try:
                date_str = f.stem.split('_')[-1]
                
                try:
                    file_date = dt.datetime.strptime(date_str, '%Y-%m-%d')
                except ValueError:
                    file_date = dt.datetime.strptime(date_str, '%Y%m%d')

                if file_date < cutoff_date:
                    print(f"Deleting old file: {f}")
                    f.unlink()
            except ValueError:
                print(f"Could not parse date from filename, skipping: {f.name}")
                continue
            except Exception as e:
                print(f"Error processing file {f}: {e}")

if __name__ == "__main__":
    cleanup_old_files()
    print("Cleanup process finished.")
