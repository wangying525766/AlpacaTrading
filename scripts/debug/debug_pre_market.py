import os
import imaplib
import email
import datetime as dt
from email.header import decode_header
from dotenv import load_dotenv

load_dotenv()

HOST = "imap.gmail.com"
USER = os.getenv("EMAIL_ADDRESS")
PASS = os.getenv("EMAIL_APP_PASSWORD")
FOLDER = "INBOX"

def decode_str(s):
    try:
        dh = decode_header(s)
        return "".join(
            (t.decode(enc or 'utf-8') if isinstance(t, bytes) else t)
            for t, enc in dh
        )
    except:
        return str(s)

def main():
    try:
        M = imaplib.IMAP4_SSL(HOST)
        M.login(USER, PASS)
        M.select(FOLDER)
        
        # Search for Open Outcrier emails (any time)
        print("Searching for Open Outcrier emails...")
        # typ, data = M.search(None, '(FROM "allenw@zgzg.io" SUBJECT "Open Outcrier")')
        # Maybe broaden the search first
        typ, data = M.search(None, '(SUBJECT "Open Outcrier")')
        
        ids = data[0].split()
        print(f"Found {len(ids)} Open Outcrier emails.")
        
        if ids:
            latest_id = ids[-1]
            typ, data = M.fetch(latest_id, "(RFC822)")
            msg = email.message_from_bytes(data[0][1])
            subj = decode_str(msg.get("Subject"))
            sender = decode_str(msg.get("From"))
            date = decode_str(msg.get("Date"))
            print(f"Latest Email:")
            print(f" - Subject: {subj}")
            print(f" - From: {sender}")
            print(f" - Date: {date}")
            
            # Check structure
            typ, s_data = M.fetch(latest_id, "(BODYSTRUCTURE)")
            print(f" - Structure: {s_data[0]}")
            
            # Check content
            if msg.is_multipart():
                for part in msg.walk():
                    ctype = part.get_content_type()
                    cdisp = str(part.get("Content-Disposition"))
                    print(f"   - Part: {ctype}, Disposition: {cdisp}")
            else:
                print(f"   - Single part: {msg.get_content_type()}")
                payload = msg.get_payload(decode=True)
                if payload:
                    print(f"   - Content len: {len(payload)}")

        M.logout()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
