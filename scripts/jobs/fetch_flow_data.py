import os
import imaplib
import email
import re
import datetime as dt
from email.header import decode_header
from pathlib import Path
from dotenv import load_dotenv
try:
    from scripts.jobs.cleanup_old_data import cleanup_old_files
except ModuleNotFoundError:
    from cleanup_old_data import cleanup_old_files

load_dotenv()

HOST = os.getenv("EMAIL_IMAP_HOST", "imap.gmail.com")
USER = os.getenv("EMAIL_ADDRESS")
PASS = os.getenv("EMAIL_APP_PASSWORD")
FOLDER = os.getenv("EMAIL_FOLDER", "INBOX")
DATA_DIRS = {
    "bigflow": "data/bigflow",
    "unusual_flow": "data/unusual_flow",
    "key_levels": "data/key_levels"
}
FETCH_DAYS = 60

def fetch_and_save_data():
    """
    Connects to the email server, fetches FlowAlgo CSV attachments,
    and saves them directly to the appropriate data directory.
    """
    if not (USER and PASS):
        print("Missing email credentials in .env file. Skipping email fetch.")
        return

    try:
        M = imaplib.IMAP4_SSL(HOST)
        M.login(USER, PASS)
        M.select(FOLDER)

        since_date = (dt.datetime.now() - dt.timedelta(days=FETCH_DAYS)).strftime("%d-%b-%Y")
        print(f"Searching for 'FlowAlgo' or 'Daily Report' emails since {since_date}...")

        criteria = f'(OR (SUBJECT "FlowAlgo") (SUBJECT "Daily Report")) (SINCE "{since_date}")'
        typ, data = M.search(None, criteria)

        if typ != 'OK':
            print(f"Error searching for emails: {data}")
            M.logout()
            return

        ids = data[0].split()
        print(f"Found {len(ids)} emails.")

        for i in reversed(ids):
            typ, data = M.fetch(i, "(RFC822)")
            if typ != 'OK':
                continue
            
            msg = email.message_from_bytes(data[0][1])

            for part in msg.walk():
                fname = part.get_filename()
                if not (fname and fname.endswith(".csv")):
                    continue

                file_type_key = None
                # Check for 'unusual' first as it's more specific
                if "unusual" in fname.lower():
                    file_type_key = "unusual_flow"
                elif "bigflow" in fname.lower():
                    file_type_key = "bigflow"
                elif "levels" in fname.lower():
                    file_type_key = "key_levels"

                if not file_type_key:
                    continue

                match = re.search(r'_(\d{8})_', fname)
                if not match:
                    continue
                
                date_str = match.group(1)
                formatted_date = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"
                
                dest_dir = Path(DATA_DIRS[file_type_key])
                if file_type_key == "unusual_flow":
                    file_prefix = "unusual"
                elif file_type_key == "bigflow":
                    file_prefix = "bigflow"
                else:
                    file_prefix = "key_levels"
                out_filename = f"{file_prefix}_{formatted_date}.csv"
                dest_file_path = dest_dir / out_filename

                if dest_file_path.exists():
                    continue

                payload = part.get_payload(decode=True)
                if not payload:
                    continue

                try:
                    dest_dir.mkdir(parents=True, exist_ok=True)
                    with open(dest_file_path, "wb") as f:
                        f.write(payload)
                    print(f"Saved new file: {dest_file_path}")
                except IOError as e:
                    print(f"Error saving file {dest_file_path}: {e}")

        M.logout()

    except Exception as e:
        print(f"An error occurred during email fetching: {e}")

if __name__ == "__main__":
    print("--- Starting Data Cleanup ---")
    cleanup_old_files()
    print("--- Cleanup Finished ---")
    
    print("\n--- Starting Data Fetch ---")
    fetch_and_save_data()
    print("--- Data Fetch Finished ---")
