
import os
from dotenv import load_dotenv

print(f"CWD: {os.getcwd()}")
print(f".env exists: {os.path.exists('.env')}")

load_dotenv()

keys = ["ALPACA_API_KEY", "ALPACA_SECRET_KEY", "OPENAI_API_KEY", "FINNHUB_API_KEY", "FRED_API_KEY", "COINDESK_API_KEY"]
for key in keys:
    val = os.getenv(key)
    print(f"{key}: {'Found' if val else 'Missing'}")
    if val:
        print(f"  Length: {len(val)}")
        print(f"  First 3 chars: {val[:3]}")
