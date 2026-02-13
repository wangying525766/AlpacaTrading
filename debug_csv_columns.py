import os
import imaplib
import email
from dotenv import load_dotenv
import pandas as pd
import io

load_dotenv()

HOST = "imap.gmail.com"
USER = os.getenv("EMAIL_ADDRESS")
PASS = os.getenv("EMAIL_APP_PASSWORD")
FOLDER = "INBOX"

def main():
    try:
        M = imaplib.IMAP4_SSL(HOST)
        M.login(USER, PASS)
        M.select(FOLDER)
        
        # Search for FlowAlgo emails
        typ, data = M.search(None, '(FROM "allenw@zgzg.io" SUBJECT "FlowAlgo")')
        ids = data[0].split()
        
        if ids:
            latest_id = ids[-1]
            typ, data = M.fetch(latest_id, "(RFC822)")
            msg = email.message_from_bytes(data[0][1])
            
            for part in msg.walk():
                if part.get_content_maintype() == 'multipart':
                    continue
                if part.get('Content-Disposition') is None:
                    continue
                    
                filename = part.get_filename()
                if filename and "bigflow" in filename.lower():
                    print(f"Found BigFlow attachment: {filename}")
                    payload = part.get_payload(decode=True)
                    
                    try:
                        df = pd.read_csv(io.BytesIO(payload))
                        print("CSV Columns:", df.columns.tolist())
                        print("First row:", df.iloc[0].to_dict())
                    except Exception as e:
                        print(f"Error parsing CSV: {e}")
                        
        M.logout()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
