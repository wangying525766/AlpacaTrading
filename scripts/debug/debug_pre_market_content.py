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
        
        typ, data = M.search(None, '(SUBJECT "Open Outcrier")')
        ids = data[0].split()
        
        if ids:
            latest_id = ids[-1]
            typ, data = M.fetch(latest_id, "(RFC822)")
            msg = email.message_from_bytes(data[0][1])
            subj = decode_str(msg.get("Subject"))
            print(f"Subject: {subj}")
            
            content = ""
            if msg.is_multipart():
                for part in msg.walk():
                    ctype = part.get_content_type()
                    if ctype == "text/plain":
                        try:
                            content += part.get_payload(decode=True).decode("utf-8", errors="ignore")
                        except: pass
            else:
                content = msg.get_payload(decode=True).decode("utf-8", errors="ignore")
            
            print("\n--- EMAIL CONTENT START ---\n")
            print(content)
            print("\n--- EMAIL CONTENT END ---\n")

        M.logout()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
