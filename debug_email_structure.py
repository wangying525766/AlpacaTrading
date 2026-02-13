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
    if not (USER and PASS):
        print("Credentials missing")
        return

    try:
        M = imaplib.IMAP4_SSL(HOST)
        M.login(USER, PASS)
        M.select(FOLDER)

        sender_email = "allenw@zgzg.io"
        print(f"Searching for emails from: {sender_email} with subject 'FlowAlgo'")
        
        # Search for FlowAlgo emails
        typ, data = M.search(None, f'(FROM "{sender_email}" SUBJECT "FlowAlgo")')
        
        ids = data[0].split()
        print(f"Found {len(ids)} FlowAlgo emails.")
        
        if ids:
            # Check the latest one
            latest_id = ids[-1]
            typ, data = M.fetch(latest_id, "(RFC822)")
            msg = email.message_from_bytes(data[0][1])
            subj = decode_str(msg.get("Subject"))
            print(f"Latest Email Subject: {subj}")
            
            # Check structure
            typ, s_data = M.fetch(latest_id, "(BODYSTRUCTURE)")
            print(f"Structure: {s_data[0]}")
            
            # Check content type and payload
            if msg.is_multipart():
                print("Multipart message")
                for part in msg.walk():
                    ctype = part.get_content_type()
                    cdisp = str(part.get("Content-Disposition"))
                    print(f" - Part: {ctype}, Disposition: {cdisp}")
                    if "attachment" in cdisp:
                        print(f"   Attachment found: {part.get_filename()}")
            else:
                print(f"Single part message: {msg.get_content_type()}")

        M.logout()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
