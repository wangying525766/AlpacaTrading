#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
email_ticker_ingest.py
Ingest tickers/data from emails (OpenOutCrier, FlowAlgo, etc.)
"""

import os
import re
import imaplib
import email
import datetime as dt
import json
import pandas as pd
from email.header import decode_header
from pathlib import Path
from dotenv import load_dotenv
import io

# Load environment variables
load_dotenv()

# Configuration
EMAIL_HOST = "imap.gmail.com"  # Default to Gmail, can be changed
EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS")
EMAIL_APP_PASSWORD = os.getenv("EMAIL_APP_PASSWORD")

# Output paths
OUT_DIR = Path("out")
ATTACHMENT_DIR = OUT_DIR / "attachments"


def safe_decode(bytes_or_str, enc='utf-8'):
    if isinstance(bytes_or_str, bytes):
        try:
            return bytes_or_str.decode(enc, errors="ignore")
        except Exception:
            return bytes_or_str.decode("utf-8", errors="ignore")
    return bytes_or_str or ""

def get_email_content_and_attachments(msg):
    """Extract content and attachments from email message"""
    content = ""
    attachments = []
    
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            content_disposition = str(part.get("Content-Disposition"))
            
            if "attachment" in content_disposition:
                filename = part.get_filename()
                if filename:
                    filename = safe_decode(filename)
                    file_data = part.get_payload(decode=True)
                    attachments.append({
                        "filename": filename,
                        "data": file_data,
                        "content_type": content_type
                    })
            
            elif content_type == "text/plain" and "attachment" not in content_disposition:
                try:
                    body = part.get_payload(decode=True)
                    content += safe_decode(body)
                except:
                    pass
    else:
        content = safe_decode(msg.get_payload(decode=True))
    
    return content, attachments

def process_attachments(attachments):
    """Process attachments and extract data if possible (CSV/Excel)"""
    processed_data = []
    
    ATTACHMENT_DIR.mkdir(parents=True, exist_ok=True)
    
    for att in attachments:
        filename = att["filename"]
        file_path = ATTACHMENT_DIR / filename
        
        # Save file
        with open(file_path, "wb") as f:
            f.write(att["data"])
            
        # Try to parse if it's data
        data_records = None
        try:
            if filename.lower().endswith(".csv"):
                df = pd.read_csv(io.BytesIO(att["data"]))
                data_records = df.to_dict('records')
            elif filename.lower().endswith((".xls", ".xlsx")):
                df = pd.read_excel(io.BytesIO(att["data"]))
                data_records = df.to_dict('records')
        except Exception as e:
            print(f"Failed to parse attachment {filename}: {e}")
            
        processed_data.append({
            "filename": filename,
            "path": str(file_path),
            "data": data_records
        })
        
    return processed_data

def fetch_latest_email(subject_keyword, sender_email=None, folder="INBOX", hours=24):
    """Fetch the latest email with the given subject keyword and optional sender"""
    if not EMAIL_ADDRESS or not EMAIL_APP_PASSWORD:
        return {"error": "Email credentials not configured in .env"}

    try:
        M = imaplib.IMAP4_SSL(EMAIL_HOST)
        M.login(EMAIL_ADDRESS, EMAIL_APP_PASSWORD)
        M.select(folder)
        
        # Build search criteria
        search_criteria = [f'(SUBJECT "{subject_keyword}")']
        
        # Only add time constraint if hours > 0
        if hours > 0:
            since = (dt.datetime.utcnow() - dt.timedelta(hours=hours))
            since_str = since.strftime("%d-%b-%Y")
            search_criteria.append(f'(SINCE {since_str})')
            
        if sender_email:
            search_criteria.append(f'(FROM "{sender_email}")')
            
        # Join criteria
        criteria_str = " ".join(search_criteria)
        print(f"IMAP Search: {criteria_str}")
        
        # Search for emails
        typ, data = M.search(None, criteria_str)
        
        if typ != "OK":
            M.logout()
            return {"error": f"Search failed for {subject_keyword}"}
            
        ids = data[0].split()
        if not ids:
            M.logout()
            return {"message": f"No emails found for '{subject_keyword}'"}
            
        # Fetch the latest one
        latest_id = ids[-1]
        typ, msg_data = M.fetch(latest_id, "(RFC822)")
        
        if typ != "OK":
            M.logout()
            return {"error": "Failed to fetch email content"}
            
        raw_email = msg_data[0][1]
        msg = email.message_from_bytes(raw_email)
        
        subject, encoding = decode_header(msg["Subject"])[0]
        if isinstance(subject, bytes):
            subject = safe_decode(subject, encoding or "utf-8")
            
        # Filter: Ensure subject actually starts with the keyword (case insensitive) if strictly required
        if not subject.lower().strip().startswith(subject_keyword.lower()):
            # Iterate backwards to find the true latest match
            found = False
            for email_id in reversed(ids):
                if email_id == latest_id: continue # already fetched
                
                # Fetch headers only to check subject
                typ, header_data = M.fetch(email_id, '(BODY.PEEK[HEADER.FIELDS (SUBJECT)])')
                header_msg = email.message_from_bytes(header_data[0][1])
                subj, enc = decode_header(header_msg["Subject"])[0]
                if isinstance(subj, bytes):
                    subj = safe_decode(subj, enc or "utf-8")
                
                if subj.lower().strip().startswith(subject_keyword.lower()):
                    # Fetch full body
                    typ, msg_data = M.fetch(email_id, "(RFC822)")
                    raw_email = msg_data[0][1]
                    msg = email.message_from_bytes(raw_email)
                    subject = subj
                    found = True
                    break
            
            if not found and not subject.lower().strip().startswith(subject_keyword.lower()):
                 M.logout()
                 return {"message": f"No email found starting with '{subject_keyword}'"}

        content, attachments = get_email_content_and_attachments(msg)
        date_str = msg.get("Date")
        
        M.logout()
        
        # Process attachments
        processed_attachments = process_attachments(attachments)
        
        # Parse Pre-Market data (Open Outcrier) if applicable
        parsed_pre_market = None
        if "Open Outcrier" in subject_keyword or "Open Outcrier" in subject:
            parsed_pre_market = parse_open_outcrier_content(content)
            
        return {
            "subject": subject,
            "date": date_str,
            "content": content,
            "parsed_data": parsed_pre_market,
            "attachments": processed_attachments,
            "timestamp": dt.datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        return {"error": str(e)}

def parse_open_outcrier_content(content):
    """
    Parse the Open Outcrier email content to extract Gainers and Losers.
    Format: $TICKER (+X.X% pre) Headline
    """
    gainers = []
    losers = []
    
    # Regex for lines like: $IRDM (+5.7% pre) Iridium: Q4 Earnings Snapshot
    # Matches: Ticker, Sign, Value, Headline
    # Updated regex to handle possible spaces
    pattern = re.compile(r'^\$(\w+)\s*\(([+-]?)(\d+\.?\d*)%?\s*pre\)\s*(.*)$', re.IGNORECASE)
    
    for line in content.splitlines():
        line = line.strip()
        if not line.startswith("$"): continue
        
        match = pattern.match(line)
        if match:
            ticker = match.group(1).upper()
            sign = match.group(2)
            if not sign: sign = "+"
            value = float(match.group(3))
            headline = match.group(4).strip()
            
            # Reconstruct percentage string
            change_str = f"{sign}{value}%"
            
            item = {
                "TICKER": ticker,
                "PRICE": "N/A", # Price is not explicitly in the line, usually just change
                "CHANGE": change_str,
                "HEADLINE": headline
            }
            
            if sign == "-":
                losers.append(item)
            else:
                gainers.append(item)
                
    return {
        "gainers": gainers,
        "losers": losers
    }

import pytz

def update_market_data():
    """Fetch and update both pre and post market data"""
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    
    pre_market_data = None
    post_market_data = None

    # Timezone setup
    pst = pytz.timezone('America/Los_Angeles')
    now_pst = dt.datetime.now(pst).time()
    
    # Pre-market fetch logic
    pre_market_file = OUT_DIR / "pre_market.json"

    if now_pst > dt.time(6, 30):
        print("Fetching Pre-Market (OpenOutCrier)...")
        pre_market_data = fetch_latest_email("Open Outcrier", sender_email=None, hours=12)
        # Only write file if data is valid
        if pre_market_data and "error" not in pre_market_data and "message" not in pre_market_data:
            with open(pre_market_file, "w") as f:
                json.dump(pre_market_data, f, indent=2, default=str)
        else:
            print(f"Pre-market fetch did not yield valid data: {pre_market_data}")
    else:
        print("Skipping pre-market fetch. It is before 6:30 AM PST.")
        
    # Post-market fetch logic
    post_market_file = OUT_DIR / "post_market.json"
    if now_pst > dt.time(13, 40):
        print("Fetching Post-Market (FlowAlgo)...")
        post_market_data = fetch_latest_email("FlowAlgo", sender_email="allenw@zgzg.io", hours=12)
        # Only write file if data is valid
        if post_market_data and "error" not in post_market_data and "message" not in post_market_data:
            with open(post_market_file, "w") as f:
                json.dump(post_market_data, f, indent=2, default=str)
        else:
            print(f"Post-market fetch did not yield valid data: {post_market_data}")
    else:
        print("Skipping post-market fetch. It is before 1:40 PM PST.")
        
    return {
        "pre_market": pre_market_data,
        "post_market": post_market_data
    }

if __name__ == "__main__":
    update_market_data()
